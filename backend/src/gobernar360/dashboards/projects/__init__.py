"""Projects dashboard: government plan, projects, milestones and strategic indicators."""

from fastapi import APIRouter

from gobernar360.dashboards.projects import export, parameters_router, projects_router, summary
from gobernar360.dashboards.projects.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(parameters_router.router)
router.include_router(projects_router.router)
router.include_router(summary.router)
router.include_router(export.router)

module = DashboardModule(key=KEY, router=router, get_summary=summary.get_summary)
