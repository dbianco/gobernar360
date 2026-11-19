"""Environment dashboard: variables of the environmental agenda, loaded per period."""

from fastapi import APIRouter

from gobernar360.dashboards.environment import export, parameters_router, summary, values_router
from gobernar360.dashboards.environment.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(parameters_router.router)
router.include_router(values_router.router)
router.include_router(summary.router)
router.include_router(export.router)

module = DashboardModule(key=KEY, router=router, get_summary=summary.get_summary)
