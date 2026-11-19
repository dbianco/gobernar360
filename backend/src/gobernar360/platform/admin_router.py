"""Municipality administrator: members of the municipality and their dashboard access."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select

from gobernar360.core.errors import conflict, not_found, validation_error
from gobernar360.core.security import hash_password
from gobernar360.platform.access import (
    RequestContext,
    enabled_dashboard_keys,
    require_municipality_admin,
)
from gobernar360.platform.audit import record_change
from gobernar360.platform.models import DashboardGrant, Membership, User
from gobernar360.platform.schemas import Email, FullName, GrantLevel, Password

router = APIRouter(prefix="/admin", tags=["admin"])

AdminContext = Annotated[RequestContext, Depends(require_municipality_admin)]


class MemberUserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str


class MemberOut(BaseModel):
    membership_id: uuid.UUID
    user: MemberUserOut
    is_admin: bool
    grants: dict[str, str]


class MemberIn(BaseModel):
    email: Email
    full_name: FullName
    password: Password
    is_admin: bool = False
    grants: dict[str, GrantLevel] = {}


class MemberPatch(BaseModel):
    is_admin: bool | None = None
    grants: dict[str, GrantLevel] | None = None


def _out(ctx: RequestContext, membership: Membership) -> MemberOut:
    # Grants left over from a dashboard that was later disabled are not shown: the
    # client sends back the whole map on every edit, and they would be rejected.
    enabled = enabled_dashboard_keys(ctx.db, ctx.municipality_id)
    return MemberOut(
        membership_id=membership.id,
        user=MemberUserOut(
            id=membership.user.id, email=membership.user.email, full_name=membership.user.full_name
        ),
        is_admin=membership.is_admin,
        grants={g.dashboard_key: g.level for g in membership.grants if g.dashboard_key in enabled},
    )


def _get_membership(ctx: RequestContext, membership_id: uuid.UUID) -> Membership:
    membership = ctx.db.scalar(
        select(Membership).where(
            Membership.id == membership_id, Membership.municipality_id == ctx.municipality_id
        )
    )
    if membership is None:
        raise not_found("User not found in this municipality.")
    return membership


def _check_grants(ctx: RequestContext, grants: dict[str, str]) -> None:
    not_enabled = sorted(set(grants) - enabled_dashboard_keys(ctx.db, ctx.municipality_id))
    if not_enabled:
        raise validation_error(
            f"Dashboards not enabled for this municipality: {', '.join(not_enabled)}."
        )


def _set_grants(ctx: RequestContext, membership: Membership, grants: dict[str, str]) -> None:
    """Replace the member's grants on the enabled dashboards.

    Grants on dashboards that are currently disabled are invisible to the client, so
    they are kept: the member gets their access back if the dashboard is enabled again.
    """
    enabled = enabled_dashboard_keys(ctx.db, ctx.municipality_id)
    hidden = [grant for grant in membership.grants if grant.dashboard_key not in enabled]
    membership.grants = hidden + [
        DashboardGrant(dashboard_key=key, level=level) for key, level in grants.items()
    ]


def _ensure_not_last_admin(ctx: RequestContext, membership: Membership) -> None:
    if not membership.is_admin:
        return
    admin_count = ctx.db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.municipality_id == ctx.municipality_id, Membership.is_admin)
    )
    if admin_count <= 1:
        raise conflict("The municipality must keep at least one administrator.")


@router.get("/dashboards")
def list_enabled_dashboards(ctx: AdminContext) -> list[str]:
    return sorted(enabled_dashboard_keys(ctx.db, ctx.municipality_id))


@router.get("/users")
def list_members(ctx: AdminContext) -> list[MemberOut]:
    memberships = ctx.db.scalars(
        select(Membership).where(Membership.municipality_id == ctx.municipality_id)
    ).unique()
    return sorted(
        (_out(ctx, m) for m in memberships), key=lambda member: member.user.full_name.lower()
    )


@router.post("/users", status_code=201)
def add_member(payload: MemberIn, ctx: AdminContext) -> MemberOut:
    _check_grants(ctx, payload.grants)
    user = ctx.db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        # An account that already exists keeps its own name and password.
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
        ctx.db.add(user)
        ctx.db.flush()
    elif ctx.db.scalar(
        select(Membership.id).where(
            Membership.user_id == user.id, Membership.municipality_id == ctx.municipality_id
        )
    ):
        raise conflict("This user already belongs to the municipality.")

    membership = Membership(
        user_id=user.id, municipality_id=ctx.municipality_id, is_admin=payload.is_admin
    )
    _set_grants(ctx, membership, payload.grants)
    ctx.db.add(membership)
    ctx.db.flush()
    ctx.db.refresh(membership)
    record_change(
        ctx,
        "create",
        membership,
        {"email": user.email, "is_admin": payload.is_admin, "grants": payload.grants},
    )
    return _out(ctx, membership)


@router.patch("/users/{membership_id}")
def update_member(membership_id: uuid.UUID, payload: MemberPatch, ctx: AdminContext) -> MemberOut:
    membership = _get_membership(ctx, membership_id)
    if payload.is_admin is False:
        _ensure_not_last_admin(ctx, membership)
    if payload.grants is not None:
        _check_grants(ctx, payload.grants)
        _set_grants(ctx, membership, payload.grants)
    if payload.is_admin is not None:
        membership.is_admin = payload.is_admin
    ctx.db.flush()
    record_change(ctx, "update", membership, payload.model_dump(exclude_none=True))
    return _out(ctx, membership)


@router.delete("/users/{membership_id}", status_code=204)
def remove_member(membership_id: uuid.UUID, ctx: AdminContext) -> None:
    membership = _get_membership(ctx, membership_id)
    _ensure_not_last_admin(ctx, membership)
    record_change(ctx, "delete", membership, {"email": membership.user.email})
    ctx.db.delete(membership)
    ctx.db.flush()
