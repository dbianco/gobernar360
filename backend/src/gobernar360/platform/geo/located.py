"""The mixin that gives a record a place, and the migration helper that goes with it."""

from typing import Any, ClassVar

from sqlalchemy import and_, join
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from gobernar360.platform.geo.models import RecordZone, Zone, ZoneVersion
from gobernar360.platform.geo.types import Geometry

POINT = "Point"
LINE = "LineString"


class LocatedMixin:
    """A tenant record with a place on the map. Its migration must call enable_location().

    `location_kinds` lists the GeoJSON geometry types the record accepts. The location is
    loaded only when asked for: lists do not carry it.
    """

    location_kinds: ClassVar[tuple[str, ...]] = (POINT,)

    @declared_attr
    def location(cls) -> Mapped[dict[str, Any] | None]:  # pragma: no mutate block
        return mapped_column(
            Geometry(_column_kind(cls.location_kinds)), nullable=True, deferred=True
        )

    @declared_attr
    def zones(cls) -> Mapped[list[Zone]]:
        """The zones the record is in today. The database keeps them up to date."""
        return relationship(
            Zone,
            secondary=join(
                RecordZone.__table__,
                ZoneVersion.__table__,
                RecordZone.zone_version_id == ZoneVersion.id,
            ),
            primaryjoin=lambda: and_(
                cls.id == RecordZone.record_id,
                RecordZone.record_table == cls.__tablename__,
                ZoneVersion.valid_to.is_(None),
            ),
            secondaryjoin=lambda: ZoneVersion.zone_id == Zone.id,
            order_by=lambda: Zone.name,
            viewonly=True,
        )


def _column_kind(kinds: tuple[str, ...]) -> str:  # pragma: no mutate block
    return kinds[0] if len(kinds) == 1 else "Geometry"


# Runs only while migrating; tests/platform/geo/test_assignment.py checks what it sets up.
def enable_location(
    table_name: str, kinds: tuple[str, ...] = (POINT,)
) -> None:  # pragma: no mutate block
    """Migration helper: add the location column and keep the record's zones up to date."""
    from alembic import op

    op.execute(
        f'ALTER TABLE "{table_name}" ADD COLUMN location geometry({_column_kind(kinds)}, 4326)'
    )
    if len(kinds) > 1:
        allowed = ", ".join(f"'{kind.upper()}'" for kind in kinds)
        op.execute(
            f'ALTER TABLE "{table_name}" ADD CONSTRAINT location_kind '
            f"CHECK (GeometryType(location) IN ({allowed}))"
        )
    # No spatial index: row-level security keeps the API role from using one, because
    # PostgreSQL may not run PostGIS operators (not leakproof) before the policy. Queries
    # narrow by municipality first, which is what bounds them.
    op.execute(
        f"CREATE TRIGGER assign_zones "
        f'AFTER INSERT OR DELETE OR UPDATE OF location, municipality_id ON "{table_name}" '
        f"FOR EACH ROW EXECUTE FUNCTION geo_assign_record()"
    )


def disable_location(table_name: str) -> None:  # pragma: no mutate block
    """Migration helper: undo enable_location()."""
    from alembic import op

    op.execute(f'DROP TRIGGER assign_zones ON "{table_name}"')
    op.execute(f'ALTER TABLE "{table_name}" DROP COLUMN location')
    op.execute(f"DELETE FROM record_zones WHERE record_table = '{table_name}'")
