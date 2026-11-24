"""General overview: headline indicators from every dashboard the member can see, with their
evolution, and the indicators that combine dashboards."""

from fastapi import APIRouter
from pydantic import BaseModel

from gobernar360.dashboards import registry
from gobernar360.platform import indicators, status
from gobernar360.platform.access import AccessLevel, Context, effective_levels
from gobernar360.platform.api_types import OrmModel
from gobernar360.platform.clock import Today
from gobernar360.platform.indicators import IndicatorEvolution

router = APIRouter(tags=["overview"])


class StatusOut(OrmModel):
    year: int
    month: int
    color: str


class DashboardOverview(BaseModel):
    dashboard_key: str
    # The indicators the dashboard reports today; empty while it has no data.
    indicators: list[IndicatorEvolution]
    # The latest status light and the ones set shortly before it, newest first.
    status: list[StatusOut]


@router.get("/overview")
def get_overview(ctx: Context, today: Today) -> list[DashboardOverview]:
    overview = []
    for key, level in effective_levels(ctx.db, ctx.membership).items():
        if level < AccessLevel.VIEWER:
            continue
        module = registry.get_module(key)
        reported = module.get_summary(ctx, today)
        values = {indicator.key: indicator.value for indicator in reported}
        overview.append(
            DashboardOverview(
                dashboard_key=key,
                indicators=indicators.dashboard_evolution(
                    ctx, module, today, values, keys=[indicator.key for indicator in reported]
                ),
                status=[StatusOut.model_validate(row) for row in status.recent(ctx.db, key, today)],
            )
        )
    return overview


@router.get("/overview/combined")
def get_combined(ctx: Context, today: Today) -> list[indicators.CombinedEvolution]:
    """Indicators that relate two dashboards, for members who can see both."""
    visible = indicators.visible_combined(effective_levels(ctx.db, ctx.membership))
    values: dict[str, indicators.Number | None] = {}
    for module in {module.key: module for _, modules in visible for module in modules}.values():
        values.update(indicators.current_values(ctx, module, today))
    return [indicators.combined_evolution(ctx, combined, values, today) for combined, _ in visible]
