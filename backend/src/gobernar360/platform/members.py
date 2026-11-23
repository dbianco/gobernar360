"""Members of a municipality and their dashboard access.

The same routes serve the municipality's own administrator and the platform
operator; they differ only in where the municipality comes from, which is what
the context dependency passed to build_router() decides.

Nobody types a password for someone else. Adding a new email creates its account and
emails it an invitation link to choose one. Accounts are shared between municipalities,
so adding an email that already has an account only adds the membership and emails a
notice; the answer is the same either way, so whoever adds someone learns nothing about
an account that existed before and gets no way into it.

Members can also be added or updated from a CSV file (see members_csv): the last row
for an email decides that person's access, whether it came in this file or an earlier one.
"""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from gobernar360.core.errors import conflict, not_found, validation_error
from gobernar360.dashboards import registry
from gobernar360.platform import accounts, members_csv
from gobernar360.platform.access import RequestContext, enabled_dashboard_keys
from gobernar360.platform.audit import record_change
from gobernar360.platform.csv_export import csv_response
from gobernar360.platform.listing import Page, PagingParams, SearchText, every_word, page_of
from gobernar360.platform.models import DashboardGrant, Membership, Municipality, User
from gobernar360.platform.schemas import Email, FullName, GrantLevel
from gobernar360.platform.texts import text


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
    # Used only when the email has no account yet.
    full_name: FullName
    is_admin: bool = False
    grants: dict[str, GrantLevel] = {}


class MemberPatch(BaseModel):
    is_admin: bool | None = None
    grants: dict[str, GrantLevel] | None = None


class ImportIn(BaseModel):
    # The file's text; the browser decodes it (UTF-8, or Windows-1252 from older Excel).
    csv: Annotated[str, Field(max_length=1_000_000)]


class ImportOut(BaseModel):
    created: int
    updated: int
    unchanged: int


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


def _admin_count(ctx: RequestContext) -> int:
    return ctx.db.scalar(
        select(func.count())
        .select_from(Membership)
        .where(Membership.municipality_id == ctx.municipality_id, Membership.is_admin)
    )


def _ensure_not_last_admin(ctx: RequestContext, membership: Membership) -> None:
    if membership.is_admin and _admin_count(ctx) <= 1:
        raise conflict("The municipality must keep at least one administrator.")


def _visible_grants(ctx: RequestContext, membership: Membership) -> dict[str, str]:
    enabled = enabled_dashboard_keys(ctx.db, ctx.municipality_id)
    return {g.dashboard_key: g.level for g in membership.grants if g.dashboard_key in enabled}


def _add_member(
    ctx: RequestContext, email: str, full_name: str, is_admin: bool, grants: dict[str, str]
) -> Membership:
    """Add the email to the municipality, creating its account if needed, and email it."""
    user = ctx.db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, full_name=full_name, password_hash=None)
        ctx.db.add(user)
        ctx.db.flush()
    elif ctx.db.scalar(
        select(Membership.id).where(
            Membership.user_id == user.id, Membership.municipality_id == ctx.municipality_id
        )
    ):
        raise conflict("This user already belongs to the municipality.")

    membership = Membership(user_id=user.id, municipality_id=ctx.municipality_id, is_admin=is_admin)
    _set_grants(ctx, membership, grants)
    ctx.db.add(membership)
    ctx.db.flush()
    ctx.db.refresh(membership)
    record_change(
        ctx, "create", membership, {"email": user.email, "is_admin": is_admin, "grants": grants}
    )
    _invite(ctx, user)
    return membership


