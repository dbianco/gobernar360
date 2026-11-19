"""Municipality administrator: manages the members of the active municipality."""

from fastapi import APIRouter

from gobernar360.platform import members
from gobernar360.platform.access import require_municipality_admin

router = APIRouter(prefix="/admin", tags=["admin"])
router.include_router(members.build_router(require_municipality_admin))
