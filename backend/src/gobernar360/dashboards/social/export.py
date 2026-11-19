"""CSV downloads of people, households and the deliveries and interventions of one year."""

from fastapi import APIRouter, Response
from sqlalchemy import ScalarResult, func, select

from gobernar360.dashboards.social import deliveries_router, interventions_router
from gobernar360.dashboards.social.access import Viewer, reads_reserved_text
from gobernar360.dashboards.social.models import Delivery, Household, Intervention, SocialPerson
from gobernar360.platform.access import RequestContext
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today
from gobernar360.platform.csv_export import csv_response, safe_text
from gobernar360.platform.models import Person

router = APIRouter()

PERSON_COLUMNS = (
    "last_name",
    "first_name",
    "dni",
    "birth_date",
    "phone",
    "email",
    "address",
    "neighborhood",
    "household",
    "relationship",
)
HOUSEHOLD_COLUMNS = ("name", "address", "neighborhood", "members", "head")
DELIVERY_COLUMNS = (
    "date",
    "benefit",
    "category",
    "quantity",
    "person",
    "document",
    "household",
    "note",
)
INTERVENTION_COLUMNS = ("date", "type", "person", "document", "performed_by")


def _people(ctx: RequestContext) -> ScalarResult[SocialPerson]:
    return ctx.db.scalars(
        select(SocialPerson)
        .join(Person, SocialPerson.person_id == Person.id)
        .order_by(Person.last_name, Person.first_name, SocialPerson.id)
    )


@router.get("/export/people.csv")
def export_people(ctx: Viewer) -> Response:
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
            safe_text(row.household.name if row.household else ""),
            row.relationship or "",
        )
        for row in _people(ctx)
    )
    return csv_response("social-people.csv", PERSON_COLUMNS, rows)


@router.get("/export/households.csv")
def export_households(ctx: Viewer) -> Response:
    members: dict[object, int] = {}
    heads: dict[object, str] = {}
    for person in _people(ctx):
        if person.household_id is None:
            continue
        members[person.household_id] = members.get(person.household_id, 0) + 1
        if person.relationship == "head":
            heads[person.household_id] = person.full_name
    households = ctx.db.scalars(
        select(Household).order_by(func.unaccent(Household.name), Household.id)
    )
    rows = (
        (
            safe_text(household.name),
            safe_text(household.address),
            safe_text(household.neighborhood),
            members.get(household.id, 0),
            safe_text(heads.get(household.id, "")),
        )
        for household in households
    )
    return csv_response("social-households.csv", HOUSEHOLD_COLUMNS, rows)


@router.get("/export/deliveries.csv")
def export_deliveries(ctx: Viewer, today: Today, year: Year | None = None) -> Response:
    year = year or today.year
    deliveries = ctx.db.scalars(
        select(Delivery).where(deliveries_router.in_year(year)).order_by(Delivery.date, Delivery.id)
    ).unique()
    rows = (
        (
            delivery.date,
            safe_text(delivery.benefit.name),
            safe_text(delivery.benefit.category.name),
            delivery.quantity,
            safe_text(delivery.person.full_name),
            delivery.person.dni or "",
            safe_text(delivery.person.household.name if delivery.person.household else ""),
            safe_text(delivery.note),
        )
        for delivery in deliveries
    )
    return csv_response(f"social-deliveries-{year}.csv", DELIVERY_COLUMNS, rows)


@router.get("/export/interventions.csv")
def export_interventions(ctx: Viewer, today: Today, year: Year | None = None) -> Response:
    """The description is reserved text: the column exists only for those who may read it."""
    year = year or today.year
    with_text = reads_reserved_text(ctx)
    interventions = ctx.db.scalars(
        select(Intervention)
        .where(interventions_router.in_year(year))
        .order_by(Intervention.date, Intervention.id)
    ).unique()

    def row(intervention: Intervention) -> tuple[object, ...]:
        cells: tuple[object, ...] = (
            intervention.date,
            safe_text(intervention.intervention_type.name),
            safe_text(intervention.person.full_name),
            intervention.person.dni or "",
            safe_text(intervention.performed_by),
        )
        return (*cells, safe_text(intervention.description)) if with_text else cells

    columns = (*INTERVENTION_COLUMNS, "description") if with_text else INTERVENTION_COLUMNS
    return csv_response(f"social-interventions-{year}.csv", columns, map(row, interventions))
