"""Complaints dashboard: every complaint a resident makes, followed from reception until it
is solved, with a service clock in business days."""

from fastapi import APIRouter

from gobernar360.dashboards.complaints import (
    complaints_router,
    export,
    parameters_router,
    summary,
)
from gobernar360.dashboards.complaints.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(parameters_router.router)
router.include_router(complaints_router.router)
router.include_router(summary.router)
router.include_router(export.router)

module = DashboardModule(key=KEY, router=router, get_summary=summary.get_summary)
