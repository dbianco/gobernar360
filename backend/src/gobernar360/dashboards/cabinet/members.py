"""Members of the municipality as attendees and owners of commitments."""

import uuid
from collections.abc import Iterable

from sqlalchemy import func, select

from gobernar360.core.errors import invalid_reference
from gobernar360.dashboards.cabinet.access import KEY
from gobernar360.platform.access import AccessLevel, RequestContext, effective_level
from gobernar360.platform.models import Membership, User


def _members(ctx: RequestContext):
    # Memberships are a platform table, without row-level security: filtered here.
    return (
        select(Membership)
        .join(User, User.id == Membership.user_id)
        .where(Membership.municipality_id == ctx.municipality_id, User.is_active)
        .order_by(func.unaccent(func.lower(User.full_name)), User.email)
    )


def list_members(ctx: RequestContext) -> list[tuple[User, bool]]:
    """Active members by name, and whether each has access to this dashboard."""
    return [
        (m.user, effective_level(ctx.db, m, KEY) >= AccessLevel.VIEWER)
        for m in ctx.db.scalars(_members(ctx)).unique()
    ]


def resolve_members(ctx: RequestContext, user_ids: Iterable[uuid.UUID], field: str) -> list[User]:
    """The members a request body refers to, in name order. Accounts are shared between
    municipalities, so an account that exists may still not be a member here."""
    wanted = set(user_ids)
    found = [
        m.user for m in ctx.db.scalars(_members(ctx).where(Membership.user_id.in_(wanted))).unique()
    ]
    if len(found) != len(wanted):
        raise invalid_reference(f"{field} does not reference a member of the municipality.")
    return found


def resolve_member(ctx: RequestContext, user_id: uuid.UUID, field: str) -> User:
    return resolve_members(ctx, [user_id], field)[0]
