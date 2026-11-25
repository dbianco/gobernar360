"""Location columns of the CSV downloads of located records."""

import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from gobernar360.platform.csv_export import safe_text
from gobernar360.platform.geo.types import PRECISION

LOCATION_COLUMNS = ("zones", "latitude", "longitude")

Places = dict[uuid.UUID, tuple[float, float]]


def places_of(db: Session, model: type[Any], ids: list[uuid.UUID]) -> Places:
    """Latitude and longitude of the located records among `ids`; of a line, a point on it."""
    point = func.ST_PointOnSurface(model.location)
    rows = db.execute(
        select(model.id, func.ST_Y(point), func.ST_X(point)).where(
            model.id.in_(ids), model.location.is_not(None)
        )
    )
    return {key: (round(y, PRECISION), round(x, PRECISION)) for key, y, x in rows}


def location_cells(record: Any, places: Places) -> tuple[Any, ...]:
    """The cells of LOCATION_COLUMNS. Load the records with `selectinload(Model.zones)`."""
    latitude, longitude = places.get(record.id, ("", ""))
    return safe_text(";".join(zone.name for zone in record.zones)), latitude, longitude
