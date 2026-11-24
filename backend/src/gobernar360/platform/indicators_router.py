"""A dashboard's headline indicators over time and their targets: read by its viewers,
targets set by its administrators. Works for any registered dashboard."""

from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Path, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from gobernar360.core.errors import forbidden, not_found
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule, IndicatorDefinition
from gobernar360.platform import indicators
from gobernar360.platform.access import AccessLevel, Context, RequestContext, effective_level
from gobernar360.platform.api_types import Year
from gobernar360.platform.clock import Today
from gobernar360.platform.indicators import IndicatorEvolution, Number
from gobernar360.platform.models import IndicatorTarget
from gobernar360.platform.tenant_crud import create_entity, delete_entity, update_entity

router = APIRouter(prefix="/dashboards/{dashboard_key}", tags=["indicators"])

# Targets are stored with four decimals and at most fourteen integer digits.
TARGET_LIMIT = 10**13


class DefinitionOut(BaseModel):
    key: str
    unit: str | None
    higher_is_better: bool
    reconstructible: bool


class MonthValues(BaseModel):
    month: int
    # Recorded at the close of the month; the current month is as of today. Indicators
    # without a value that month are left out.
    values: dict[str, Number | None]


class YearValuesOut(BaseModel):
    year: int
    indicators: list[DefinitionOut]
    months: list[MonthValues]


class TargetOut(DefinitionOut):
    target: Number | None


class TargetIn(BaseModel):
    # Null removes the target.
    value: float | None = Field(allow_inf_nan=False, gt=-TARGET_LIMIT, lt=TARGET_LIMIT)


def _module(ctx: RequestContext, dashboard_key: str, level: AccessLevel) -> DashboardModule:
    # Unknown and disabled dashboards have no level, so they are refused the same way.
    if effective_level(ctx.db, ctx.membership, dashboard_key) < level:
        raise forbidden()
    return registry.get_module(dashboard_key)


def _definition(definition: IndicatorDefinition) -> DefinitionOut:
    return DefinitionOut(
        key=definition.key,
        unit=definition.unit,
        higher_is_better=definition.higher_is_better,
        reconstructible=definition.reconstructible,
    )


@router.get("/evolution")
def get_evolution(ctx: Context, today: Today, dashboard_key: str) -> list[IndicatorEvolution]:
    """Every indicator of the dashboard's catalogue, today and over the last twelve months."""
    module = _module(ctx, dashboard_key, AccessLevel.VIEWER)
    values = indicators.current_values(ctx, module, today)
    return indicators.dashboard_evolution(ctx, module, today, values)


@router.get("/evolution/months")
def get_year_values(ctx: Context, today: Today, dashboard_key: str, year: Year) -> YearValuesOut:
    """The indicators of each month of a year, shown next to the month's status light."""
    module = _module(ctx, dashboard_key, AccessLevel.VIEWER)
    keys = [definition.key for definition in module.indicators]
    recorded = indicators.history(ctx.db, keys, (year, 1), (year, 12))
    current = indicators.month_of(today)
    live = indicators.current_values(ctx, module, today) if year == today.year else {}
    months = []
    for number in range(1, 13):
        if (year, number) == current:
            values = {key: live[key] for key in keys if key in live}
        else:
            values = {
                key: recorded[key][(year, number)]
                for key in keys
                if (year, number) in recorded[key]
            }
        months.append(MonthValues(month=number, values=values))
    return YearValuesOut(
        year=year,
        indicators=[_definition(definition) for definition in module.indicators],
        months=months,
    )


@router.get("/targets")
def list_targets(ctx: Context, dashboard_key: str, year: Year) -> list[TargetOut]:
    module = _module(ctx, dashboard_key, AccessLevel.VIEWER)
    keys = [definition.key for definition in module.indicators]
    goals = indicators.targets(ctx.db, keys, [year])
    return [
        TargetOut(**_definition(definition).model_dump(), target=goals[definition.key].get(year))
        for definition in module.indicators
    ]


def _find_target(ctx: RequestContext, indicator_key: str, year: int) -> IndicatorTarget | None:
    return ctx.db.scalar(
        select(IndicatorTarget).where(
            IndicatorTarget.indicator_key == indicator_key, IndicatorTarget.year == year
        )
    )


@router.put("/targets/{year}/{indicator_key}", status_code=204)
def set_target(
    ctx: Context,
    dashboard_key: str,
    year: Annotated[Year, Path()],
    indicator_key: str,
    body: TargetIn,
) -> Response:
    module = _module(ctx, dashboard_key, AccessLevel.ADMIN)
    if module.indicator(indicator_key) is None:
        raise not_found("The dashboard has no indicator with that key.")
    existing = _find_target(ctx, indicator_key, year)
    value = None if body.value is None else Decimal(str(body.value))
    if value is None:
        if existing is not None:
            delete_entity(ctx, existing)
    elif existing is not None:
        update_entity(ctx, existing, {"value": value})
    else:
        fields = {
            "dashboard_key": dashboard_key,
            "indicator_key": indicator_key,
            "year": year,
            "value": value,
        }
        try:
            with ctx.db.begin_nested():
                create_entity(ctx, IndicatorTarget(**fields), fields)
        except IntegrityError:
            # Another administrator set the same target a moment ago: ours wins.
            update_entity(ctx, _find_target(ctx, indicator_key, year), {"value": value})
    return Response(status_code=204)
