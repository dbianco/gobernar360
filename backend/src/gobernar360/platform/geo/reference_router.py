"""Public facilities of the municipality's maps, for any of its members."""

import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from gobernar360.platform.access import Context
from gobernar360.platform.geo.features import parse_area
from gobernar360.platform.geo.models import REFERENCE_LAYERS, ReferenceFeature

router = APIRouter(prefix="/geo/reference-layers", tags=["geography"])

# Far more than a town has; keeps one answer from being huge.
MAX_FEATURES = 1000


class LayerOut(BaseModel):
    layer: str
    features: int
    imported_at: datetime


class ReferenceFeatureOut(BaseModel):
    id: uuid.UUID
    name: str
    # type, address, sector, level: those the source gives.
    properties: dict[str, str]
    geometry: dict[str, Any]


class ReferenceFeaturesOut(BaseModel):
    features: list[ReferenceFeatureOut]
    # There are more inside the area than can be sent.
    truncated: bool


@router.get("")
def list_layers(ctx: Context) -> list[LayerOut]:
    """The layers with something to show."""
    rows = ctx.db.execute(
        select(
            ReferenceFeature.layer, func.count(), func.max(ReferenceFeature.imported_at)
        ).group_by(ReferenceFeature.layer)
    ).all()
    return [
        LayerOut(layer=layer, features=features, imported_at=imported_at)
        for layer, features, imported_at in sorted(
            rows, key=lambda row: REFERENCE_LAYERS.index(row[0])
        )
    ]


@router.get("/{layer}")
def list_features(
    layer: Literal["health", "schools"], ctx: Context, bbox: str
) -> ReferenceFeaturesOut:
    """The facilities inside the visible area (`bbox`: west,south,east,north)."""
    rows = ctx.db.execute(
        select(
            ReferenceFeature.id,
            ReferenceFeature.name,
            ReferenceFeature.properties,
            ReferenceFeature.location.label("geometry"),
        )
        .where(
            ReferenceFeature.layer == layer,
            func.ST_Intersects(ReferenceFeature.location, parse_area(bbox).envelope()),
        )
        .order_by(ReferenceFeature.name, ReferenceFeature.id)
        .limit(MAX_FEATURES + 1)
    )
    found = [ReferenceFeatureOut(**row) for row in rows.mappings()]
    return ReferenceFeaturesOut(features=found[:MAX_FEATURES], truncated=len(found) > MAX_FEATURES)
