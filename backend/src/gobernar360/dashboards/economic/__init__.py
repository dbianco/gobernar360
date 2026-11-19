"""Economic dashboard: local economic actors, people, support tools and their assignments."""

from datetime import date

from fastapi import APIRouter

from gobernar360.dashboards.economic import actors_router, parameters_router, people_router
from gobernar360.dashboards.economic.access import KEY
from gobernar360.dashboards.registry import DashboardModule, SummaryIndicator
from gobernar360.platform.access import RequestContext

router = APIRouter()
router.include_router(parameters_router.router)
router.include_router(actors_router.router)
router.include_router(people_router.router)


def _no_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    return []


module = DashboardModule(key=KEY, router=router, get_summary=_no_summary)
