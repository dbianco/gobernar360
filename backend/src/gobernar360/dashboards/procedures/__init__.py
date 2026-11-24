"""Procedures dashboard: the inventory of what the municipality offers, what each
procedure asks for and who already holds that data."""

from fastapi import APIRouter

from gobernar360.dashboards.procedures import (
    catalog_router,
    export,
    procedures_router,
    summary,
)
from gobernar360.dashboards.procedures.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(catalog_router.router)
router.include_router(procedures_router.router)
router.include_router(summary.router)
router.include_router(export.router)

module = DashboardModule(
    key=KEY,
    name="Trámites",
    router=router,
    get_summary=summary.get_summary,
    indicators=summary.INDICATORS,
)
