"""Economic dashboard: local economic actors, people, support tools and their assignments."""

from fastapi import APIRouter

from gobernar360.dashboards.economic import (
    actors_router,
    assignments_router,
    export,
    parameters_router,
    people_router,
    summary,
)
from gobernar360.dashboards.economic.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(parameters_router.router)
router.include_router(actors_router.router)
router.include_router(people_router.router)
router.include_router(assignments_router.router)
router.include_router(summary.router)
router.include_router(export.router)

module = DashboardModule(
    key=KEY,
    name="Económico",
    router=router,
    get_summary=summary.get_summary,
    indicators=summary.INDICATORS,
)
