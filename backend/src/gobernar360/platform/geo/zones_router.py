"""Zones of the municipality: seen by its members, managed by its administrators."""

import uuid
from datetime import date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import func, select

from gobernar360.core.errors import (
    ApiError,
    not_found,
    zone_file_invalid,
    zone_file_too_large,
)
from gobernar360.platform.access import Context, RequestContext, require_municipality_admin
from gobernar360.platform.api_types import Name, OrmModel, PatchModel
from gobernar360.platform.clock import Today
from gobernar360.platform.geo import zones
from gobernar360.platform.geo.geojson import boundary_geometry
from gobernar360.platform.geo.models import Zone, ZoneVersion

MAX_IMPORTED_ZONES = 300
# A whole city with detailed outlines takes a tenth of this.
MAX_IMPORT_BYTES = 10 * 1024 * 1024
# Properties of a GeoJSON feature that may hold the zone's name.
NAME_PROPERTIES = ("name", "nombre")

router = APIRouter(tags=["zones"])

AdminContext = Annotated[RequestContext, Depends(require_municipality_admin)]


class ZoneOut(BaseModel):
    id: uuid.UUID
    name: str
    version: int
    # When this boundary took effect.
    valid_from: datetime
    # Where an official boundary comes from, e.g. the law that approves it.
    source: str
    boundary: dict[str, Any]


class ZoneRef(OrmModel):
    id: uuid.UUID
    name: str


class OverlapOut(OrmModel):
    zone: ZoneRef
    other: ZoneRef
    area_m2: float


class ZoneSaved(BaseModel):
    zone: ZoneOut
    # Other zones this one shares ground with. A warning: the zone was saved.
    overlaps: list[OverlapOut]


class VersionOut(OrmModel):
    version: int
    valid_from: datetime
    valid_to: datetime | None
    source: str
    boundary: dict[str, Any]


class ZoneIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Name
    # GeoJSON Polygon or MultiPolygon.
    boundary: dict[str, Any]


class ZonePatch(PatchModel):
    model_config = ConfigDict(extra="forbid")

    name: Name | None = None
    boundary: dict[str, Any] | None = None
    # The version the person was looking at: changing the zone on top of somebody else's
    # new boundary would undo it unseen.
    base_version: int


class ImportIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # GeoJSON FeatureCollection; every feature needs a name property.
    geojson: dict[str, Any]


class ImportOut(BaseModel):
    created: int
    moved: int
    unchanged: int
    overlaps: list[OverlapOut]


def _listed(ctx: RequestContext, *conditions: Any) -> list[ZoneOut]:
    rows = ctx.db.execute(
        select(
            Zone.id,
            Zone.name,
            ZoneVersion.version,
            ZoneVersion.valid_from,
            ZoneVersion.source,
            ZoneVersion.boundary,
        )
        .join(ZoneVersion, ZoneVersion.zone_id == Zone.id)
        .where(*conditions)
        .order_by(func.unaccent(Zone.name), Zone.id)
    )
    return [ZoneOut(**row) for row in rows.mappings()]


def _overlaps(ctx: RequestContext, zone_ids: list[uuid.UUID] | None = None) -> list[OverlapOut]:
    return [OverlapOut.model_validate(pair) for pair in zones.overlaps(ctx.db, zone_ids)]


def _saved(ctx: RequestContext, zone: Zone) -> ZoneSaved:
    [out] = _listed(ctx, zones.is_current(), Zone.id == zone.id)
    return ZoneSaved(zone=out, overlaps=_overlaps(ctx, [zone.id]))


@router.get("/zones")
def list_zones(ctx: Context, today: Today, as_of: date | None = None) -> list[ZoneOut]:
    """Zones and the boundaries a breakdown as of that day uses (default: today's)."""
    day = zones.boundaries_day(ctx.db, as_of, today)
    return _listed(ctx, zones.in_force(day))


@router.post("/admin/zones", status_code=201)
def create_zone(payload: ZoneIn, ctx: AdminContext) -> ZoneSaved:
    return _saved(ctx, zones.create(ctx, payload.name, boundary_geometry(payload.boundary)))


@router.get("/admin/zones/overlaps")
def list_overlaps(ctx: AdminContext) -> list[OverlapOut]:
    return _overlaps(ctx)


async def read_import(request: Request, ctx: AdminContext) -> ImportIn:
    """The body of an import, read only as far as the largest one accepted.

    FastAPI would read and parse all of it before any check of ours: that is why the body
    is not a parameter of the route. Declaring the context here has whoever may not import
    refused before a single byte is read.
    """
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_IMPORT_BYTES:
            raise zone_file_too_large(MAX_IMPORT_BYTES)
    try:
        return ImportIn.model_validate_json(bytes(body))
    except ValidationError as error:
        raise RequestValidationError(
            [{**problem, "loc": ("body", *problem["loc"])} for problem in error.errors()]
        ) from error


