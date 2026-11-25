"""Located records of any dashboard: map, figures by zone, review list and locations.

The routes are the same for every dashboard; what differs comes from its `LocatedRecord`.
"""

import uuid
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy import ColumnElement, func, select

from gobernar360.core.errors import forbidden, not_found
from gobernar360.dashboards import registry
from gobernar360.platform import csv_export
from gobernar360.platform.access import AccessLevel, Context, RequestContext, effective_level
from gobernar360.platform.clock import Today
from gobernar360.platform.geo import aggregates, features
from gobernar360.platform.geo.contract import LocatedRecord
from gobernar360.platform.geo.geojson import location_geometry
from gobernar360.platform.geo.zones_router import ZoneRef
from gobernar360.platform.listing import Page, Paging, PagingParams, SearchText, every_word
from gobernar360.platform.tenant_crud import get_or_404, update_entity

router = APIRouter(prefix="/dashboards/{dashboard_key}/geo/{record_key}", tags=["geography"])

ZOOM_MAX = 22


class GroupOut(BaseModel):
    # None: the records without a value, e.g. actors without a sector.
    name: str | None
    count: int


class CellOut(BaseModel):
    # Counts are numbers and amounts are decimals in text; null when hidden from the member.
    values: dict[str, int | str | None]
    groups: list[GroupOut]
    # Whether a count is hidden because it is small, or to protect one that is.
    suppressed: bool


class ZoneCellOut(CellOut):
    zone: ZoneRef


class MetricOut(BaseModel):
    key: str
    unit: str | None


class BreakdownOut(BaseModel):
    # The past day whose boundaries were used; null for today's.
    boundaries_as_of: date | None
    metrics: list[MetricOut]
    grouping: str | None
    zones: list[ZoneCellOut]
    outside: CellOut
    unlocated: CellOut
    total: CellOut
    # Counts below this many are hidden from the member; null when nothing is.
    threshold: int | None


class FeatureOut(BaseModel):
    id: uuid.UUID
    title: str
    geometry: dict[str, Any]


class ClusterOut(BaseModel):
    count: int
    center: tuple[float, float]
    bounds: tuple[float, float, float, float]


class FeaturesOut(BaseModel):
    # True when the member gets counts per zone only, never records.
    restricted: bool
    # Records inside the area.
    total: int
    features: list[FeatureOut]
    clusters: list[ClusterOut]
    # More records than can be sent on their own: zoom in to see the rest.
    truncated: bool


class LocationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # GeoJSON geometry, or null to leave the record without a location.
    location: dict[str, Any] | None


class LocationOut(BaseModel):
    location: dict[str, Any] | None
    kinds: list[str]
    zones: list[ZoneRef]


class UnzonedOut(BaseModel):
    id: uuid.UUID
    title: str


class Located:
    """The located records named in the path, and what the member may do with them."""

    def __init__(self, ctx: Context, dashboard_key: str, record_key: str) -> None:
        self.ctx = ctx
        self.level = effective_level(ctx.db, ctx.membership, dashboard_key)
        # Unknown and disabled dashboards have no level, so they are refused the same way.
        if self.level < AccessLevel.VIEWER:
            raise forbidden()
        located = registry.get_module(dashboard_key).located
        found = next((record for record in located if record.key == record_key), None)
        if found is None:
            raise not_found()
        self.record: LocatedRecord = found
        self.file_name = f"{dashboard_key}-{record_key}"

    @property
    def individual(self) -> bool:
        return aggregates.sees_individual(self.record, self.level)

    def require_individual(self) -> None:
        if not self.individual:
            raise forbidden()


LocatedParams = Annotated[Located, Depends()]


def read_filters(record: LocatedRecord, request: Request) -> BaseModel:
    """The record's own filters, taken from the query string."""
    given = {key: value for key, value in request.query_params.items() if value != ""}
    try:
        return record.filters.model_validate(given)
    except ValidationError as error:
        raise RequestValidationError(
            [{**problem, "loc": ("query", *problem["loc"])} for problem in error.errors()]
        ) from error


@router.get("/features")
def list_features(
    located: LocatedParams,
    request: Request,
    today: Today,
    bbox: str,
    zoom: Annotated[int, Query(ge=0, le=ZOOM_MAX)],
) -> FeaturesOut:
    """What is inside the visible area (`bbox`: west,south,east,north)."""
    area = features.parse_area(bbox)
    filters = read_filters(located.record, request)
    if not located.individual:
        return FeaturesOut(restricted=True, total=0, features=[], clusters=[], truncated=False)
    record, ctx = located.record, located.ctx
    found = features.visible(ctx.db, record, record.conditions(ctx, today, filters), area, zoom)
    return FeaturesOut(
        restricted=False,
        total=found.total,
        features=[FeatureOut(**vars(feature)) for feature in found.features],
        clusters=[ClusterOut(**vars(cluster)) for cluster in found.clusters],
        truncated=found.truncated,
    )


