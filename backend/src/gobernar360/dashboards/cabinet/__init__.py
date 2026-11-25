"""Cabinet dashboard: meetings, the commitments taken in them and how they are delivered.

The commitments are the platform's (`platform.commitments`); this package imports no other
dashboard, and knows what they are about only through `platform.subjects`.
"""

from fastapi import APIRouter

from gobernar360.dashboards.cabinet import (
    commitments_router,
    export,
    meetings_router,
    present,
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
    name="Gabinete",
    router=router,
    get_summary=summary.get_summary,
    indicators=summary.INDICATORS,
    get_commitment_origins=present.origins,
)
