"""Areas, sources and the municipality's single list of requirements.

Reading needs viewer access. Areas and sources are changed by dashboard admins;
requirements by editors, because whoever loads a procedure must be able to add
the ones it asks for.
"""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter
from sqlalchemy import func, select

from gobernar360.core.errors import validation_error
from gobernar360.dashboards.procedures.access import Admin, Editor, Viewer
from gobernar360.dashboards.procedures.models import (
    Area,
    ProcedureRequirement,
    Requirement,
    Source,
)
from gobernar360.dashboards.procedures.schemas import (
    NamedRef,
    NameIn,
    RequirementIn,
    RequirementOut,
    RequirementPatch,
    SourceIn,
    SourceOut,
    SourcePatch,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.listing import SearchText, contains
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


@router.get("/areas")
def list_areas(ctx: Viewer) -> list[NamedRef]:
    return ctx.db.scalars(select(Area).order_by(Area.name)).all()


@router.post("/areas", status_code=201)
def create_area(payload: NameIn, ctx: Admin) -> NamedRef:
    return create_entity(ctx, Area(name=payload.name), payload.model_dump())


@router.patch("/areas/{area_id}")
def rename_area(area_id: uuid.UUID, payload: NameIn, ctx: Admin) -> NamedRef:
    return update_entity(ctx, get_or_404(ctx, Area, area_id), payload.model_dump())


@router.delete("/areas/{area_id}", status_code=204)
def delete_area(area_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Area, area_id))


def _check_source_area(ctx: RequestContext, level: str, area_id: uuid.UUID | None) -> None:
    if area_id is None:
        return
    if level != "municipal":
        raise validation_error("Only a municipal source belongs to an area.")
    resolve(ctx, Area, area_id, "area_id")


@router.get("/sources")
def list_sources(ctx: Viewer) -> list[SourceOut]:
    return ctx.db.scalars(select(Source).order_by(Source.name)).all()


@router.post("/sources", status_code=201)
def create_source(payload: SourceIn, ctx: Admin) -> SourceOut:
    _check_source_area(ctx, payload.level, payload.area_id)
    source = create_entity(ctx, Source(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(source)
    return source


@router.patch("/sources/{source_id}")
def update_source(source_id: uuid.UUID, payload: SourcePatch, ctx: Admin) -> SourceOut:
    source = get_or_404(ctx, Source, source_id)
    changes = payload.model_dump(exclude_unset=True)
    level = changes.get("level", source.level)
    if level != "municipal" and "area_id" not in changes:
        # The area of a source that stops being municipal no longer applies.
        changes["area_id"] = None
    _check_source_area(ctx, level, changes.get("area_id", source.area_id))
    update_entity(ctx, source, changes)
    ctx.db.refresh(source)
    return source


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Source, source_id))


def present_requirements(
    ctx: RequestContext, requirements: Sequence[Requirement]
) -> list[RequirementOut]:
    """Requirements with how many procedures ask for each."""
    counts = dict(
        ctx.db.execute(
            select(ProcedureRequirement.requirement_id, func.count())
            .where(ProcedureRequirement.requirement_id.in_([r.id for r in requirements]))
            .group_by(ProcedureRequirement.requirement_id)
        ).all()
    )
    return [
        RequirementOut(
            id=requirement.id,
            name=requirement.name,
            description=requirement.description,
            source=requirement.source,
            procedure_count=counts.get(requirement.id, 0),
        )
        for requirement in requirements
    ]


def _present(ctx: RequestContext, requirement: Requirement) -> RequirementOut:
    ctx.db.refresh(requirement)
    return present_requirements(ctx, [requirement])[0]


@router.get("/requirements")
def list_requirements(ctx: Viewer, q: SearchText = None) -> list[RequirementOut]:
    query = select(Requirement).order_by(
        func.unaccent(func.lower(Requirement.name)), Requirement.id
    )
    if q and q.strip():
        query = query.where(contains(Requirement.name, q.strip()))
    return present_requirements(ctx, ctx.db.scalars(query).all())


@router.post("/requirements", status_code=201)
def create_requirement(payload: RequirementIn, ctx: Editor) -> RequirementOut:
    if payload.source_id is not None:
        resolve(ctx, Source, payload.source_id, "source_id")
    requirement = create_entity(ctx, Requirement(**payload.model_dump()), payload.model_dump())
    return _present(ctx, requirement)


@router.patch("/requirements/{requirement_id}")
def update_requirement(
    requirement_id: uuid.UUID, payload: RequirementPatch, ctx: Editor
) -> RequirementOut:
    requirement = get_or_404(ctx, Requirement, requirement_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("source_id") is not None:
        resolve(ctx, Source, changes["source_id"], "source_id")
    return _present(ctx, update_entity(ctx, requirement, changes))


@router.delete("/requirements/{requirement_id}", status_code=204)
def delete_requirement(requirement_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, get_or_404(ctx, Requirement, requirement_id))
