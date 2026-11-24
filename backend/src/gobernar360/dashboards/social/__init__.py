"""Social dashboard: people, households, benefits delivered and interventions."""

from fastapi import APIRouter

from gobernar360.dashboards.registry import DashboardModule
from gobernar360.dashboards.social import (
    deliveries_router,
    export,
    households_router,
    interventions_router,
    parameters_router,
    people_router,
    summary,
)
from gobernar360.dashboards.social.access import KEY

router = APIRouter()
router.include_router(parameters_router.router)
router.include_router(people_router.router)
router.include_router(households_router.router)
router.include_router(deliveries_router.router)
router.include_router(interventions_router.router)
router.include_router(summary.router)
router.include_router(export.router)

module = DashboardModule(
    key=KEY,
    name="Social",
    router=router,
    get_summary=summary.get_summary,
    indicators=summary.INDICATORS,
)
