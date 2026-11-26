"""Zones and places for tests, on a plane grid: one unit is a hundredth of a degree."""

from datetime import UTC, datetime

from sqlalchemy import select

from gobernar360.dashboards.economic.models import Actor
from gobernar360.platform.geo.models import RecordZone, Zone, ZoneVersion
from gobernar360.platform.models import Municipality
from tests.factories import (
    admin_session,
    enable_dashboards,
    login,
    make_membership,
    make_municipality,
    make_user,
)

ADMIN = "admin@noetinger.test"
ZONES = "/api/admin/zones"


def at(x: float, y: float) -> list[float]:
    return [round(-62 + x / 100, 6), round(-32 + y / 100, 6)]


def point(x: float, y: float) -> dict:
    return {"type": "Point", "coordinates": at(x, y)}


def line(*points: tuple[float, float]) -> dict:
    return {"type": "LineString", "coordinates": [at(*p) for p in points]}


def ring(x: float, y: float, width: float = 1, height: float | None = None) -> list[list[float]]:
    height = width if height is None else height
    corners = [(x, y), (x + width, y), (x + width, y + height), (x, y + height), (x, y)]
    return [at(*corner) for corner in corners]


def square(x: float, y: float, width: float = 1, height: float | None = None) -> dict:
    """A rectangle whose south-west corner is at x, y."""
    return {"type": "Polygon", "coordinates": [ring(x, y, width, height)]}


def admin_of(municipality: Municipality | None = None, email: str = ADMIN, *dashboards: str):
    """An administrator of the municipality, with those dashboards enabled."""
    municipality = municipality or make_municipality()
    enable_dashboards(municipality, list(dashboards) or ["projects", "economic", "social"])
    make_membership(make_user(email), municipality, admin=True, enable=[])
    return municipality


def signed_in_admin(client, *dashboards: str) -> Municipality:
    municipality = admin_of(None, ADMIN, *dashboards)
    login(client, ADMIN)
    return municipality


def make_zone(
    municipality: Municipality,
    name: str = "Centro",
    boundary: dict | None = None,
    valid_from: datetime | None = None,
) -> Zone:
    """Written through the owner connection, like every builder."""
    polygon = boundary or square(0, 0)
    zone = Zone(municipality_id=municipality.id, name=name)
    with admin_session() as session, session.begin():
        session.add(zone)
        session.flush()
        session.add(
            ZoneVersion(
                municipality_id=municipality.id,
                zone_id=zone.id,
                version=1,
                boundary={"type": "MultiPolygon", "coordinates": [polygon["coordinates"]]},
                valid_from=valid_from or datetime(2020, 1, 1, tzinfo=UTC),
            )
        )
    return zone


def make_actor_at(municipality: Municipality, name: str, location: dict | None, **fields) -> Actor:
    # Loaded long ago unless told otherwise: figures of a past day leave out what was not.
    fields.setdefault("created_at", datetime(2020, 1, 1, tzinfo=UTC))
    actor = Actor(municipality_id=municipality.id, name=name, location=location, **fields)
    with admin_session() as session, session.begin():
        session.add(actor)
    return actor


def zone_names(record) -> list[str]:
    """Names of the zones in use the database has the record in."""
    with admin_session() as session:
        return list(
            session.scalars(
                select(Zone.name)
                .join(ZoneVersion, ZoneVersion.zone_id == Zone.id)
                .join(RecordZone, RecordZone.zone_version_id == ZoneVersion.id)
                .where(RecordZone.record_id == record.id, ZoneVersion.valid_to.is_(None))
                .order_by(Zone.name)
            )
        )
