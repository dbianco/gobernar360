"""The background of the active municipality's maps, for whoever sees them."""

from fastapi import APIRouter
from pydantic import BaseModel

from gobernar360.platform import municipality_settings
from gobernar360.platform.access import Context
from gobernar360.platform.api_types import OrmModel
from gobernar360.platform.geo import backgrounds

router = APIRouter(tags=["geography"])


class BackgroundOut(OrmModel):
    key: str
    url: str
    attribution: str
    max_zoom: int
    provider: str | None
    tile_size: int
    zoom_offset: int


class ChosenBackground(BaseModel):
    background: BackgroundOut
    api_key: str | None


@router.get("/map-background")
def get_background(ctx: Context) -> ChosenBackground:
    row = municipality_settings.find(ctx.db, ctx.municipality_id)
    chosen = backgrounds.in_use(row.map_background if row else backgrounds.DEFAULT)
    return ChosenBackground(
        background=BackgroundOut.model_validate(chosen),
        api_key=row.map_api_key if row and chosen.provider else None,
    )
