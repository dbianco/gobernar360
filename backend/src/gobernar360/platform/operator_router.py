"""Platform operator: municipalities, their enabled dashboards and their users."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gobernar360.core.db import set_tenant
from gobernar360.core.errors import conflict, not_found, validation_error
from gobernar360.dashboards import registry
from gobernar360.platform import accounts, members
from gobernar360.platform.access import CurrentUser, Db, RequestContext, require_operator
from gobernar360.platform.audit import record_change
from gobernar360.platform.models import Municipality, MunicipalityDashboard, User
from gobernar360.platform.schemas import MunicipalityOut, Password

router = APIRouter(prefix="/platform", tags=["platform"], dependencies=[Depends(require_operator)])


MunicipalityKind = Literal["municipality", "commune"]


class MunicipalityIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    slug: Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=100)]
    kind: MunicipalityKind


class MunicipalityDetail(MunicipalityOut):
    dashboards: list[str]


class DashboardKeysIn(BaseModel):
    keys: list[str]


class MunicipalityPatch(BaseModel):
    """The slug identifies the municipality and cannot be changed."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)] = (
        None
    )
    kind: MunicipalityKind = None


class PasswordIn(BaseModel):
    password: Password


def _enabled_keys(db: Session, municipality_id: uuid.UUID) -> list[str]:
    return sorted(
        db.scalars(
            select(MunicipalityDashboard.dashboard_key).where(
                MunicipalityDashboard.municipality_id == municipality_id
            )
        )
    )


def _detail(db: Session, municipality: Municipality) -> MunicipalityDetail:
    return MunicipalityDetail(
        **MunicipalityOut.model_validate(municipality).model_dump(),
        dashboards=_enabled_keys(db, municipality.id),
    )


def _get_municipality(db: Session, municipality_id: uuid.UUID) -> Municipality:
    municipality = db.get(Municipality, municipality_id)
    if municipality is None:
        raise not_found("Municipality not found.")
    return municipality


@router.get("/municipalities")
def list_municipalities(db: Db) -> list[MunicipalityDetail]:
    municipalities = db.scalars(select(Municipality).order_by(Municipality.name))
    return [_detail(db, municipality) for municipality in municipalities]


@router.post("/municipalities", status_code=201)
def create_municipality(payload: MunicipalityIn, db: Db) -> MunicipalityDetail:
    if db.scalar(select(Municipality.id).where(Municipality.slug == payload.slug)):
        raise conflict("A municipality with this slug already exists.")
    municipality = Municipality(**payload.model_dump())
    db.add(municipality)
    db.flush()
    return _detail(db, municipality)


@router.get("/dashboards")
def list_registered_dashboards() -> list[str]:
    return sorted(module.key for module in registry.all_modules())


@router.put("/municipalities/{municipality_id}/dashboards")
def set_enabled_dashboards(
    municipality_id: uuid.UUID, payload: DashboardKeysIn, db: Db
) -> MunicipalityDetail:
    municipality = _get_municipality(db, municipality_id)
    unknown = sorted(key for key in payload.keys if registry.get_module(key) is None)
    if unknown:
        raise validation_error(f"Unknown dashboards: {', '.join(unknown)}.")
    db.execute(
        delete(MunicipalityDashboard).where(
            MunicipalityDashboard.municipality_id == municipality_id
        )
    )
    db.add_all(
        MunicipalityDashboard(municipality_id=municipality_id, dashboard_key=key)
        for key in set(payload.keys)
    )
    db.flush()
    return _detail(db, municipality)


@router.patch("/municipalities/{municipality_id}")
def update_municipality(
    municipality_id: uuid.UUID, payload: MunicipalityPatch, db: Db
) -> MunicipalityDetail:
    municipality = _get_municipality(db, municipality_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(municipality, field, value)
    db.flush()
    return _detail(db, municipality)


def get_operator_context(municipality_id: uuid.UUID, db: Db, user: CurrentUser) -> RequestContext:
    """The operator acting on the municipality named in the path, without being a member."""
    _get_municipality(db, municipality_id)
    # Scopes the transaction so the audit trail of the municipality can be written.
    set_tenant(db, municipality_id)
    return RequestContext(user=user, municipality_id=municipality_id, membership=None, db=db)


OperatorContext = Annotated[RequestContext, Depends(get_operator_context)]

router.include_router(
    members.build_router(get_operator_context),
    prefix="/municipalities/{municipality_id}",
)


@router.put("/municipalities/{municipality_id}/users/{membership_id}/password", status_code=204)
def set_member_password(
    membership_id: uuid.UUID, payload: PasswordIn, ctx: OperatorContext
) -> None:
    """Only the operator may do this: accounts are shared between municipalities, so a
    municipality administrator could otherwise take over someone else's account."""
    membership = members.get_membership(ctx, membership_id)
    accounts.set_password(ctx.db, ctx.db.get(User, membership.user_id), payload.password)
    record_change(ctx, "update", membership, {"password": "changed"})
    ctx.db.flush()