@router.post(
    "/admin/zones/import",
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {"application/json": {"schema": ImportIn.model_json_schema()}},
        }
    },
)
def import_zones(
    ctx: AdminContext, payload: Annotated[ImportIn, Depends(read_import)]
) -> ImportOut:
    """Create or move the zones of a GeoJSON file. Zones are matched by name; nothing is
    changed if any of them has a problem."""
    wanted = _read_features(ctx, payload.geojson)
    existing = {
        zone.name.casefold(): zone
        for zone in ctx.db.scalars(
            select(Zone).where(Zone.retired_at.is_(None)).with_for_update().order_by(Zone.id)
        )
    }
    created, moved, touched = 0, 0, []
    for name, boundary in wanted:
        zone = existing.get(name.casefold())
        if zone is None:
            touched.append(zones.create(ctx, name, boundary).id)
            created += 1
        elif zones.move(ctx, zone, boundary):
            touched.append(zone.id)
            moved += 1
    return ImportOut(
        created=created,
        moved=moved,
        unchanged=len(wanted) - len(touched),
        overlaps=_overlaps(ctx, touched),
    )


def _read_features(
    ctx: RequestContext, geojson: dict[str, Any]
) -> list[tuple[str, dict[str, Any]]]:
    """Names and boundaries in the file, or an error listing every feature with a problem."""
    features = geojson.get("features")
    if geojson.get("type") != "FeatureCollection" or not isinstance(features, list):
        raise _file_problem(0, "not_a_collection")
    if not features:
        raise _file_problem(0, "empty")
    if len(features) > MAX_IMPORTED_ZONES:
        raise _file_problem(0, "too_many")
    read: list[tuple[str, dict[str, Any]]] = []
    problems: list[dict[str, Any]] = []
    seen: set[str] = set()
    for number, feature in enumerate(features, start=1):
        name = _feature_name(feature)
        if name is None:
            problems.append({"row": number, "name": None, "code": "no_name"})
            continue
        if name.casefold() in seen:
            problems.append({"row": number, "name": name, "code": "repeated_name"})
            continue
        seen.add(name.casefold())
        try:
            boundary = boundary_geometry(feature.get("geometry"))
            zones.check_valid(ctx.db, boundary)
            read.append((name, boundary))
        except ApiError as error:
            problems.append({"row": number, "name": name, "code": error.code})
    if problems:
        raise zone_file_invalid(problems)
    return read


def _file_problem(row: int, code: str) -> ApiError:
    """A problem of the whole file, reported as of feature 0."""
    return zone_file_invalid([{"row": row, "name": None, "code": code}])


def _feature_name(feature: Any) -> str | None:
    properties = feature.get("properties") if isinstance(feature, dict) else None
    if not isinstance(properties, dict):
        return None
    by_name = {str(key).casefold(): value for key, value in properties.items()}
    for key in NAME_PROPERTIES:
        value = by_name.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:200]
    return None


@router.patch("/admin/zones/{zone_id}")
def update_zone(zone_id: uuid.UUID, payload: ZonePatch, ctx: AdminContext) -> ZoneSaved:
    """Rename the zone or move its boundary from now on. Past periods keep the old one."""
    zone = zones.find(ctx.db, zone_id, for_update=True)
    zones.check_base(ctx.db, zone, payload.base_version)
    if payload.boundary is not None:
        zones.move(ctx, zone, boundary_geometry(payload.boundary))
    if payload.name is not None and payload.name != zone.name:
        zones.rename(ctx, zone, payload.name)
    return _saved(ctx, zone)


@router.delete("/admin/zones/{zone_id}", status_code=204)
def retire_zone(zone_id: uuid.UUID, ctx: AdminContext) -> None:
    """Stop using the zone. Figures of the periods it was in force keep it."""
    zones.retire(ctx, zones.find(ctx.db, zone_id, for_update=True))


@router.get("/admin/zones/{zone_id}/versions")
def list_versions(zone_id: uuid.UUID, ctx: AdminContext) -> list[VersionOut]:
    """Every boundary the zone has had, the newest first."""
    versions = ctx.db.scalars(
        select(ZoneVersion)
        .where(ZoneVersion.zone_id == zone_id)
        .order_by(ZoneVersion.version.desc())
    ).all()
    if not versions:
        raise not_found()
    return [VersionOut.model_validate(version) for version in versions]
