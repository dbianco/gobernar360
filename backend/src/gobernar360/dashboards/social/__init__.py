"""Social dashboard: people, households, benefits delivered and interventions."""

from fastapi import APIRouter

from gobernar360.dashboards.registry import DashboardModule, SummaryIndicator
from gobernar360.dashboards.social import (
    deliveries_router,
    households_router,
    interventions_router,
    parameters_router,
    people_router,
)
from gobernar360.dashboards.social.access import KEY

router = APIRouter()
router.include_router(parameters_router.router)
router.include_router(people_router.router)
router.include_router(households_router.router)
router.include_router(deliveries_router.router)
router.include_router(interventions_router.router)


def _no_summary(ctx, today) -> list[SummaryIndicator]:
    return []


module = DashboardModule(key=KEY, router=router, get_summary=_no_summary)
