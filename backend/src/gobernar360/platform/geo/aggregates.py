"""Figures per zone of a dashboard's located records."""

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, and_, exists, func, select

from gobernar360.platform import municipality_settings
from gobernar360.platform.access import AccessLevel, RequestContext
from gobernar360.platform.geo import zones
from gobernar360.platform.geo.contract import LocatedRecord
from gobernar360.platform.geo.models import RecordZone, Zone, ZoneVersion
from gobernar360.platform.geo.suppression import hidden_cells

MONEY = "money"
# None: hidden from this member.
Value = int | str | None


@dataclass
class Cell:
    """The figures of one zone, or of the records that have none."""

    values: dict[str, Value]
    groups: list[tuple[str | None, int]] = field(default_factory=list)
    suppressed: bool = False


@dataclass
class Breakdown:
    # The past day whose boundaries were used; None: today's.
    boundaries_as_of: date | None
    zones: list[tuple[Zone, Cell]]
    # Located, but in no zone.
    outside: Cell
    # Without a location yet.
    unlocated: Cell
    # Every record once, even those in several zones.
    total: Cell
    # Whether small counts were hidden from this member, and below how many.
    threshold: int | None


def sees_individual(record: LocatedRecord, level: AccessLevel) -> bool:
    return level >= record.individual_level


def in_zone_version(record: LocatedRecord) -> ColumnElement[bool]:
    return and_(
        RecordZone.record_table == record.table,
        RecordZone.record_id == record.model.id,
        RecordZone.zone_version_id == ZoneVersion.id,
    )


def outside_every_zone(record: LocatedRecord, day: date | None = None) -> ColumnElement[bool]:
    return and_(
        record.model.location.is_not(None),
        ~exists().where(in_zone_version(record), zones.in_force(day)),
    )


def _value(value: Any, unit: str | None) -> Value:
    if unit == MONEY:
        return f"{Decimal(value or 0):.2f}"
    return int(value or 0)


def _per_zone(
    record: LocatedRecord, day: date | None, conditions: list[ColumnElement[bool]], *columns: Any
) -> Select[Any]:
    return (
        select(ZoneVersion.zone_id, *columns)
        .select_from(record.model)
        .join(
            RecordZone,
            and_(
                RecordZone.record_table == record.table,
                RecordZone.record_id == record.model.id,
            ),
        )
        .join(ZoneVersion, RecordZone.zone_version_id == ZoneVersion.id)
        .where(zones.in_force(day), *conditions)
        .group_by(ZoneVersion.zone_id)
    )


def _groups(
    ctx: RequestContext,
    record: LocatedRecord,
    day: date | None,
    conditions: list[ColumnElement[bool]],
    aggregate: ColumnElement[Any],
) -> dict[uuid.UUID, list[tuple[str | None, int]]]:
    grouping = record.grouping
    if grouping is None:
        return {}
    query = (
        _per_zone(record, day, conditions, grouping.label, aggregate)
        .outerjoin(grouping.model, grouping.on)
        .group_by(grouping.label)
        .order_by(aggregate.desc(), grouping.label)
    )
    groups: dict[uuid.UUID, list[tuple[str | None, int]]] = defaultdict(list)
    for zone_id, name, count in ctx.db.execute(query):
        groups[zone_id].append((name, count))
    return groups


def by_zone(
    ctx: RequestContext,
    record: LocatedRecord,
    level: AccessLevel,
    filters: BaseModel,
    today: date,
    as_of: date | None = None,
) -> Breakdown:
    """The record's metrics for every zone in force on `as_of` (today when None).

    A record in several zones (a street, or ground two zones share) counts in each.
    """
    day = zones.boundaries_day(ctx.db, as_of, today)
    individual = sees_individual(record, level)
    # Whoever gets only counts cannot narrow them: two searches that differ in one record
    # would tell where it is, however large both counts are.
    conditions = record.conditions(ctx, today, filters) if individual else []
    aggregates = [metric.aggregate(today, filters) for metric in record.metrics]
    columns = [
        aggregate.label(metric.key)
        for metric, aggregate in zip(record.metrics, aggregates, strict=True)
    ]

    def cell(values: Any) -> Cell:
        return Cell(
            {
                metric.key: _value(value, metric.unit)
                for metric, value in zip(record.metrics, values, strict=True)
            }
        )

    def whole(*extra: ColumnElement[bool]) -> Cell:
        query = select(*columns).select_from(record.model).where(*conditions, *extra)
        return cell(ctx.db.execute(query).one())

    rows = {
        zone_id: cell(values)
        for zone_id, *values in ctx.db.execute(_per_zone(record, day, conditions, *columns))
    }
    shown = ctx.db.scalars(
        select(Zone)
        .join(ZoneVersion, ZoneVersion.zone_id == Zone.id)
        .where(zones.in_force(day))
        .order_by(func.unaccent(Zone.name), Zone.id)
    ).all()
    breakdown = Breakdown(
        boundaries_as_of=day,
        zones=[(zone, rows.get(zone.id) or cell([None] * len(columns))) for zone in shown],
        outside=whole(outside_every_zone(record, day)),
        unlocated=whole(record.model.location.is_(None)),
        total=whole(),
        threshold=None,
    )
    if individual:
        groups = _groups(ctx, record, day, conditions, aggregates[0])
        for zone, zone_cell in breakdown.zones:
            zone_cell.groups = groups.get(zone.id, [])
    else:
        threshold = municipality_settings.small_zone_threshold(ctx.db, ctx.municipality_id)
        _suppress(breakdown, record, threshold)
    return breakdown


def _suppress(breakdown: Breakdown, record: LocatedRecord, threshold: int) -> None:
    breakdown.threshold = threshold
    cells = [cell for _, cell in breakdown.zones] + [breakdown.outside, breakdown.unlocated]
    amounts = [metric.key for metric in record.metrics if metric.unit is not None]
    for metric in record.metrics:
        if metric.key in amounts:
            continue
        for index in hidden_cells([cell.values[metric.key] for cell in cells], threshold):
            cells[index].values[metric.key] = None
            cells[index].suppressed = True
            # An amount next to a hidden count would say almost as much as the count.
            cells[index].values.update(dict.fromkeys(amounts))
