"""CSV downloads of actors, people and the assignments of one year."""

from fastapi import APIRouter, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from gobernar360.dashboards.economic.access import Viewer
from gobernar360.dashboards.economic.assignments_router import in_year
from gobernar360.dashboards.economic.models import Actor, Assignment, EconomicPerson
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today
from gobernar360.platform.csv_export import csv_response, safe_text
from gobernar360.platform.geo.export import LOCATION_COLUMNS, location_cells, places_of
from gobernar360.platform.models import Person

router = APIRouter()

ACTOR_COLUMNS = (
    "name",
    "type",
    "sector",
    "cuit",
    "address",
    "phone",
    "email",
    "employees",
    "notes",
    *LOCATION_COLUMNS,
)
PERSON_COLUMNS = (
    "last_name",
    "first_name",
    "dni",
    "birth_date",
    "phone",
    "email",
    "address",
    "neighborhood",
    "employment_status",
    "occupation",
)
ASSIGNMENT_COLUMNS = ("date", "tool", "category", "recipient_type", "recipient", "document", "note")


@router.get("/export/actors.csv")
def export_actors(ctx: Viewer) -> Response:
    actors = ctx.db.scalars(
        select(Actor).options(selectinload(Actor.zones)).order_by(Actor.name, Actor.id)
    ).all()
    places = places_of(ctx.db, Actor, [actor.id for actor in actors])
    rows = (
        (
            safe_text(actor.name),
            safe_text(actor.actor_type.name if actor.actor_type else ""),
            safe_text(actor.sector.name if actor.sector else ""),
            actor.cuit,
            safe_text(actor.address),
            safe_text(actor.phone),
            safe_text(actor.email),
            "" if actor.employee_count is None else actor.employee_count,
            safe_text(actor.notes),
            *location_cells(actor, places),
        )
        for actor in actors
    )
    return csv_response("economic-actors.csv", ACTOR_COLUMNS, rows)


@router.get("/export/people.csv")
def export_people(ctx: Viewer) -> Response:
    registered = ctx.db.scalars(
        select(EconomicPerson)
        .join(Person, EconomicPerson.person_id == Person.id)
        .order_by(Person.last_name, Person.first_name, EconomicPerson.id)
    )
    rows = (
        (
            safe_text(row.person.last_name),
            safe_text(row.person.first_name),
            row.person.dni or "",
            row.person.birth_date or "",
            safe_text(row.person.phone),
            safe_text(row.person.email),
            safe_text(row.person.address),
            safe_text(row.person.neighborhood),
            row.employment_status,
            safe_text(row.occupation),
        )
        for row in registered
    )
    return csv_response("economic-people.csv", PERSON_COLUMNS, rows)


def _recipient(assignment: Assignment) -> tuple[str, str, str]:
    if assignment.actor is not None:
        return "actor", assignment.actor.name, assignment.actor.cuit
    person = assignment.person.person
    return "person", person.full_name, person.dni or ""


@router.get("/export/assignments.csv")
def export_assignments(ctx: Viewer, today: Today, year: Year | None = None) -> Response:
    year = year or today.year
    assignments = ctx.db.scalars(
        select(Assignment).where(in_year(year)).order_by(Assignment.date, Assignment.id)
    ).unique()

    def row(assignment: Assignment) -> tuple[object, ...]:
        kind, name, document = _recipient(assignment)
        return (
            assignment.date,
            safe_text(assignment.tool.name),
            safe_text(assignment.tool.category.name),
            kind,
            safe_text(name),
            document,
            safe_text(assignment.note),
        )

    return csv_response(
        f"economic-assignments-{year}.csv", ASSIGNMENT_COLUMNS, map(row, assignments)
    )
