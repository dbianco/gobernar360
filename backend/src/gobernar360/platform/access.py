"""Who is making the request and what they may do."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import IntEnum
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.db import get_db, set_tenant
from gobernar360.core.errors import forbidden, municipality_suspended, not_authenticated
from gobernar360.core.security import hash_token
from gobernar360.dashboards import registry
from gobernar360.platform.models import Membership, MunicipalityDashboard, User
from gobernar360.platform.models import Session as SessionRow
from gobernar360.platform.municipality_settings import sso_municipality_ids

SESSION_COOKIE = "g360_session"

Db = Annotated[Session, Depends(get_db)]


def get_current_session(
    db: Db, token: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None
) -> SessionRow:
    if not token:
        raise not_authenticated()
    session_row = db.scalar(
        select(SessionRow).where(
            SessionRow.token_hash == hash_token(token),
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

SSO = "sso"


def reachable(
    db: Session, session_row: SessionRow, memberships: list[Membership]
) -> list[Membership]:
    """The memberships a session may use: all of them after a password sign-in; after
    single sign-on, only those of municipalities that allow it."""
    if session_row.auth_method != SSO:
        return memberships
    allowed = sso_municipality_ids(db)
    return [m for m in memberships if m.municipality_id in allowed]


class AccessLevel(IntEnum):
    NONE = 0
    VIEWER = 1
    EDITOR = 2
    ADMIN = 3


@dataclass
class RequestContext:
    """A signed-in member acting inside their active municipality.

    `db` is already scoped to that municipality by row-level security.
    `membership` is None when a platform operator manages the municipality from
    outside; such a context never reaches dashboard routes.
    `user` is None only in a system context (see `system_context`).
    """

    user: User | None
    municipality_id: uuid.UUID
    membership: Membership | None
    db: Session


def system_context(db: Session, municipality_id: uuid.UUID) -> RequestContext:
    """A context for work done outside a request, such as taking monthly snapshots.

    `db` must already be scoped to the municipality (`core.db.tenant_session`). There is no
    user, so it can only be handed to code that reads, like a dashboard's `get_summary`,
    never to the audited writes of `tenant_crud`.
    """
    return RequestContext(user=None, municipality_id=municipality_id, membership=None, db=db)


def get_context(db: Db, user: CurrentUser, session_row: CurrentSession) -> RequestContext:
    municipality_id = session_row.active_municipality_id
    if municipality_id is None:
        raise forbidden("No active municipality is selected.")
    # Looked up on every request so revoked access takes effect immediately.
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.municipality_id == municipality_id
        )
    )
    if membership is None or not reachable(db, session_row, [membership]):
        raise forbidden("You do not belong to this municipality.")
    # Checked on every request too, so a suspension cuts off sessions already signed in.
    if membership.municipality.is_suspended:
        raise municipality_suspended()
    set_tenant(db, municipality_id)
    return RequestContext(user=user, municipality_id=municipality_id, membership=membership, db=db)


Context = Annotated[RequestContext, Depends(get_context)]


def enabled_dashboard_keys(db: Session, municipality_id: uuid.UUID) -> set[str]:
    """Dashboards the operator enabled for the municipality and that are installed."""
    enabled = db.scalars(
        select(MunicipalityDashboard.dashboard_key).where(
            MunicipalityDashboard.municipality_id == municipality_id
        )
    )
    return {key for key in enabled if registry.get_module(key) is not None}


def effective_levels(db: Session, membership: Membership) -> dict[str, AccessLevel]:
    """Access level per enabled dashboard; dashboards without access are omitted."""
    grants = {grant.dashboard_key: AccessLevel[grant.level.upper()] for grant in membership.grants}
    levels: dict[str, AccessLevel] = {}
    for key in sorted(enabled_dashboard_keys(db, membership.municipality_id)):
        level = AccessLevel.ADMIN if membership.is_admin else grants.get(key, AccessLevel.NONE)
        if level > AccessLevel.NONE:
            levels[key] = level
    return levels


def effective_level(db: Session, membership: Membership, dashboard_key: str) -> AccessLevel:
    return effective_levels(db, membership).get(dashboard_key, AccessLevel.NONE)


def require_dashboard(key: str, level: AccessLevel) -> Callable[..., RequestContext]:
    """Dependency factory: the member needs at least `level` on dashboard `key`."""

    def dependency(ctx: Context) -> RequestContext:
        if effective_level(ctx.db, ctx.membership, key) < level:
            raise forbidden()
        return ctx

    return dependency


def require_operator(user: CurrentUser, session_row: CurrentSession) -> User:
    # Operating the platform takes the account's password, not another system's word.
    if not user.is_platform_operator or session_row.auth_method == SSO:
        raise forbidden()
    return user


def require_municipality_admin(ctx: Context) -> RequestContext:
    if not ctx.membership.is_admin:
        raise forbidden()
    return ctx
