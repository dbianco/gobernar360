"""Tools assigned to actors and to people.
Reading needs viewer access; loading data needs editor access."""

import uuid
from datetime import date

from fastapi import APIRouter
from sqlalchemy import ColumnElement, select

from gobernar360.core.errors import validation_error
from gobernar360.dashboards.economic.access import Editor, Viewer
from gobernar360.dashboards.economic.models import Actor, Assignment, EconomicPerson, Tool
from gobernar360.dashboards.economic.schemas import AssignmentIn, AssignmentOut, AssignmentPatch
from gobernar360.platform.api_types import Year
from gobernar360.platform.listing import Page, PagingParams, SearchText, every_word, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


def in_year(year: int) -> ColumnElement[bool]:
    return Assignment.date.between(date(year, 1, 1), date(year, 12, 31))


@router.get("/assignments")
def list_assignments(
    ctx: Viewer,
    paging: PagingParams,
    year: Year | None = None,
    tool_id: uuid.UUID | None = None,
    actor_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    q: SearchText = None,
) -> Page[AssignmentOut]:
    query = select(Assignment).order_by(Assignment.date.desc(), Assignment.id)
    if q and q.strip():
        # The tool, or who received it: an actor, or a person by name or document.
        query = (
            query.join(Tool, Assignment.tool_id == Tool.id)
            .outerjoin(Actor, Assignment.actor_id == Actor.id)
            .outerjoin(EconomicPerson, Assignment.person_id == EconomicPerson.id)
            .outerjoin(Person, EconomicPerson.person_id == Person.id)
            .where(
                *every_word(
                    q,
                    Tool.name,
                    Actor.name,
                    Person.first_name,
                    Person.last_name,
                    document=Person.dni,
                )
            )
        )
    if year is not None:
        query = query.where(in_year(year))
    for column, value in (
        (Assignment.tool_id, tool_id),
        (Assignment.actor_id, actor_id),
        (Assignment.person_id, person_id),
    ):
        if value is not None:
            query = query.where(column == value)
    return page_of(ctx, query, paging)


@router.post("/assignments", status_code=201)
def create_assignment(payload: AssignmentIn, ctx: Editor) -> AssignmentOut:
    tool = resolve(ctx, Tool, payload.tool_id, "tool_id")
    if payload.actor_id is not None:
        resolve(ctx, Actor, payload.actor_id, "actor_id")
        recipient = "actors"
    else:
        resolve(ctx, EconomicPerson, payload.person_id, "person_id")
        recipient = "people"
    if tool.audience not in (recipient, "both"):
        raise validation_error(f"This tool is not offered to {recipient}.")
    assignment = create_entity(ctx, Assignment(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(assignment)
    return assignment


@router.patch("/assignments/{assignment_id}")
def update_assignment(
    assignment_id: uuid.UUID, payload: AssignmentPatch, ctx: Editor
) -> AssignmentOut:
    assignment = get_or_404(ctx, Assignment, assignment_id)
    update_entity(ctx, assignment, payload.model_dump(exclude_unset=True))
    ctx.db.refresh(assignment)
    return assignment


@router.delete("/assignments/{assignment_id}", status_code=204)
def delete_assignment(assignment_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, get_or_404(ctx, Assignment, assignment_id))
