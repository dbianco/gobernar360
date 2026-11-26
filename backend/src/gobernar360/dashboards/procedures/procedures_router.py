"""Procedures and the requirements each one asks for.
Reading needs viewer access; loading data needs editor access."""

import uuid
from collections.abc import Sequence
from typing import Any, Literal

from fastapi import APIRouter
from sqlalchemy import func, select

from gobernar360.core.errors import cidi_level_in_person, conflict, not_found, validation_error
from gobernar360.dashboards.procedures.access import Editor, Viewer
from gobernar360.dashboards.procedures.digital import FULLY_DIGITAL
from gobernar360.dashboards.procedures.models import (
    Area,
    Procedure,
    ProcedureRequirement,
    Requirement,
)
from gobernar360.dashboards.procedures.schemas import (
    Channel,
    LinkIn,
    LinkOut,
    LinkPatch,
    ProcedureDetail,
    ProcedureIn,
    ProcedureOut,
    ProcedurePatch,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.listing import Page, PagingParams, SearchText, contains, page_of
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()

IN_PERSON = "in_person"


def _present(ctx: RequestContext, procedures: Sequence[Procedure]) -> list[dict[str, Any]]:
    """Procedures as response data, each with how many requirements it asks for and whether
    it can be done entirely from home."""
    counts = dict(
        ctx.db.execute(
            select(ProcedureRequirement.procedure_id, func.count())
            .where(ProcedureRequirement.procedure_id.in_([p.id for p in procedures]))
            .group_by(ProcedureRequirement.procedure_id)
        ).all()
    )
    digital = set(
        ctx.db.scalars(
            select(Procedure.id).where(Procedure.id.in_([p.id for p in procedures]), FULLY_DIGITAL)
        )
    )
    worked_out = {"requirement_count", "fully_digital"}
    fields = [name for name in ProcedureOut.model_fields if name not in worked_out]
    return [
        {name: getattr(procedure, name) for name in fields}
        | {
            "requirement_count": counts.get(procedure.id, 0),
            "fully_digital": procedure.id in digital,
        }
        for procedure in procedures
    ]


def _present_one(ctx: RequestContext, procedure: Procedure) -> dict[str, Any]:
    ctx.db.refresh(procedure)
    return _present(ctx, [procedure])[0]


@router.get("/procedures")
def list_procedures(
    ctx: Viewer,
    paging: PagingParams,
    q: SearchText = None,
    area_id: uuid.UUID | None = None,
    channel: Channel | None = None,
    cidi_level: Literal["1", "2", "3", "none"] | None = None,
    active: bool | None = None,
) -> Page[ProcedureOut]:
    query = select(Procedure).order_by(func.unaccent(func.lower(Procedure.name)), Procedure.id)
    if q and q.strip():
        query = query.where(contains(Procedure.name, q.strip()))
    if area_id is not None:
        query = query.where(Procedure.area_id == area_id)
    if channel is not None:
        query = query.where(Procedure.channel == channel)
    if cidi_level == "none":
        query = query.where(Procedure.cidi_level.is_(None))
    elif cidi_level is not None:
        query = query.where(Procedure.cidi_level == int(cidi_level))
    if active is not None:
        query = query.where(Procedure.is_active.is_(active))
    page = page_of(ctx, query, paging)
    return {"items": _present(ctx, page["items"]), "total": page["total"]}


def _check_cidi(channel: str, cidi_level: int | None) -> None:
    if channel == IN_PERSON and cidi_level is not None:
        raise cidi_level_in_person()


@router.post("/procedures", status_code=201)
def create_procedure(payload: ProcedureIn, ctx: Editor) -> ProcedureOut:
    resolve(ctx, Area, payload.area_id, "area_id")
    _check_cidi(payload.channel, payload.cidi_level)
    procedure = create_entity(ctx, Procedure(**payload.model_dump()), payload.model_dump())
    return _present_one(ctx, procedure)


@router.get("/procedures/{procedure_id}")
def get_procedure(procedure_id: uuid.UUID, ctx: Viewer) -> ProcedureDetail:
    procedure = get_or_404(ctx, Procedure, procedure_id)
    links = ctx.db.scalars(
        select(ProcedureRequirement)
        .join(Requirement, ProcedureRequirement.requirement_id == Requirement.id)
        .where(ProcedureRequirement.procedure_id == procedure.id)
        .order_by(func.unaccent(func.lower(Requirement.name)), ProcedureRequirement.id)
    ).all()
    return _present_one(ctx, procedure) | {"requirements": links}


@router.patch("/procedures/{procedure_id}")
def update_procedure(procedure_id: uuid.UUID, payload: ProcedurePatch, ctx: Editor) -> ProcedureOut:
    procedure = get_or_404(ctx, Procedure, procedure_id)
    changes = payload.model_dump(exclude_unset=True)
    if "area_id" in changes:
        resolve(ctx, Area, changes["area_id"], "area_id")
    channel = changes.get("channel", procedure.channel)
    if channel == IN_PERSON and "cidi_level" not in changes:
        # Nobody signs in to a procedure that stops being online.
        changes["cidi_level"] = None
    _check_cidi(channel, changes.get("cidi_level"))
    is_free = changes.get("is_free", procedure.is_free)
    if is_free and "cost" not in changes:
        # The price of a procedure that becomes free no longer applies.
        changes["cost"] = None
    if is_free and changes.get("cost") is not None:
        raise validation_error("A free procedure has no cost.")
    return _present_one(ctx, update_entity(ctx, procedure, changes))


@router.delete("/procedures/{procedure_id}", status_code=204)
def delete_procedure(procedure_id: uuid.UUID, ctx: Editor) -> None:
    """Its requirement links go with it; the requirements themselves stay in the list."""
    delete_entity(ctx, get_or_404(ctx, Procedure, procedure_id))


def _link_of(ctx: RequestContext, procedure_id: uuid.UUID, link_id: uuid.UUID):
    link = get_or_404(ctx, ProcedureRequirement, link_id)
    if link.procedure_id != procedure_id:
        raise not_found()
    return link


@router.post("/procedures/{procedure_id}/requirements", status_code=201)
def add_requirement(procedure_id: uuid.UUID, payload: LinkIn, ctx: Editor) -> LinkOut:
    procedure = get_or_404(ctx, Procedure, procedure_id)
    requirement = resolve(ctx, Requirement, payload.requirement_id, "requirement_id")
    already_asked = ctx.db.scalar(
        select(ProcedureRequirement.id).where(
            ProcedureRequirement.procedure_id == procedure.id,
            ProcedureRequirement.requirement_id == requirement.id,
        )
    )
    if already_asked:
        raise conflict("This procedure already asks for that requirement.")
    link = ProcedureRequirement(procedure_id=procedure.id, **payload.model_dump())
    create_entity(ctx, link, payload.model_dump() | {"procedure_id": procedure.id})
    ctx.db.refresh(link)
    return link


@router.patch("/procedures/{procedure_id}/requirements/{link_id}")
def update_requirement_link(
    procedure_id: uuid.UUID, link_id: uuid.UUID, payload: LinkPatch, ctx: Editor
) -> LinkOut:
    link = _link_of(ctx, procedure_id, link_id)
    update_entity(ctx, link, payload.model_dump(exclude_unset=True))
    ctx.db.refresh(link)
    return link


@router.delete("/procedures/{procedure_id}/requirements/{link_id}", status_code=204)
def remove_requirement(procedure_id: uuid.UUID, link_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, _link_of(ctx, procedure_id, link_id))
