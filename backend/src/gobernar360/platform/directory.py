"""The people of a municipality that use the platform, for choosing among them."""

import uuid
from collections.abc import Iterable

from fastapi import APIRouter
from sqlalchemy import func, select

from gobernar360.core.errors import invalid_reference
from gobernar360.platform.access import Context, RequestContext
from gobernar360.platform.api_types import OrmModel
from gobernar360.platform.models import Membership, User

router = APIRouter(tags=["members"])


class UserRef(OrmModel):
    id: uuid.UUID
    full_name: str


def _members(ctx: RequestContext):
    # Memberships are a platform table, without row-level security: filtered here.
    return (
        select(User)
        .join(Membership, Membership.user_id == User.id)
        .where(Membership.municipality_id == ctx.municipality_id, User.is_active)
        .order_by(func.unaccent(func.lower(User.full_name)), User.email)
    )


def resolve_members(ctx: RequestContext, user_ids: Iterable[uuid.UUID], field: str) -> list[User]:
    """The members a request body refers to, in name order. Accounts are shared between
    municipalities, so an account that exists may still not be a member here."""
    wanted = set(user_ids)
    found = list(ctx.db.scalars(_members(ctx).where(User.id.in_(wanted))))
    if len(found) != len(wanted):
        raise invalid_reference(f"{field} does not reference a member of the municipality.")
    return found


def resolve_member(ctx: RequestContext, user_id: uuid.UUID, field: str) -> User:
    return resolve_members(ctx, [user_id], field)[0]


@router.get("/members")
def list_members(ctx: Context) -> list[UserRef]:
    """Active members by name: whoever may be given a commitment or attend a meeting."""
    return [UserRef.model_validate(user) for user in ctx.db.scalars(_members(ctx))]
