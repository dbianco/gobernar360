"""Platform operator: municipalities, their enabled dashboards and first administrators."""

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from gobernar360.core.errors import conflict, not_found, validation_error
from gobernar360.core.security import hash_password
from gobernar360.dashboards import registry
from gobernar360.platform.access import Db, require_operator
from gobernar360.platform.models import Membership, Municipality, MunicipalityDashboard, User
from gobernar360.platform.schemas import Email, FullName, MunicipalityOut, Password, UserOut

router = APIRouter(prefix="/platform", tags=["platform"], dependencies=[Depends(require_operator)])


class MunicipalityIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=200)]
    slug: Annotated[str, Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=100)]
    kind: Literal["municipality", "commune"]


class MunicipalityDetail(MunicipalityOut):
    dashboards: list[str]


class DashboardKeysIn(BaseModel):
    keys: list[str]


class AdminIn(BaseModel):
    email: Email
    full_name: FullName
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


@router.post("/municipalities/{municipality_id}/admins", status_code=201)
def create_municipality_admin(municipality_id: uuid.UUID, payload: AdminIn, db: Db) -> UserOut:
    _get_municipality(db, municipality_id)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        # An existing account keeps its own name and password.
        user = User(
            email=payload.email,
            full_name=payload.full_name,
            password_hash=hash_password(payload.password),
        )
        db.add(user)
        db.flush()
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.municipality_id == municipality_id
        )
    )
    if membership is None:
        db.add(Membership(user_id=user.id, municipality_id=municipality_id, is_admin=True))
    else:
        membership.is_admin = True
    db.flush()
    return UserOut.model_validate(user)
