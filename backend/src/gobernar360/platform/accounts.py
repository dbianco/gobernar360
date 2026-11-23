"""Accounts by email: invitations, password recovery and the links they send.

A link carries a random token that works once, until it expires; only its SHA-256 is
stored. Whoever opens it chooses the account's password, so links only ever go to the
account's own address: nobody else, administrators included, learns or sets it.
"""

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select, text, update
from sqlalchemy.orm import Session

from gobernar360.core.config import get_settings
from gobernar360.core.errors import invalid_token, too_many_requests
from gobernar360.core.security import hash_password, hash_token, new_token
from gobernar360.platform import email_templates
from gobernar360.platform.models import (
    AccountToken,
    Membership,
    Municipality,
    PasswordResetRequest,
    User,
)
from gobernar360.platform.models import Session as SessionRow
from gobernar360.platform.texts import format_datetime

INVITATION = "invitation"
PASSWORD_RESET = "password_reset"
SET_PASSWORD_PATH = "/set-password"


def set_password(
    db: Session, user: User, password: str, keep_session_id: uuid.UUID | None = None
) -> None:
    """Give the account a new password and end its sessions, except `keep_session_id`."""
    user.password_hash = hash_password(password)
    sessions = delete(SessionRow).where(SessionRow.user_id == user.id)
    if keep_session_id is not None:
        sessions = sessions.where(SessionRow.id != keep_session_id)
    db.execute(sessions)
    # A link sent earlier must not be able to override the password just chosen.
    _revoke_tokens(db, user.id)


def _revoke_tokens(db: Session, user_id: uuid.UUID, purpose: str | None = None) -> None:
    revoke = (
        update(AccountToken)
        .where(AccountToken.user_id == user_id, AccountToken.used_at.is_(None))
        .values(used_at=datetime.now(UTC))
    )
    if purpose is not None:
        revoke = revoke.where(AccountToken.purpose == purpose)
    db.execute(revoke)


def _lifetime(purpose: str) -> timedelta:
    settings = get_settings()
    if purpose == INVITATION:
        return timedelta(hours=settings.invitation_ttl_hours)
    return timedelta(minutes=settings.password_reset_ttl_minutes)


def issue_token(db: Session, user: User, purpose: str) -> tuple[str, datetime]:
    """A new link token for the account. Earlier unused ones for the same purpose stop working.

    Returns the token, which is never stored, and when it expires.
    """
    _revoke_tokens(db, user.id, purpose)
    token, token_hash = new_token()
    expires_at = datetime.now(UTC) + _lifetime(purpose)
    db.add(
        AccountToken(user_id=user.id, purpose=purpose, token_hash=token_hash, expires_at=expires_at)
    )
    return token, expires_at


def token_link(token: str) -> str:
    # In the fragment, so the token never reaches a server log or a Referer header.
    return get_settings().app_link(f"{SET_PASSWORD_PATH}#{token}")


def _valid(token: str):
    return (
        AccountToken.token_hash == hash_token(token),
        AccountToken.used_at.is_(None),
        AccountToken.expires_at > datetime.now(UTC),
    )


def inspect_token(db: Session, token: str) -> tuple[AccountToken, User]:
    """The token and its account, if the link can still be used."""
    row = db.scalar(select(AccountToken).where(*_valid(token)))
    user = db.get(User, row.user_id) if row else None
    if row is None or user is None or not user.is_active:
        raise invalid_token()
    return row, user


def redeem_token(db: Session, token: str, password: str) -> User:
    """Set the password chosen through a link, which then stops working."""
    # Marking it used is the check: of two requests racing with the same token, the
    # second waits for the first's row lock and then no longer matches.
    user_id = db.scalar(
        update(AccountToken)
        .where(*_valid(token))
        .values(used_at=datetime.now(UTC))
        .returning(AccountToken.user_id)
    )
    user = db.get(User, user_id) if user_id else None
    if user is None or not user.is_active:
        raise invalid_token()
    set_password(db, user, password)
    return user


def send_invitation(db: Session, user: User, municipality: Municipality, inviter: str) -> None:
    token, expires_at = issue_token(db, user, INVITATION)
    email_templates.send(
        db,
        user.email,
        municipality.id,
        email_templates.INVITATION,
        name=user.full_name,
        inviter=inviter,
        municipality=municipality.name,
        link=token_link(token),
        expires=format_datetime(expires_at),
    )


def send_membership_notice(
    db: Session, user: User, municipality: Municipality, inviter: str
) -> None:
    """Tell the owner of an existing account they were given access to a municipality."""
    email_templates.send(
        db,
        user.email,
        municipality.id,
        email_templates.MEMBERSHIP_ADDED,
        name=user.full_name,
        inviter=inviter,
        municipality=municipality.name,
        link=get_settings().app_link("/login"),
    )


def _recovery_municipality(db: Session, user: User) -> uuid.UUID | None:
    """Whose version of the recovery email an account gets: its municipality's when it
    belongs to exactly one, the default one otherwise."""
    ids = db.scalars(select(Membership.municipality_id).where(Membership.user_id == user.id))
    ids = list(ids)
    return ids[0] if len(ids) == 1 else None


def request_password_reset(db: Session, email: str) -> None:
    """Email a recovery link if the address has an account.

    Everything the caller can observe is the same for known and unknown addresses,
    including the rate limit, which counts requests per address whether or not it exists.
    """
    settings = get_settings()
    email_hash = hash_token(email)
    # Serialises requests for one address, so concurrent ones cannot all pass the limit.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"), {"key": email_hash})
    window = timedelta(minutes=settings.password_reset_window_minutes)
    recent = db.scalar(
        select(func.count())
        .select_from(PasswordResetRequest)
        .where(
            PasswordResetRequest.email_hash == email_hash,
            PasswordResetRequest.created_at > func.now() - window,
        )
    )
    if recent >= settings.password_reset_limit:
        raise too_many_requests()
    db.execute(
        delete(PasswordResetRequest).where(PasswordResetRequest.created_at < func.now() - window)
    )
    db.add(PasswordResetRequest(email_hash=email_hash))

    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return
    token, expires_at = issue_token(db, user, PASSWORD_RESET)
    email_templates.send(
        db,
        user.email,
        _recovery_municipality(db, user),
        email_templates.PASSWORD_RESET,
        name=user.full_name,
        link=token_link(token),
        expires=format_datetime(expires_at),
    )
