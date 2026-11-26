"""Bringing a municipality's official geography in: its urban radius and its facilities.

`gobernar360 import-idecor` runs it. Everything is read and checked before anything is
stored, and stored in one transaction: a failure leaves the municipality as it was.
"""

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from sqlalchemy import func, select, type_coerce
from sqlalchemy.orm import Session, undefer

from gobernar360.core.errors import ApiError
from gobernar360.platform import municipality_settings
from gobernar360.platform.access import RequestContext
from gobernar360.platform.audit import record_change
from gobernar360.platform.geo import idecor, zones
from gobernar360.platform.geo.geojson import boundary_geometry, location_geometry
from gobernar360.platform.geo.idecor import IdecorError
from gobernar360.platform.geo.located import POINT
from gobernar360.platform.geo.models import HEALTH, SCHOOLS, ReferenceFeature, Zone
from gobernar360.platform.geo.types import PRECISION, SRID, Geometry
from gobernar360.platform.geo.zones import Overlap
from gobernar360.platform.tenant_crud import update_entity

RADIUS_ZONE = "Radio urbano"
MAX_SOURCE = 300
MAX_NAME = 300
MAX_PROPERTY = 300


@dataclass(frozen=True)
class Layer:
    """A layer of facilities: where it is in IDECOR and what is kept of each one."""

    name: str
    title: str
    # What we call it, from what they do; the first that has a value.
    properties: dict[str, tuple[str, ...]]


# Nothing else is kept: the layers are public, but only this is of use on a map.
LAYERS = {
    HEALTH: Layer(
        idecor.HEALTH,
        "establecimiento_salud",
        {
            "type": ("categoria", "tipo"),
            "address": ("domicilio",),
            "sector": ("dependencia",),
        },
    ),
    SCHOOLS: Layer(
        idecor.SCHOOLS,
        "nombre",
        {"level": ("nivel",), "address": ("est_domicilio",), "sector": ("est_sector",)},
    ),
}


@dataclass(frozen=True)
class RadiusReport:
    change: Literal["created", "moved", "unchanged"]
    area_ha: float
    source: str
    law: str
    srid: int
    overlaps: list[Overlap]


@dataclass
class LayerReport:
    layer: str
    source: str
    srid: int
    # Features in the answer; the sum of `kept` and the next two.
    read: int = 0
    # Without a place, a name or an identifier, of a kind that is not a point, or repeated.
    skipped: int = 0
    # In the box of the radius but not inside it, e.g. of the next town.
    outside: int = 0
    created: int = 0
    moved: int = 0
    unchanged: int = 0
    # Stored by an earlier import and no longer published.
    removed: int = 0

    @property
    def kept(self) -> int:
        return self.created + self.moved + self.unchanged


@dataclass
class ImportReport:
    radius: RadiusReport | None = None
    layers: list[LayerReport] = field(default_factory=list)


@dataclass(frozen=True)
class _Facility:
    source_id: str
    name: str
    properties: dict[str, str]
    location: dict[str, Any]


def _finite(coordinates: Any) -> bool:
    if isinstance(coordinates, list):
        return all(_finite(part) for part in coordinates)
    return (
        isinstance(coordinates, int | float)
        and not isinstance(coordinates, bool)
        and math.isfinite(coordinates)
    )


def _to_degrees(db: Session, geometry: dict[str, Any], srid: int) -> Any:
    """The geometry in degrees, worked out by the database."""
    # PostGIS reads GeoJSON as degrees whatever it is.
    read = func.ST_SetSRID(func.ST_GeomFromGeoJSON(json.dumps(geometry)), srid)
    return json.loads(
        db.scalar(select(func.ST_AsGeoJSON(func.ST_Transform(read, SRID), PRECISION)))
    )


def _radius(db: Session, answer: idecor.Answer, key: str) -> tuple[dict[str, Any], str]:
    """The boundary of the radius, in degrees, and the law that approves it."""
    found = [
        feature
        for feature in answer.features
        if isinstance(feature, dict) and str((feature.get("properties") or {}).get("key")) == key
    ]
    if len(found) != 1:
        raise IdecorError(
            f"{idecor.RADIUS}: expected one urban radius with key {key}, found {len(found)}."
        )
    [feature] = found
    geometry = feature.get("geometry")
    kind = geometry.get("type") if isinstance(geometry, dict) else None
    if kind not in ("Polygon", "MultiPolygon") or not _finite(geometry.get("coordinates")):
        raise IdecorError(f"{idecor.RADIUS}: the urban radius {key} has no usable boundary.")
    try:
        boundary = boundary_geometry(_to_degrees(db, geometry, answer.srid))
        zones.check_valid(db, boundary)
    except ApiError as error:
        raise IdecorError(f"{idecor.RADIUS}: {error.message}") from error
    law = feature["properties"].get("url")
    return boundary, str(law).strip()[:MAX_SOURCE] if law else ""


def _text(value: Any) -> str:
    """A value as IDECOR writes it, sometimes a list inside a text: '["1. Común"]'."""
    if isinstance(value, str) and value.startswith("["):
        try:
            parts = json.loads(value)
        except ValueError:
            parts = [value]
        value = "; ".join(str(part).strip() for part in parts if str(part).strip())
    return "" if value is None else " ".join(str(value).split())


