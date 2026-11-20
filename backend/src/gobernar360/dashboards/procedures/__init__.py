"""Procedures dashboard: the inventory of what the municipality offers, what each
procedure asks for and who already holds that data."""

from fastapi import APIRouter

from gobernar360.dashboards.procedures import catalog_router
from gobernar360.dashboards.procedures.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(catalog_router.router)

module = DashboardModule(key=KEY, router=router, get_summary=lambda ctx, today: [])
