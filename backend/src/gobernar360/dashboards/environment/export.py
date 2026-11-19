"""CSV download of the values loaded in one year."""

from fastapi import APIRouter, Response
from sqlalchemy import select

from gobernar360.dashboards.environment.access import Viewer
from gobernar360.dashboards.environment.models import WHOLE_YEAR, Subcategory, Value, Variable
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today
from gobernar360.platform.csv_export import csv_response, plain_number, safe_text

router = APIRouter()

COLUMNS = ("category", "subcategory", "variable", "unit", "frequency", "year", "period", "value")


@router.get("/export/values.csv")
def export_values(ctx: Viewer, today: Today, year: Year | None = None) -> Response:
    year = year or today.year
    query = (
        select(Value, Variable)
        .join(Variable, Value.variable_id == Variable.id)
        .join(Subcategory, Variable.subcategory_id == Subcategory.id)
        .where(Value.year == year)
        .order_by(Subcategory.category, Subcategory.name, Variable.name, Value.period)
    )
    rows = (
        (
            variable.subcategory.category,
            safe_text(variable.subcategory.name),
            safe_text(variable.name),
            safe_text(variable.unit),
            variable.frequency,
            value.year,
            "" if value.period == WHOLE_YEAR else value.period,
            plain_number(value.value),
        )
        for value, variable in ctx.db.execute(query)
    )
    return csv_response(f"environment-values-{year}.csv", COLUMNS, rows)
