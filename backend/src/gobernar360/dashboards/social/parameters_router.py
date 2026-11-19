"""The municipality's own catalogs: benefit categories, benefits and intervention types.
Reading needs viewer access; changing them needs dashboard admin."""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from gobernar360.dashboards.social.access import Admin, Viewer
from gobernar360.dashboards.social.models import Benefit, BenefitCategory, InterventionType
from gobernar360.dashboards.social.schemas import (
    BenefitIn,
    BenefitOut,
    BenefitPatch,
    NamedRef,
    NameIn,
)
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


def _add_name_catalog(path: str, model: type[Any]) -> None:
    """Routes of a list whose items only have a name."""

    @router.get(path, name=f"list {path}")
    def list_items(ctx: Viewer) -> list[NamedRef]:
        return ctx.db.scalars(select(model).order_by(model.name)).all()

    @router.post(path, status_code=201, name=f"create {path}")
    def create_item(payload: NameIn, ctx: Admin) -> NamedRef:
        return create_entity(ctx, model(name=payload.name), payload.model_dump())

    @router.patch(f"{path}/{{item_id}}", name=f"rename {path}")
    def rename_item(item_id: uuid.UUID, payload: NameIn, ctx: Admin) -> NamedRef:
        return update_entity(ctx, get_or_404(ctx, model, item_id), payload.model_dump())

    @router.delete(f"{path}/{{item_id}}", status_code=204, name=f"delete {path}")
    def delete_item(item_id: uuid.UUID, ctx: Admin) -> None:
        delete_entity(ctx, get_or_404(ctx, model, item_id))


_add_name_catalog("/benefit-categories", BenefitCategory)
_add_name_catalog("/intervention-types", InterventionType)


@router.get("/benefits")
def list_benefits(ctx: Viewer) -> list[BenefitOut]:
    return ctx.db.scalars(select(Benefit).order_by(Benefit.name)).all()


@router.post("/benefits", status_code=201)
def create_benefit(payload: BenefitIn, ctx: Admin) -> BenefitOut:
    resolve(ctx, BenefitCategory, payload.category_id, "category_id")
    benefit = create_entity(ctx, Benefit(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(benefit)
    return benefit


@router.patch("/benefits/{benefit_id}")
def update_benefit(benefit_id: uuid.UUID, payload: BenefitPatch, ctx: Admin) -> BenefitOut:
    benefit = get_or_404(ctx, Benefit, benefit_id)
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes:
        resolve(ctx, BenefitCategory, changes["category_id"], "category_id")
    update_entity(ctx, benefit, changes)
    ctx.db.refresh(benefit)
    return benefit


@router.delete("/benefits/{benefit_id}", status_code=204)
def delete_benefit(benefit_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Benefit, benefit_id))
