"""What a dashboard declares about its records that have a place."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel
from sqlalchemy import ColumnElement

from gobernar360.platform.geo.located import LocatedMixin

if TYPE_CHECKING:
    from gobernar360.platform.access import RequestContext

# Levels as `platform.access.AccessLevel` numbers them; importing it here would be circular.
VIEWER = 1
EDITOR = 2


class NoFilters(BaseModel):
    """For records whose list has no filters."""


def _no_conditions(
    ctx: RequestContext, today: date, filters: BaseModel
) -> list[ColumnElement[bool]]:
    return []


@dataclass(frozen=True)
class ZoneMetric:
    """A figure a dashboard gives for every zone, as an SQL aggregate over its records."""

    key: str
    # Built from the filters in use, e.g. to count only what happened in a year.
    aggregate: Callable[[date, Any], ColumnElement[Any]]
    # None for a count, or "money".
    unit: str | None = None


@dataclass(frozen=True)
class ZoneGrouping:
    """Splits the first metric of every zone, e.g. economic actors by sector."""

    key: str
    # Table joined to the record for its name, and how.
    model: type[Any]
    on: Any
    label: Any


@dataclass(frozen=True)
class LocatedRecord:
    """A kind of record with a location. Its model uses LocatedMixin.

    Records whose place is sensitive set `individual_level`: members below it never get a
    record, a location or the zone of one record, only counts per zone, and not those under
    the municipality's threshold (`MunicipalitySettings.small_zone_threshold`).
    """

    # Names the kind in URLs and texts, e.g. "projects".
    key: str
    model: type[LocatedMixin]
    # Column with the name people know the record by.
    title: Any
    metrics: tuple[ZoneMetric, ...]
    # The filters of the record's list. The map and the breakdown accept the same ones.
    filters: type[BaseModel] = NoFilters
    conditions: Callable[[RequestContext, date, Any], list[ColumnElement[bool]]] = _no_conditions
    # The filters the general overview applies. Default: none.
    overview_filters: Callable[[RequestContext, date], BaseModel] | None = None
    grouping: ZoneGrouping | None = None
    individual_level: int = VIEWER

    @property
    def table(self) -> str:
        return self.model.__tablename__
