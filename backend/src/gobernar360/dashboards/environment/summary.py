"""Where each variable stands in a year: its figure against the target, and how much was loaded."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import date
from decimal import Decimal

from fastapi import APIRouter
from sqlalchemy import select

from gobernar360.dashboards.environment.access import Viewer
from gobernar360.dashboards.environment.models import CATEGORIES, Value, Variable
from gobernar360.dashboards.environment.parameters_router import variables_query
from gobernar360.dashboards.environment.rules import (
    achievement,
    annual_value,
    expected_loads,
    target_met,
)
from gobernar360.dashboards.environment.schemas import (
    CategorySummary,
    SummaryOut,
    VariableOut,
    VariableSummary,
)
from gobernar360.dashboards.registry import SummaryIndicator
from gobernar360.platform.access import RequestContext
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today

router = APIRouter()


def compute_summary(
    variables: Sequence[Variable], values: Sequence[Value], year: int
) -> SummaryOut:
    """Aggregate already-loaded variables and their values of one year. Touches no database."""
    periods: dict[object, dict[int, Decimal]] = defaultdict(dict)
    for value in values:
        periods[value.variable_id][value.period] = value.value

    by_category: dict[str, list[VariableSummary]] = {category: [] for category in CATEGORIES}
    for variable in variables:
        loaded = periods.get(variable.id, {})
        figure = annual_value(variable.annual_aggregation, loaded)
        by_category[variable.subcategory.category].append(
            VariableSummary(
                variable=VariableOut.model_validate(variable),
                value=figure,
                loaded=len(loaded),
                expected=expected_loads(variable.frequency),
                achievement=achievement(variable.direction, figure, variable.target),
                target_met=target_met(variable.direction, figure, variable.target),
            )
        )

    rows = [row for category_rows in by_category.values() for row in category_rows]
    return SummaryOut(
        year=year,
        variable_count=len(rows),
        loaded=sum(row.loaded for row in rows),
        expected=sum(row.expected for row in rows),
        targets_met=sum(row.target_met is True for row in rows),
        targets_missed=sum(row.target_met is False for row in rows),
        categories=[
            CategorySummary(
                category=category,
                loaded=sum(row.loaded for row in category_rows),
                expected=sum(row.expected for row in category_rows),
                variables=category_rows,
            )
            for category, category_rows in by_category.items()
        ],
    )


def summary_of_year(ctx: RequestContext, year: int) -> SummaryOut:
    variables = ctx.db.scalars(variables_query()).all()
    values = ctx.db.scalars(select(Value).where(Value.year == year)).all()
    return compute_summary(variables, values, year)


@router.get("/summary")
def get_year_summary(ctx: Viewer, today: Today, year: Year | None = None) -> SummaryOut:
    return summary_of_year(ctx, year or today.year)


def get_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    """Indicators for the general overview, for the current year."""
    summary = summary_of_year(ctx, today.year)
    if summary.variable_count == 0:
        return []
    return [
        SummaryIndicator("environment.variables", summary.variable_count),
        SummaryIndicator(
            "environment.load_completion", round(summary.loaded / summary.expected, 4), "ratio"
        ),
        SummaryIndicator("environment.targets_met", summary.targets_met),
        SummaryIndicator("environment.targets_missed", summary.targets_missed),
    ]