def _facility(db: Session, layer: Layer, feature: Any, srid: int) -> _Facility | None:
    """What is kept of a feature, or None when it cannot be shown."""
    if not isinstance(feature, dict):
        return None
    properties, geometry = feature.get("properties"), feature.get("geometry")
    if not isinstance(properties, dict) or not isinstance(geometry, dict):
        return None
    source_id, name = _text(properties.get("id")), _text(properties.get(layer.title))
    coordinates = geometry.get("coordinates")
    if not source_id or not name or geometry.get("type") != POINT:
        return None
    if not isinstance(coordinates, list) or len(coordinates) < 2 or not _finite(coordinates):
        return None
    try:
        location = location_geometry(
            _to_degrees(db, {"type": POINT, "coordinates": coordinates[:2]}, srid), (POINT,)
        )
    except ApiError:
        # Nowhere in the world.
        return None
    kept = {
        ours: next((text for key in theirs if (text := _text(properties.get(key)))), "")
        for ours, theirs in layer.properties.items()
    }
    return _Facility(
        source_id[:100],
        name[:MAX_NAME],
        {key: value[:MAX_PROPERTY] for key, value in kept.items() if value},
        location,
    )


def _box(boundary: dict[str, Any]) -> idecor.Box:
    positions = [p for polygon in boundary["coordinates"] for ring in polygon for p in ring]
    longitudes, latitudes = zip(*positions, strict=True)
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def _inside(db: Session, boundary: dict[str, Any], location: dict[str, Any]) -> bool:
    shape, point = type_coerce(boundary, Geometry()), type_coerce(location, Geometry())
    return db.scalar(select(func.ST_Intersects(shape, point)))


def _facilities(
    db: Session, key: str, answer: idecor.Answer, boundary: dict[str, Any]
) -> tuple[dict[str, _Facility], LayerReport]:
    report = LayerReport(key, answer.source, answer.srid, read=len(answer.features))
    found: dict[str, _Facility] = {}
    for feature in answer.features:
        facility = _facility(db, LAYERS[key], feature, answer.srid)
        if facility is None or facility.source_id in found:
            report.skipped += 1
        elif not _inside(db, boundary, facility.location):
            report.outside += 1
        else:
            found[facility.source_id] = facility
    return found, report


def _save_radius(
    ctx: RequestContext, boundary: dict[str, Any], law: str, answer: idecor.Answer
) -> RadiusReport:
    zone = ctx.db.scalar(
        select(Zone)
        .where(func.lower(Zone.name) == RADIUS_ZONE.lower(), Zone.retired_at.is_(None))
        .with_for_update()
    )
    if zone is None:
        zone, change = zones.create(ctx, RADIUS_ZONE, boundary, law), "created"
    elif zones.move(ctx, zone, boundary, law):
        change = "moved"
    else:
        change = "unchanged"
        current = zones.current_version(ctx.db, zone)
        if current.source != law:
            # The same outline under another law, or drawn by hand before.
            update_entity(ctx, current, {"source": law})
    record_change(ctx, "update", zone, {"imported_from": answer.source, "law": law})
    return RadiusReport(
        change,
        ctx.db.scalar(select(zones.area_m2(type_coerce(boundary, Geometry())))) / 10_000,
        answer.source,
        law,
        answer.srid,
        zones.overlaps(ctx.db, [zone.id]),
    )


def _save_layer(
    ctx: RequestContext, found: dict[str, _Facility], report: LayerReport, now: datetime
) -> None:
    stored = {
        row.source_id: row
        for row in ctx.db.scalars(
            select(ReferenceFeature)
            .where(ReferenceFeature.layer == report.layer)
            .options(undefer(ReferenceFeature.location))
            .with_for_update()
        )
    }
    for source_id, facility in found.items():
        row = stored.pop(source_id, None)
        if row is None:
            row = ReferenceFeature(
                municipality_id=ctx.municipality_id, layer=report.layer, source_id=source_id
            )
            ctx.db.add(row)
            report.created += 1
        elif (row.name, row.properties, row.location) == (
            facility.name,
            facility.properties,
            facility.location,
        ):
            report.unchanged += 1
        else:
            report.moved += 1
        row.name, row.properties = facility.name, facility.properties
        row.location = facility.location
        row.source_url, row.imported_at = report.source[:1000], now
    for row in stored.values():
        ctx.db.delete(row)
    report.removed = len(stored)
    ctx.db.flush()


def import_official(
    ctx: RequestContext,
    source: idecor.Source,
    *,
    radius: bool,
    layers: Iterable[str],
    now: datetime,
) -> ImportReport:
    """Bring in the urban radius as a zone, and the facilities inside it.

    `ctx` is a system context: the caller's transaction is what makes it all or nothing.
    """
    settings = municipality_settings.find(ctx.db, ctx.municipality_id)
    key = settings.idecor_key if settings else None
    if key is None:
        raise IdecorError(
            "The municipality has no IDECOR key. The platform operator sets it in "
            "Configuración, tab Mapas y zonas."
        )
    # The radius says where to look for facilities even when the zone is left alone.
    answer = source.radius(key)
    boundary, law = _radius(ctx.db, answer, key)
    read = [
        _facilities(ctx.db, layer, source.facilities(LAYERS[layer].name, _box(boundary)), boundary)
        for layer in layers
    ]
    report = ImportReport()
    if radius:
        report.radius = _save_radius(ctx, boundary, law, answer)
    for found, layer_report in read:
        _save_layer(ctx, found, layer_report, now)
        report.layers.append(layer_report)
    if settings and report.layers:
        record_change(
            ctx,
            "update",
            settings,
            {
                "reference_layers": {
                    r.layer: {"imported_from": r.source, "features": r.kept} for r in report.layers
                }
            },
        )
    return report
