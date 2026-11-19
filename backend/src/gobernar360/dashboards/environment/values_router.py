"""Values loaded per period, and the history of one variable."""

import uuid
from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Response
from sqlalchemy import select

from gobernar360.core.errors import validation_error
from gobernar360.dashboards.environment.access import Editor, Viewer
from gobernar360.dashboards.environment.models import WHOLE_YEAR, Value, Variable
from gobernar360.dashboards.environment.rules import MONTHLY, annual_value, expected_loads
from gobernar360.dashboards.environment.schemas import (
    MonthPoint,
    SeriesOut,
    ValueIn,
    ValueOut,
    YearPoint,
)
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


@router.get("/values")
def list_values(ctx: Viewer, year: Year, variable_id: uuid.UUID | None = None) -> list[ValueOut]:
    query = select(Value).where(Value.year == year).order_by(Value.variable_id, Value.period)
    if variable_id is not None:
        query = query.where(Value.variable_id == variable_id)
    return ctx.db.scalars(query).all()


@router.put("/values", response_model=ValueOut)
def set_value(payload: ValueIn, ctx: Editor):
    """Store the value of one period, replacing any previous one; null clears the period."""
    variable = resolve(ctx, Variable, payload.variable_id, "variable_id")
    is_month = payload.period != WHOLE_YEAR
    if is_month != (variable.frequency == MONTHLY):
        raise validation_error("period does not match the variable's frequency.")

    existing = ctx.db.scalar(
        select(Value).where(
            Value.variable_id == variable.id,
            Value.year == payload.year,
            Value.period == payload.period,
        )
    )
    if payload.value is None:
        if existing is not None:
            delete_entity(ctx, existing)
        return Response(status_code=204)
    if existing is None:
        return create_entity(ctx, Value(**payload.model_dump()), payload.model_dump())
    return update_entity(ctx, existing, {"value": payload.value})


@router.get("/variables/{variable_id}/series")
def get_series(
    variable_id: uuid.UUID, ctx: Viewer, today: Today, year: Year | None = None
) -> SeriesOut:
    """The months of one year, and the year's figure for every year that has values."""
    variable = get_or_404(ctx, Variable, variable_id)
    year = year or today.year
    by_year: dict[int, dict[int, Decimal]] = defaultdict(dict)
    for value in ctx.db.scalars(select(Value).where(Value.variable_id == variable_id)):
        by_year[value.year][value.period] = value.value

    monthly = []
    if variable.frequency == MONTHLY:
        months = by_year.get(year, {})
        monthly = [MonthPoint(period=month, value=months.get(month)) for month in range(1, 13)]
    annual = [
        YearPoint(
            year=loaded_year,
            value=annual_value(variable.annual_aggregation, periods),
            loaded=len(periods),
            expected=expected_loads(variable.frequency),
        )
        for loaded_year, periods in sorted(by_year.items())
    ]
    return SeriesOut(variable=variable, year=year, monthly=monthly, annual=annual)
