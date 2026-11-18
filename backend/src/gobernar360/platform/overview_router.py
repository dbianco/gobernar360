"""General overview: headline indicators from every dashboard the member can see."""

from fastapi import APIRouter
from pydantic import BaseModel

from gobernar360.dashboards import registry
from gobernar360.platform.access import AccessLevel, Context, effective_levels
from gobernar360.platform.clock import Today

router = APIRouter(tags=["overview"])


class IndicatorOut(BaseModel):
    key: str
    value: float | int | None
    unit: str | None


class DashboardOverview(BaseModel):
    dashboard_key: str
    indicators: list[IndicatorOut]


@router.get("/overview")
def get_overview(ctx: Context, today: Today) -> list[DashboardOverview]:
    overview = []
    for key, level in effective_levels(ctx.db, ctx.membership).items():
        if level < AccessLevel.VIEWER:
            continue
        indicators = registry.get_module(key).get_summary(ctx, today)
        overview.append(
            DashboardOverview(
                dashboard_key=key,
                indicators=[
                    IndicatorOut(key=i.key, value=i.value, unit=i.unit) for i in indicators
                ],
            )
        )
    return overview
