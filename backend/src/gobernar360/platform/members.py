"""Members of a municipality and their dashboard access.

The same routes serve the municipality's own administrator and the platform
operator; they differ only in where the municipality comes from, which is what
the context dependency passed to build_router() decides.
"""

import uuid
from collections.abc import Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, func, select

from gobernar360.core.errors import account_exists, conflict, not_found, validation_error
from gobernar360.core.security import hash_password
from gobernar360.platform.access import RequestContext, enabled_dashboard_keys
from gobernar360.platform.audit import record_change
from gobernar360.platform.models import DashboardGrant, Membership, User
from gobernar360.platform.models import Session as SessionRow
from gobernar360.platform.schemas import Email, FullName, GrantLevel, Password


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
    # What to do when the email already has an account. Only the operator may choose.
    existing_account: Literal["keep_password", "replace_password"] | None = None


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


def get_membership(ctx: RequestContext, membership_id: uuid.UUID) -> Membership:
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


def set_password(ctx: RequestContext, user: User, password: str) -> None:
    """Give the account a new password and end every session opened with the old one."""
    user.password_hash = hash_password(password)
    ctx.db.execute(delete(SessionRow).where(SessionRow.user_id == user.id))


def build_router(
    context: Callable[..., RequestContext], may_add_existing_accounts: bool = False
) -> APIRouter:
    """Member-management routes for whoever `context` lets through.

    Accounts are shared between municipalities, and whoever registered an email first
    chose its password. Attaching such an account to a municipality could therefore
    give a stranger access to it, so a municipality administrator cannot do it. With
    `may_add_existing_accounts` (the operator) the request must say whether the
    account keeps its password or gets the one in the request.
    """
    router = APIRouter()
    MemberContext = Annotated[RequestContext, Depends(context)]  # noqa: N806

    @router.get("/dashboards")
    def list_enabled_dashboards(ctx: MemberContext) -> list[str]:
        return sorted(enabled_dashboard_keys(ctx.db, ctx.municipality_id))

    @router.get("/users")
    def list_members(ctx: MemberContext) -> list[MemberOut]:
        memberships = ctx.db.scalars(
            select(Membership).where(Membership.municipality_id == ctx.municipality_id)
        ).unique()
        return sorted(
            (_out(ctx, m) for m in memberships), key=lambda member: member.user.full_name.lower()
        )

    @router.post("/users", status_code=201)
    def add_member(payload: MemberIn, ctx: MemberContext) -> MemberOut:
        _check_grants(ctx, payload.grants)
        password_replaced = False
        user = ctx.db.scalar(select(User).where(User.email == payload.email))
        if user is None:
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
        elif not may_add_existing_accounts or payload.existing_account is None:
            raise account_exists()
        elif payload.existing_account == "replace_password":
            set_password(ctx, user, payload.password)
            password_replaced = True

        membership = Membership(
            user_id=user.id, municipality_id=ctx.municipality_id, is_admin=payload.is_admin
        )
        _set_grants(ctx, membership, payload.grants)
        ctx.db.add(membership)
        ctx.db.flush()
        ctx.db.refresh(membership)
        changes = {"email": user.email, "is_admin": payload.is_admin, "grants": payload.grants}
        if password_replaced:
            changes["password"] = "replaced"
        record_change(ctx, "create", membership, changes)
        return _out(ctx, membership)

    @router.patch("/users/{membership_id}")
    def update_member(
        membership_id: uuid.UUID, payload: MemberPatch, ctx: MemberContext
    ) -> MemberOut:
        membership = get_membership(ctx, membership_id)
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
    def remove_member(membership_id: uuid.UUID, ctx: MemberContext) -> None:
        membership = get_membership(ctx, membership_id)
        _ensure_not_last_admin(ctx, membership)
        record_change(ctx, "delete", membership, {"email": membership.user.email})
        ctx.db.delete(membership)
        ctx.db.flush()

    return router
