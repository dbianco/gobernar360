"""Who is making the request and what they may do."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.db import get_db
from gobernar360.core.errors import not_authenticated
from gobernar360.core.security import hash_session_token
from gobernar360.platform.models import Session as SessionRow
from gobernar360.platform.models import User

SESSION_COOKIE = "g360_session"

Db = Annotated[Session, Depends(get_db)]


def get_current_session(
    db: Db, token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None
) -> SessionRow:
    if not token:
        raise not_authenticated()
    session_row = db.scalar(
        select(SessionRow).where(
            SessionRow.token_hash == hash_session_token(token),
            SessionRow.expires_at > datetime.now(UTC),
        )
    )
    if session_row is None:
        raise not_authenticated()
    return session_row


CurrentSession = Annotated[SessionRow, Depends(get_current_session)]


def get_current_user(db: Db, session_row: CurrentSession) -> User:
    user = db.get(User, session_row.user_id)
    if user is None or not user.is_active:
        raise not_authenticated()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
