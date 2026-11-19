"""The municipality's own lists (actor types, sectors, tool categories and subcategories)
and the tools it offers. Reading needs viewer access; changing them needs dashboard admin."""

import uuid
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from gobernar360.core.errors import invalid_reference
from gobernar360.dashboards.economic.access import Admin, Viewer
from gobernar360.dashboards.economic.models import (
    ActorType,
    Sector,
    Tool,
    ToolCategory,
    ToolSubcategory,
)
from gobernar360.dashboards.economic.schemas import (
    NamedRef,
    NameIn,
    SubcategoryIn,
    SubcategoryOut,
    ToolIn,
    ToolOut,
    ToolPatch,
)
from gobernar360.platform.access import RequestContext
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


_add_name_catalog("/actor-types", ActorType)
_add_name_catalog("/sectors", Sector)
_add_name_catalog("/tool-categories", ToolCategory)


@router.get("/tool-subcategories")
def list_subcategories(ctx: Viewer) -> list[SubcategoryOut]:
    return ctx.db.scalars(select(ToolSubcategory).order_by(ToolSubcategory.name)).all()


@router.post("/tool-subcategories", status_code=201)
def create_subcategory(payload: SubcategoryIn, ctx: Admin) -> SubcategoryOut:
    resolve(ctx, ToolCategory, payload.category_id, "category_id")
    return create_entity(ctx, ToolSubcategory(**payload.model_dump()), payload.model_dump())


@router.patch("/tool-subcategories/{subcategory_id}")
def rename_subcategory(subcategory_id: uuid.UUID, payload: NameIn, ctx: Admin) -> SubcategoryOut:
    subcategory = get_or_404(ctx, ToolSubcategory, subcategory_id)
    return update_entity(ctx, subcategory, payload.model_dump())


@router.delete("/tool-subcategories/{subcategory_id}", status_code=204)
def delete_subcategory(subcategory_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, ToolSubcategory, subcategory_id))


def _check_tool_references(
    ctx: RequestContext, category_id: uuid.UUID, subcategory_id: uuid.UUID | None
) -> None:
    resolve(ctx, ToolCategory, category_id, "category_id")
    if subcategory_id is None:
        return
    subcategory = resolve(ctx, ToolSubcategory, subcategory_id, "subcategory_id")
    if subcategory.category_id != category_id:
        raise invalid_reference("subcategory_id does not belong to the tool's category.")


@router.get("/tools")
def list_tools(ctx: Viewer) -> list[ToolOut]:
    return ctx.db.scalars(select(Tool).order_by(Tool.name)).all()


@router.post("/tools", status_code=201)
def create_tool(payload: ToolIn, ctx: Admin) -> ToolOut:
    _check_tool_references(ctx, payload.category_id, payload.subcategory_id)
    tool = create_entity(ctx, Tool(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(tool)
    return tool


@router.patch("/tools/{tool_id}")
def update_tool(tool_id: uuid.UUID, payload: ToolPatch, ctx: Admin) -> ToolOut:
    tool = get_or_404(ctx, Tool, tool_id)
    changes = payload.model_dump(exclude_unset=True)
    if "category_id" in changes and "subcategory_id" not in changes:
        # A subcategory of the previous category makes no sense under the new one.
        if changes["category_id"] != tool.category_id:
            changes["subcategory_id"] = None
    _check_tool_references(
        ctx,
        changes.get("category_id", tool.category_id),
        changes.get("subcategory_id", tool.subcategory_id),
    )
    update_entity(ctx, tool, changes)
    ctx.db.refresh(tool)
    return tool


@router.delete("/tools/{tool_id}", status_code=204)
def delete_tool(tool_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Tool, tool_id))
