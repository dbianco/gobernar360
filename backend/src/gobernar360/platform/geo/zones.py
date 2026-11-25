"""Creating, moving and comparing zones."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

from sqlalchemy import ColumnElement, func, select, type_coerce
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from gobernar360.core.errors import (
    invalid_boundary,
    not_found,
    zone_changed,
    zone_name_exists,
    zone_self_intersects,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import LOCAL_TIMEZONE
from gobernar360.platform.geo.models import Zone, ZoneVersion
from gobernar360.platform.geo.types import Geometry
from gobernar360.platform.tenant_crud import create_entity, update_entity

# Hand-drawn neighbours never share an exact border; a sliver is not worth reporting.
MIN_OVERLAP_M2 = 10
# Smaller than a house: a slip of the hand, not a zone.
MIN_ZONE_M2 = 10
# What ST_CollectionExtract calls polygons.
POLYGONS = 3


@dataclass(frozen=True)
class Overlap:
    zone: Zone
    other: Zone
    area_m2: float


def _area_m2(geometry: Any) -> ColumnElement[float]:
    return func.ST_Area(func.geography(geometry))


def check_valid(db: Session, boundary: dict[str, Any]) -> None:
    """Refuse a boundary that crosses itself or encloses nothing."""
    geometry = type_coerce(boundary, Geometry())
    valid, reason = db.execute(
        select(func.ST_IsValid(geometry), func.ST_IsValidReason(geometry))
    ).one()
    if not valid:
        raise zone_self_intersects(reason)
    if db.scalar(select(_area_m2(geometry))) < MIN_ZONE_M2:
        raise invalid_boundary("The zone encloses almost no area.")


def is_current() -> ColumnElement[bool]:
    return ZoneVersion.valid_to.is_(None)


def _end_of(day: date) -> datetime:
    return datetime.combine(day + timedelta(days=1), time.min, LOCAL_TIMEZONE)


def boundaries_day(db: Session, as_of: date | None, today: date) -> date | None:
    """The past day whose boundaries answer for `as_of`; None means today's.

    Before the municipality drew its first zone there are no boundaries to go back to, so
    today's are used rather than answering that everything was outside every zone.
    """
    if as_of is None or as_of >= today:
        return None
    first = db.scalar(select(func.min(ZoneVersion.valid_from)))
    return as_of if first is not None and first < _end_of(as_of) else None


def in_force(day: date | None) -> ColumnElement[bool]:
    """Zone versions in force at the end of `day`, or today when it is None."""
    if day is None:
        return is_current()
    moment = _end_of(day)
    return (ZoneVersion.valid_from < moment) & (
        ZoneVersion.valid_to.is_(None) | (ZoneVersion.valid_to >= moment)
    )


def find(db: Session, zone_id: uuid.UUID, for_update: bool = False) -> Zone:
    """A zone in use. Retired ones are only reachable through their versions."""
    query = select(Zone).where(Zone.id == zone_id, Zone.retired_at.is_(None))
    zone = db.scalar(query.with_for_update() if for_update else query)
    if zone is None:
        raise not_found()
    return zone


def current_version(db: Session, zone: Zone) -> ZoneVersion:
    return db.scalars(select(ZoneVersion).where(ZoneVersion.zone_id == zone.id, is_current())).one()


def _add_version(
    ctx: RequestContext, zone: Zone, boundary: dict[str, Any], number: int, moment: datetime
) -> ZoneVersion:
    version = ZoneVersion(zone_id=zone.id, version=number, boundary=boundary, valid_from=moment)
    return create_entity(ctx, version, {"zone_id": zone.id, "version": number})


def _moment(db: Session) -> datetime:
    # Not now(): a transaction that waited for the zone's lock would be earlier than the
    # version it has to close.
    return db.scalar(select(func.clock_timestamp()))


def create(ctx: RequestContext, name: str, boundary: dict[str, Any]) -> Zone:
    check_valid(ctx.db, boundary)
    try:
        with ctx.db.begin_nested():
            zone = create_entity(ctx, Zone(name=name), {"name": name})
    except IntegrityError as error:
        raise zone_name_exists() from error
    _add_version(ctx, zone, boundary, 1, _moment(ctx.db))
    return zone


def rename(ctx: RequestContext, zone: Zone, name: str) -> None:
    try:
        with ctx.db.begin_nested():
            update_entity(ctx, zone, {"name": name})
    except IntegrityError as error:
        raise zone_name_exists() from error


def move(
    ctx: RequestContext, zone: Zone, boundary: dict[str, Any], base_version: int | None = None
) -> bool:
    """Give the zone a new boundary from now on. False when it already had that one.

    `zone` must be locked (`find(..., for_update=True)`). `base_version` is the version the
    person was looking at: moving on top of somebody else's change would undo it unseen.
    """
    check_valid(ctx.db, boundary)
    current = current_version(ctx.db, zone)
    if base_version is not None and base_version != current.version:
        raise zone_changed()
    same = select(func.ST_Equals(ZoneVersion.boundary, type_coerce(boundary, Geometry()))).where(
        ZoneVersion.id == current.id
    )
    if ctx.db.scalar(same):
        return False
    moment = _moment(ctx.db)
    update_entity(ctx, current, {"valid_to": moment})
    _add_version(ctx, zone, boundary, current.version + 1, moment)
    return True


def retire(ctx: RequestContext, zone: Zone) -> None:
    """Stop using a zone from now on; past periods keep it."""
    moment = _moment(ctx.db)
    update_entity(ctx, current_version(ctx.db, zone), {"valid_to": moment})
    update_entity(ctx, zone, {"retired_at": moment})


def overlaps(db: Session, zone_ids: list[uuid.UUID] | None = None) -> list[Overlap]:
    """Pairs of zones in use that share ground, the largest overlap first.

    With `zone_ids`, only the pairs with one of them.
    """
    other = aliased(ZoneVersion)
    # Where two borders also touch, the intersection carries points and lines besides.
    shared_ground = func.ST_CollectionExtract(
        func.ST_Intersection(ZoneVersion.boundary, other.boundary), POLYGONS
    )
    area = _area_m2(shared_ground)
    query = (
        select(ZoneVersion, other, area)
        .join(other, ZoneVersion.zone_id < other.zone_id)
        .where(
            is_current(),
            other.valid_to.is_(None),
            func.ST_Intersects(ZoneVersion.boundary, other.boundary),
            ~func.ST_Touches(ZoneVersion.boundary, other.boundary),
        )
    )
    if zone_ids is not None:
        query = query.where(ZoneVersion.zone_id.in_(zone_ids) | other.zone_id.in_(zone_ids))
    found = [
        Overlap(*sorted((one.zone, two.zone), key=lambda zone: zone.name), round(shared, 1))
        for one, two, shared in db.execute(query)
        if shared >= MIN_OVERLAP_M2
    ]
    return sorted(found, key=lambda pair: (-pair.area_m2, pair.zone.name, pair.other.name))