def cell_out(cell: aggregates.Cell) -> dict[str, Any]:
    return {
        "values": cell.values,
        "groups": [GroupOut(name=name, count=count) for name, count in cell.groups],
        "suppressed": cell.suppressed,
    }


def breakdown_out(record: LocatedRecord, found: aggregates.Breakdown) -> BreakdownOut:
    return BreakdownOut(
        boundaries_as_of=found.boundaries_as_of,
        metrics=[MetricOut(key=metric.key, unit=metric.unit) for metric in record.metrics],
        grouping=record.grouping.key if record.grouping else None,
        zones=[
            ZoneCellOut(zone=ZoneRef.model_validate(zone), **cell_out(cell))
            for zone, cell in found.zones
        ],
        outside=CellOut(**cell_out(found.outside)),
        unlocated=CellOut(**cell_out(found.unlocated)),
        total=CellOut(**cell_out(found.total)),
        threshold=found.threshold,
    )


@router.get("/zones")
def get_breakdown(
    located: LocatedParams, request: Request, today: Today, as_of: date | None = None
) -> BreakdownOut:
    """Figures by zone, with the boundaries in force at the end of `as_of` (default: today's)."""
    filters = read_filters(located.record, request)
    found = aggregates.by_zone(located.ctx, located.record, located.level, filters, today, as_of)
    return breakdown_out(located.record, found)


# Names of the rows that are not a zone, and what a hidden figure says.
OUTSIDE, UNLOCATED, TOTAL, HIDDEN = "(outside)", "(no location)", "(total)", "*"


@router.get("/zones.csv")
def export_breakdown(
    located: LocatedParams, request: Request, today: Today, as_of: date | None = None
) -> Response:
    """The same figures as a file, hiding the same ones."""
    found = aggregates.by_zone(
        located.ctx,
        located.record,
        located.level,
        read_filters(located.record, request),
        today,
        as_of,
    )
    keys = [metric.key for metric in located.record.metrics]

    def row(name: str, cell: aggregates.Cell) -> list[Any]:
        values = [cell.values[key] for key in keys]
        return [name, *(HIDDEN if value is None else value for value in values)]

    rows = [row(csv_export.safe_text(zone.name), cell) for zone, cell in found.zones]
    rows += [
        row(OUTSIDE, found.outside),
        row(UNLOCATED, found.unlocated),
        row(TOTAL, found.total),
    ]
    return csv_export.csv_response(f"{located.file_name}-by-zone.csv", ("zone", *keys), rows)


@router.get("/unzoned")
def list_unzoned(
    located: LocatedParams,
    paging: PagingParams,
    reason: Literal["outside", "unlocated"] = "outside",
    q: SearchText = None,
) -> Page[UnzonedOut]:
    """Records to review: located outside every zone, or without a location yet."""
    located.require_individual()
    record = located.record
    condition = (
        aggregates.outside_every_zone(record)
        if reason == "outside"
        else record.model.location.is_(None)
    )
    return _named_page(located.ctx, record, paging, condition, *every_word(q, record.title))


def _named_page(
    ctx: RequestContext, record: LocatedRecord, paging: Paging, *conditions: ColumnElement[bool]
) -> dict[str, Any]:
    """A page of records by name alone: `listing.page_of` pages whole rows."""
    model = record.model
    total = ctx.db.scalar(select(func.count()).select_from(model).where(*conditions))
    rows = ctx.db.execute(
        select(model.id, record.title)
        .where(*conditions)
        .order_by(func.unaccent(record.title), model.id)
        .limit(paging.limit)
        .offset(paging.offset)
    )
    return {"items": [UnzonedOut(id=row[0], title=row[1]) for row in rows], "total": total}


def _location_out(located: Located, entity: Any) -> LocationOut:
    return LocationOut(
        location=entity.location,
        kinds=list(located.record.model.location_kinds),
        zones=[ZoneRef.model_validate(zone) for zone in entity.zones],
    )


@router.get("/{record_id}/location")
def get_location(record_id: uuid.UUID, located: LocatedParams) -> LocationOut:
    located.require_individual()
    return _location_out(located, get_or_404(located.ctx, located.record.model, record_id))


@router.put("/{record_id}/location")
def set_location(record_id: uuid.UUID, payload: LocationIn, located: LocatedParams) -> LocationOut:
    located.require_individual()
    if located.level < AccessLevel.EDITOR:
        raise forbidden()
    entity = get_or_404(located.ctx, located.record.model, record_id)
    location = payload.location
    if location is not None:
        location = location_geometry(location, located.record.model.location_kinds)
    update_entity(located.ctx, entity, {"location": location})
    # The database has just worked out the zones.
    located.ctx.db.expire(entity, ["location", "zones"])
    return _location_out(located, entity)
