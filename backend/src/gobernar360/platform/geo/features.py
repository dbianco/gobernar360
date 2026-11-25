"""What a map shows: the records inside the visible area, grouped when they are close."""

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Text, cast, func, select
from sqlalchemy.orm import Session

from gobernar360.core.errors import invalid_area
from gobernar360.platform.geo.contract import LocatedRecord
from gobernar360.platform.geo.types import PRECISION, SRID

# From this zoom on every record is shown on its own: streets are told apart.
FIRST_UNCLUSTERED_ZOOM = 17
# Side, in pixels, of the squares whose records are grouped together.
CELL_PIXELS = 64
TILE_PIXELS = 256
# Records sent on their own at most. The map says so when there are more.
MAX_FEATURES = 1000
# On screen a degree of latitude is longer than one of longitude; at the latitudes of
# Argentina this makes the grouping cells about square.
LATITUDE_RATIO = 0.8


@dataclass(frozen=True)
class Area:
    """The visible rectangle, in degrees."""

    west: float
    south: float
    east: float
    north: float

    def envelope(self) -> ColumnElement[Any]:
        return func.ST_MakeEnvelope(self.west, self.south, self.east, self.north, SRID)


@dataclass(frozen=True)
class Cluster:
    count: int
    # Longitude and latitude of the middle of its records.
    center: tuple[float, float]
    # West, south, east and north of its records: where to zoom to see them.
    bounds: tuple[float, float, float, float]


@dataclass(frozen=True)
class Feature:
    id: uuid.UUID
    title: str
    geometry: dict[str, Any]


@dataclass(frozen=True)
class Features:
    total: int
    features: list[Feature]
    clusters: list[Cluster]
    truncated: bool


def parse_area(text: str) -> Area:
    """ "west,south,east,north" as the visible area."""
    try:
        west, south, east, north = (float(part) for part in text.split(","))
    except ValueError as error:
        raise invalid_area("The area must be west,south,east,north.") from error
    # Written so that NaN, which compares false with everything, is refused too.
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise invalid_area("The area must be inside the world, with west < east and south < north.")
    return Area(west, south, east, north)


def _cell(zoom: int) -> tuple[float, float]:
    """Width and height, in degrees, of the grouping squares at a zoom.

    They do not depend on the area, so panning does not regroup the records.
    """
    width = 360 / (TILE_PIXELS * 2**zoom) * CELL_PIXELS
    return width, width * LATITUDE_RATIO


def visible(
    db: Session,
    record: LocatedRecord,
    conditions: list[ColumnElement[bool]],
    area: Area,
    zoom: int,
) -> Features:
    """Records inside the area. Close ones come as clusters until the zoom tells them apart."""
    model = record.model
    inside = (
        # The second condition matters for lines, whose box may overlap without them entering.
        model.location.op("&&")(area.envelope()),
        func.ST_Intersects(model.location, area.envelope()),
        *conditions,
    )
    if zoom >= FIRST_UNCLUSTERED_ZOOM:
        features = _features(db, record, inside, MAX_FEATURES + 1)
        total = len(features)
        if total > MAX_FEATURES:
            total = db.scalar(select(func.count()).select_from(model).where(*inside))
        return Features(total, features[:MAX_FEATURES], [], total > MAX_FEATURES)

    width, height = _cell(zoom)
    located = (
        # A point of a line is on the line itself, unlike its centroid.
        select(model.id.label("id"), func.ST_PointOnSurface(model.location).label("point"))
        .where(*inside)
        .subquery()
    )
    point, box = located.c.point, func.ST_Extent(located.c.point)
    center = func.ST_Centroid(func.ST_Collect(point))
    cells = db.execute(
        select(
            func.count(),
            # Any id: it is only read where there is just one.
            func.min(cast(located.c.id, Text)),
            func.ST_X(center),
            func.ST_Y(center),
            func.ST_XMin(box),
            func.ST_YMin(box),
            func.ST_XMax(box),
            func.ST_YMax(box),
        ).group_by(func.ST_SnapToGrid(point, width, height))
    ).all()
    clusters = [
        Cluster(count, _rounded(x, y), _rounded(*bounds))
        for count, _, x, y, *bounds in cells
        if count > 1
    ]
    alone = [uuid.UUID(record_id) for count, record_id, *_ in cells if count == 1]
    return Features(
        total=sum(count for count, *_ in cells),
        features=_features(db, record, (model.id.in_(alone),), MAX_FEATURES) if alone else [],
        clusters=sorted(clusters, key=lambda cluster: (-cluster.count, cluster.center)),
        truncated=len(alone) > MAX_FEATURES,
    )


def _rounded(*values: float) -> tuple[float, ...]:
    return tuple(round(value, PRECISION) for value in values)


def _features(
    db: Session, record: LocatedRecord, conditions: tuple[ColumnElement[bool], ...], limit: int
) -> list[Feature]:
    model = record.model
    rows = db.execute(
        select(model.id, record.title, model.location)
        .where(*conditions)
        .order_by(record.title, model.id)
        .limit(limit)
    )
    return [Feature(*row) for row in rows]
