"""Cabinet dashboard: meetings, the commitments taken in them and their follow-up.

Commitments point at months and records of other dashboards only through
`platform.subjects`; this package imports no other dashboard.
"""

from fastapi import APIRouter

from gobernar360.dashboards.cabinet import (
    commitments_router,
    export,
    meetings_router,
    summary,
)
from gobernar360.dashboards.cabinet.access import KEY
from gobernar360.dashboards.registry import DashboardModule

router = APIRouter()
router.include_router(meetings_router.router)
router.include_router(commitments_router.router)
router.include_router(summary.router)
router.include_router(export.router)

module = DashboardModule(
    key=KEY,
    router=router,
    get_summary=summary.get_summary,
    get_commitments=summary.get_commitments,
)
