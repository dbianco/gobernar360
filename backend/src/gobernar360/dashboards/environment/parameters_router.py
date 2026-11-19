"""What the municipality measures: subcategories and variables inside the fixed categories.
Reading needs viewer access; changing them needs dashboard admin."""

import uuid

from fastapi import APIRouter
from sqlalchemy import Select, select

from gobernar360.dashboards.environment.access import Admin, Viewer
from gobernar360.dashboards.environment.models import Subcategory, Variable
from gobernar360.dashboards.environment.schemas import (
    Category,
    SubcategoryIn,
    SubcategoryOut,
    SubcategoryPatch,
    VariableIn,
    VariableOut,
    VariablePatch,
)
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


@router.get("/subcategories")
def list_subcategories(ctx: Viewer, category: Category | None = None) -> list[SubcategoryOut]:
    query = select(Subcategory).order_by(Subcategory.name)
    if category is not None:
        query = query.where(Subcategory.category == category)
    return ctx.db.scalars(query).all()


@router.post("/subcategories", status_code=201)
def create_subcategory(payload: SubcategoryIn, ctx: Admin) -> SubcategoryOut:
    return create_entity(ctx, Subcategory(**payload.model_dump()), payload.model_dump())


@router.patch("/subcategories/{subcategory_id}")
def update_subcategory(
    subcategory_id: uuid.UUID, payload: SubcategoryPatch, ctx: Admin
) -> SubcategoryOut:
    subcategory = get_or_404(ctx, Subcategory, subcategory_id)
    return update_entity(ctx, subcategory, payload.model_dump())


@router.delete("/subcategories/{subcategory_id}", status_code=204)
def delete_subcategory(subcategory_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Subcategory, subcategory_id))


def variables_query(
    category: str | None = None, subcategory_id: uuid.UUID | None = None
) -> Select[tuple[Variable]]:
    query = (
        select(Variable)
        .join(Subcategory, Variable.subcategory_id == Subcategory.id)
        .order_by(Subcategory.name, Variable.name)
    )
    if category is not None:
        query = query.where(Subcategory.category == category)
    if subcategory_id is not None:
        query = query.where(Variable.subcategory_id == subcategory_id)
    return query


@router.get("/variables")
def list_variables(
    ctx: Viewer, category: Category | None = None, subcategory_id: uuid.UUID | None = None
) -> list[VariableOut]:
    return ctx.db.scalars(variables_query(category, subcategory_id)).all()


@router.post("/variables", status_code=201)
def create_variable(payload: VariableIn, ctx: Admin) -> VariableOut:
    resolve(ctx, Subcategory, payload.subcategory_id, "subcategory_id")
    variable = create_entity(ctx, Variable(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(variable)
    return variable


@router.patch("/variables/{variable_id}")
def update_variable(variable_id: uuid.UUID, payload: VariablePatch, ctx: Admin) -> VariableOut:
    variable = get_or_404(ctx, Variable, variable_id)
    changes = payload.model_dump(exclude_unset=True)
    if "subcategory_id" in changes:
        resolve(ctx, Subcategory, changes["subcategory_id"], "subcategory_id")
    update_entity(ctx, variable, changes)
    ctx.db.refresh(variable)
    return variable


@router.delete("/variables/{variable_id}", status_code=204)
def delete_variable(variable_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Variable, variable_id))
