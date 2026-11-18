"""Projects dashboard: government plan, projects, milestones and strategic indicators."""

from fastapi import APIRouter

from gobernar360.dashboards.projects import parameters_router
from gobernar360.dashboards.projects.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(parameters_router.router)

module = DashboardModule(key=KEY, router=router, get_summary=lambda ctx: [])