def _import(ctx: RequestContext, rows: list[members_csv.MemberRow]) -> ImportOut:
    """Apply the rows: add new members, update the access of existing ones."""
    result = ImportOut(created=0, updated=0, unchanged=0)
    had_admin = _admin_count(ctx) > 0
    for row in rows:
        membership = ctx.db.scalar(
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(User.email == row.email, Membership.municipality_id == ctx.municipality_id)
        )
        if membership is None:
            grants = {key: level for key, level in row.grants.items() if level}
            _add_member(ctx, row.email, row.full_name, bool(row.is_admin), grants)
            result.created += 1
            continue
        current = _visible_grants(ctx, membership)
        grants = dict(current)
        for key, level in row.grants.items():
            if level:
                grants[key] = level
            else:
                grants.pop(key, None)
        is_admin = membership.is_admin if row.is_admin is None else row.is_admin
        if grants == current and is_admin == membership.is_admin:
            result.unchanged += 1
            continue
        _set_grants(ctx, membership, grants)
        membership.is_admin = is_admin
        ctx.db.flush()
        record_change(
            ctx, "update", membership, {"is_admin": is_admin, "grants": grants, "source": "csv"}
        )
        result.updated += 1
    # Checked once at the end: a file may hand the role from one person to another. A
    # municipality that had no administrator yet (the operator is filling it) may stay so.
    if had_admin and _admin_count(ctx) == 0:
        raise conflict("The municipality must keep at least one administrator.")
    return result


def _invite(ctx: RequestContext, user: User) -> None:
    """Email the account a way in to the municipality: a link to choose its password
    while it has none, otherwise a notice."""
    if not user.is_active:
        return
    municipality = ctx.db.get(Municipality, ctx.municipality_id)
    if user.password_hash is None:
        # Never signed in: the link goes to the owner of the email, whoever invites them.
        accounts.send_invitation(ctx.db, user, municipality, ctx.user.full_name)
    else:
        accounts.send_membership_notice(ctx.db, user, municipality, ctx.user.full_name)


def build_router(context: Callable[..., RequestContext]) -> APIRouter:
    """Member-management routes for whoever `context` lets through."""
    # These two lines run once, while the routers are imported, where mutation testing
    # cannot reach them; every route built here is exercised through both routers.
    router = APIRouter()  # pragma: no mutate
    MemberContext = Annotated[RequestContext, Depends(context)]  # noqa: N806  # pragma: no mutate

    @router.get("/dashboards")
    def list_enabled_dashboards(ctx: MemberContext) -> list[str]:
        return sorted(enabled_dashboard_keys(ctx.db, ctx.municipality_id))

    @router.get("/users")
    def list_members(
        ctx: MemberContext, paging: PagingParams, q: SearchText = None
    ) -> Page[MemberOut]:
        """One page of members, by name; `q` searches names and emails."""
        query = (
            select(Membership)
            .join(User, User.id == Membership.user_id)
            .where(Membership.municipality_id == ctx.municipality_id)
            .where(*every_word(q, User.full_name, User.email))
            .order_by(func.lower(User.full_name), User.email, Membership.id)
        )
        page = page_of(ctx, query, paging)
        return Page[MemberOut](
            items=[_out(ctx, membership) for membership in page["items"]], total=page["total"]
        )

    @router.post("/users", status_code=201)
    def add_member(payload: MemberIn, ctx: MemberContext) -> MemberOut:
        _check_grants(ctx, payload.grants)
        membership = _add_member(
            ctx, payload.email, payload.full_name, payload.is_admin, payload.grants
        )
        return _out(ctx, membership)

    @router.get("/users/import-template.csv")
    def import_template(ctx: MemberContext) -> Response:
        """An example file to fill in: the header and two people."""
        header, rows = members_csv.template(
            sorted(enabled_dashboard_keys(ctx.db, ctx.municipality_id))
        )
        return csv_response(text("membersCsv.filename"), header, rows)

    @router.post("/users/import")
    def import_members(payload: ImportIn, ctx: MemberContext) -> ImportOut:
        """Add or update members from a CSV file; nothing changes if any row is wrong."""
        rows = members_csv.parse(
            payload.csv,
            sorted(enabled_dashboard_keys(ctx.db, ctx.municipality_id)),
            {module.key for module in registry.all_modules()},
        )
        return _import(ctx, rows)

    @router.post("/users/{membership_id}/invitation", status_code=204)
    def resend_invitation(membership_id: uuid.UUID, ctx: MemberContext) -> None:
        """A new invitation link, for someone who has not chosen a password yet.

        Answers the same for everyone; an account that already has a password gets no
        email, since its owner can sign in or recover it themselves.
        """
        user = get_membership(ctx, membership_id).user
        if user.password_hash is None:
            _invite(ctx, user)

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
