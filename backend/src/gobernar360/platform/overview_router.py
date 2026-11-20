"""General overview: headline indicators from every dashboard the member can see."""

from fastapi import APIRouter
from pydantic import BaseModel

from gobernar360.dashboards import registry
from gobernar360.platform import status
from gobernar360.platform.access import AccessLevel, Context, effective_levels
from gobernar360.platform.api_types import OrmModel
from gobernar360.platform.clock import Today

router = APIRouter(tags=["overview"])


class IndicatorOut(BaseModel):
    key: str
    value: float | int | None
    unit: str | None


class StatusOut(OrmModel):
    year: int
    month: int
    color: str


class DashboardOverview(BaseModel):
    dashboard_key: str
    indicators: list[IndicatorOut]
    # The latest status light and the ones set shortly before it, newest first.
    status: list[StatusOut]


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
                status=[StatusOut.model_validate(row) for row in status.recent(ctx.db, key, today)],
            )
        )
    return overview
