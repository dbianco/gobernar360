"""A PostGIS geometry column that reads and writes GeoJSON geometries as dicts."""

import json
from typing import Any

from sqlalchemy import Text, cast, func
from sqlalchemy.dialects.postgresql.base import ischema_names
from sqlalchemy.types import UserDefinedType

# Longitude and latitude in degrees, as GeoJSON and GPS use.
SRID = 4326
# Decimals of the coordinates handed out: about a centimetre.
PRECISION = 7


class Geometry(UserDefinedType):
    """`geometry(<kind>, 4326)`. Plain dicts in and out, so no geometry library is needed."""

    cache_ok = True

    def __init__(self, kind: str = "Geometry", srid: int | str = SRID) -> None:
        self.kind = kind
        # Reflection (alembic's comparison) hands the type's arguments over as text.
        self.srid = int(srid)

    def get_col_spec(self, **kw: Any) -> str:
        return f"geometry({self.kind},{self.srid})"

    def bind_processor(self, dialect: Any):
        return lambda value: None if value is None else json.dumps(value)

    def bind_expression(self, bindvalue: Any):
        # The cast picks one of ST_GeomFromGeoJSON's overloads (text, json and jsonb).
        return func.ST_GeomFromGeoJSON(cast(bindvalue, Text))

    def column_expression(self, col: Any):
        return func.ST_AsGeoJSON(col, PRECISION, type_=self)

    def result_processor(self, dialect: Any, coltype: Any):
        return lambda value: None if value is None else json.loads(value)


# Lets SQLAlchemy reflect geometry columns, which alembic does to compare the schema.
ischema_names["geometry"] = Geometry


def is_ours(item: Any, name: str | None, kind: str, reflected: bool, compared: Any) -> bool:
    """For alembic's `include_object`: PostGIS keeps its list of coordinate systems in a table."""
    return not (kind == "table" and name == "spatial_ref_sys")
