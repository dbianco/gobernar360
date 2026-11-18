"""Sign-in, sign-out and the current user's profile."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.config import get_settings
from gobernar360.core.errors import ApiError, forbidden
from gobernar360.core.security import (
    DUMMY_PASSWORD_HASH,
    new_session_token,
    normalize_email,
    verify_password,
)
from gobernar360.platform.access import SESSION_COOKIE, CurrentSession, CurrentUser, Db
from gobernar360.platform.models import Membership, User
from gobernar360.platform.models import Session as SessionRow
from gobernar360.platform.schemas import Me, MembershipOut, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


class ActiveMunicipalityIn(BaseModel):
    municipality_id: uuid.UUID


def _memberships(db: Session, user: User) -> list[Membership]:
    return list(db.scalars(select(Membership).where(Membership.user_id == user.id)).unique())


def build_me(db: Session, user: User, session_row: SessionRow) -> Me:
    memberships = sorted(_memberships(db, user), key=lambda m: m.municipality.name)
    active_id = session_row.active_municipality_id
    # A membership removed after sign-in must not leave a stale active municipality.
    if active_id not in {m.municipality_id for m in memberships}:
        active_id = None
    return Me(
        user=UserOut.model_validate(user),
        memberships=[MembershipOut.model_validate(m) for m in memberships],
        active_municipality_id=active_id,
        dashboards=[],
    )


@router.post("/login")
def login(payload: LoginIn, response: Response, db: Db) -> Me:
    user = db.scalar(select(User).where(User.email == normalize_email(payload.email)))
    password_ok = verify_password(
        payload.password, user.password_hash if user else DUMMY_PASSWORD_HASH
    )
    if user is None or not password_ok or not user.is_active:
        raise ApiError(401, "invalid_credentials", "Email or password is incorrect.")

    settings = get_settings()
    memberships = _memberships(db, user)
    token, token_hash = new_session_token()
    session_row = SessionRow(
        token_hash=token_hash,
        user_id=user.id,
        active_municipality_id=memberships[0].municipality_id if len(memberships) == 1 else None,
        expires_at=datetime.now(UTC) + timedelta(hours=settings.session_ttl_hours),
    )
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
    return build_me(db, user, session_row)


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
    if payload.municipality_id not in {m.municipality_id for m in _memberships(db, user)}:
        raise forbidden("You do not belong to this municipality.")
    session_row.active_municipality_id = payload.municipality_id
    db.flush()
    return build_me(db, user, session_row)
