"""Environment dashboard: variables of the environmental agenda, loaded per period."""

from fastapi import APIRouter

from gobernar360.dashboards.environment import parameters_router
from gobernar360.dashboards.environment.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(parameters_router.router)

module = DashboardModule(key=KEY, router=router, get_summary=lambda ctx, today: [])
