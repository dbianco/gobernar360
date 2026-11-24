"""Sign-in, sign-out, the current user's profile, and password links sent by email."""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, StringConstraints
from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.config import get_settings
from gobernar360.core.errors import (
    ApiError,
    forbidden,
    municipality_suspended,
    validation_error,
)
from gobernar360.core.security import new_token, normalize_email, verify_password
from gobernar360.platform import accounts
from gobernar360.platform.access import (
    SESSION_COOKIE,
    CurrentSession,
    CurrentUser,
    Db,
    effective_levels,
    reachable,
)
from gobernar360.platform.models import Membership, User
from gobernar360.platform.models import Session as SessionRow
from gobernar360.platform.schemas import (
    DashboardAccessOut,
    Email,
    Me,
    MembershipOut,
    MunicipalityOut,
    Password,
    Phone,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class ActiveMunicipalityIn(BaseModel):
    municipality_id: uuid.UUID


def _memberships(db: Session, user: User, session_row: SessionRow) -> list[Membership]:
    """The memberships this session may use."""
    memberships = db.scalars(select(Membership).where(Membership.user_id == user.id)).unique()
    return reachable(db, session_row, list(memberships))


def build_me(db: Session, user: User, session_row: SessionRow) -> Me:
    every = sorted(_memberships(db, user, session_row), key=lambda m: m.municipality.name)
    memberships = [m for m in every if not m.municipality.is_suspended]
    active_id = session_row.active_municipality_id
    # A membership removed after sign-in must not leave a stale active municipality, and a
    # suspended one is not active. The session keeps it, so resuming brings the user back.
    if active_id not in {m.municipality_id for m in memberships}:
        active_id = None
    profile = UserOut.model_validate(user)
    # Operating the platform needs a password sign-in (see access.require_operator).
    profile.is_platform_operator = user.is_platform_operator and session_row.auth_method != "sso"
    return Me(
        user=profile,
        has_password=user.password_hash is not None,
        memberships=[MembershipOut.model_validate(m) for m in memberships],
        suspended_municipalities=[
            MunicipalityOut.model_validate(m.municipality)
            for m in every
            if m.municipality.is_suspended
        ],
        active_municipality_id=active_id,
        dashboards=[
            DashboardAccessOut(key=key, level=level.name.lower())
            for m in memberships
            if m.municipality_id == active_id
            for key, level in effective_levels(db, m).items()
        ],
    )


def start_session(
    db: Session, user: User, response: Response, auth_method: str = "password"
) -> SessionRow:
    """Open a session for a user who proved who they are, and set its cookie."""
    settings = get_settings()
    token, token_hash = new_token()
    session_row = SessionRow(
        token_hash=token_hash,
        user_id=user.id,
        auth_method=auth_method,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
    )
    memberships = _memberships(db, user, session_row)
    available = [m for m in memberships if not m.municipality.is_suspended]
    # With a single municipality to work in, it is the active one. A sole suspended one is
    # kept too: it is not active while suspended, and resuming it needs no new choice.
    only = available if available else memberships
    if len(only) == 1:
        session_row.active_municipality_id = only[0].municipality_id
    db.add(session_row)
    db.flush()
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=settings.cookie_secure,
        path="/",
    )
    return session_row


@router.post("/login")
def login(payload: LoginIn, response: Response, db: Db) -> Me:
    user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
    # Unknown emails and accounts without a password still pay for a verification.
    password_ok = verify_password(payload.password, user.password_hash if user else None)
    if user is None or not password_ok or not user.is_active:
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")
    return build_me(db, user, start_session(db, user, response))


@router.post("/logout", status_code=204)
def logout(response: Response, db: Db, session_row: CurrentSession) -> None:
    db.delete(session_row)
    response.delete_cookie(SESSION_COOKIE, path="/")


@router.get("/me")
def me(db: Db, user: CurrentUser, session_row: CurrentSession) -> Me:
    return build_me(db, user, session_row)


@router.post("/active-municipality")
def set_active_municipality(
    payload: ActiveMunicipalityIn, db: Db, user: CurrentUser, session_row: CurrentSession
) -> Me:
    membership = next(
        (
            m
            for m in _memberships(db, user, session_row)
            if m.municipality_id == payload.municipality_id
        ),
        None,
    )
    if membership is None:
        raise forbidden("You do not belong to this municipality.")
    if membership.municipality.is_suspended:
        raise municipality_suspended()
    session_row.active_municipality_id = payload.municipality_id
    db.flush()
    return build_me(db, user, session_row)


class PasswordChangeIn(BaseModel):
    current_password: str
    new_password: Password


def _check_current_password(user: User, password: str) -> None:
    if not verify_password(password, user.password_hash):
        raise ApiError(403, "invalid_credentials", "The current password is incorrect.")


@router.post("/password", status_code=204)
def change_password(
    payload: PasswordChangeIn, db: Db, user: CurrentUser, session_row: CurrentSession
) -> None:
    """Change the signed-in user's password and sign out their other sessions."""
    _check_current_password(user, payload.current_password)
    accounts.set_password(db, user, payload.new_password, keep_session_id=session_row.id)


class AccountIn(BaseModel):
    # Asked for every change, so an unattended open session cannot take over the account.
    # An account without a password (it signs in through single sign-on) has none to give.
    current_password: str | None = None
    full_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    phone: Phone = ""
    # Null or absent keeps the current password.
    new_password: Password | None = None


@router.put("/account")
def update_account(
    payload: AccountIn, db: Db, user: CurrentUser, session_row: CurrentSession
) -> Me:
    """Change the signed-in user's name, phone and, optionally, password.

    Nothing is saved unless the current password is right. A new password signs out the
    user's other sessions, as `change_password` does. An account without a password changes
    its name and phone freely, and gets a password only through a link sent to its address.
    """
    if user.password_hash is not None:
        _check_current_password(user, payload.current_password or "")
    elif payload.new_password is not None:
        raise validation_error(
            "An account without a password chooses one through the link sent by email."
        )
    user.full_name = payload.full_name
    user.phone = payload.phone
    if payload.new_password is not None:
        accounts.set_password(db, user, payload.new_password, keep_session_id=session_row.id)
    db.flush()
    return build_me(db, user, session_row)


class PasswordResetIn(BaseModel):
    email: Email


@router.post("/password-reset", status_code=204)
def request_password_reset(payload: PasswordResetIn, db: Db) -> None:
    """Email a link to choose a new password. Answers the same whether or not the email
    has an account."""
    accounts.request_password_reset(db, payload.email)


class TokenIn(BaseModel):
    token: str


class TokenOut(BaseModel):
    purpose: Literal["invitation", "password_reset"]
    email: str
    full_name: str


@router.post("/tokens/inspect")
def inspect_token(payload: TokenIn, db: Db) -> TokenOut:
    """What a link from an email is for, if it can still be used. Does not use it up."""
    token, user = accounts.inspect_token(db, payload.token)
    return TokenOut(purpose=token.purpose, email=user.email, full_name=user.full_name)


class RedeemIn(BaseModel):
    token: str
    password: Password


@router.post("/tokens/redeem", status_code=204)
def redeem_token(payload: RedeemIn, db: Db) -> None:
    """Set the password chosen through a link. Every session of the account is closed."""
    accounts.redeem_token(db, payload.token, payload.password)
