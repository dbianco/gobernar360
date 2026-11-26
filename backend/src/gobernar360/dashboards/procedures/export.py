"""CSV downloads of the inventory and of the opportunities report."""

from fastapi import APIRouter, Response
from sqlalchemy import func, select

from gobernar360.dashboards.procedures.access import Viewer
from gobernar360.dashboards.procedures.models import (
    Procedure,
    ProcedureRequirement,
    Requirement,
)
from gobernar360.dashboards.procedures.summary import opportunities_of
from gobernar360.platform.csv_export import csv_response, plain_number, safe_text

router = APIRouter()

PROCEDURE_COLUMNS = (
    "name",
    "area",
    "audience",
    "channel",
    "url",
    "free",
    "cost",
    "duration_days",
    "annual_volume",
    "active",
    "requirements",
    "cidi_level",
)
LINK_COLUMNS = (
    "procedure",
    "area",
    "active",
    "requirement",
    "source",
    "source_level",
    "mandatory",
    "format",
    "note",
)
OPPORTUNITY_COLUMNS = ("source", "level", "area", "requirements", "procedures", "annual_volume")
BY_NAME = (func.unaccent(func.lower(Procedure.name)), Procedure.id)


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _blank(value: int | None) -> int | str:
    return "" if value is None else value


@router.get("/export/procedures.csv")
def export_procedures(ctx: Viewer) -> Response:
    count = func.count(ProcedureRequirement.id)
    found = ctx.db.execute(
        select(Procedure, count)
        .outerjoin(ProcedureRequirement, ProcedureRequirement.procedure_id == Procedure.id)
        .group_by(Procedure.id)
        .order_by(*BY_NAME)
    ).unique()
    rows = (
        (
            safe_text(procedure.name),
            safe_text(procedure.area.name),
            procedure.audience,
            procedure.channel,
            safe_text(procedure.url),
            _yes_no(procedure.is_free),
            plain_number(procedure.cost),
            _blank(procedure.duration_days),
            _blank(procedure.annual_volume),
            _yes_no(procedure.is_active),
            requirements,
            _blank(procedure.cidi_level),
        )
        for procedure, requirements in found
    )
    return csv_response("procedures.csv", PROCEDURE_COLUMNS, rows)


@router.get("/export/procedure-requirements.csv")
def export_procedure_requirements(ctx: Viewer) -> Response:
    found = ctx.db.execute(
        select(Procedure, ProcedureRequirement)
        .join(ProcedureRequirement, ProcedureRequirement.procedure_id == Procedure.id)
        .join(Requirement, ProcedureRequirement.requirement_id == Requirement.id)
        .order_by(*BY_NAME, func.unaccent(func.lower(Requirement.name)), ProcedureRequirement.id)
    ).unique()

    def row(procedure: Procedure, link: ProcedureRequirement) -> tuple[object, ...]:
        source = link.requirement.source
        return (
            safe_text(procedure.name),
            safe_text(procedure.area.name),
            _yes_no(procedure.is_active),
            safe_text(link.requirement.name),
            safe_text(source.name if source else ""),
            source.level if source else "",
            _yes_no(link.mandatory),
            link.format,
            safe_text(link.note),
        )

    return csv_response("procedure-requirements.csv", LINK_COLUMNS, (row(*pair) for pair in found))


@router.get("/export/opportunities.csv")
def export_opportunities(ctx: Viewer) -> Response:
    report = opportunities_of(ctx)
    rows = [
        (
            safe_text(row.source.name),
            row.source.level,
            safe_text(row.source.area.name if row.source.area else ""),
            row.requirements,
            row.procedures,
            row.annual_volume,
        )
        for row in report.sources
    ]
    rest = report.without_source
    if rest.requirements:
        # What people bring themselves, for comparison with what a source could provide.
        rows.append(("", "none", "", rest.requirements, rest.procedures, rest.annual_volume))
    return csv_response("procedures-opportunities.csv", OPPORTUNITY_COLUMNS, rows)
