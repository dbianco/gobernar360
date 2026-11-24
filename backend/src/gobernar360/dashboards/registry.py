"""Contract every dashboard module implements, and the registry of installed modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

from fastapi import APIRouter

if TYPE_CHECKING:
    from gobernar360.platform.access import RequestContext


@dataclass(frozen=True)
class SummaryIndicator:
    """One headline number a dashboard contributes to the general overview."""

    key: str
    value: float | int | None
    unit: str | None = None


# Units an indicator can have; None is a plain count or amount.
UNITS = (None, "percent", "ratio")


@dataclass(frozen=True)
class IndicatorDefinition:
    """An entry of a dashboard's indicator catalogue.

    `reconstructible` says whether `get_summary` gives an honest value for a past date.
    Only indicators computed from records that carry their own date (a delivery, an
    assignment) are; those that depend on how things stand today (a project's status,
    the actors loaded) are not, and their past months are only known from snapshots
    taken at the time.
    """

    key: str
    unit: str | None = None
    higher_is_better: bool = True
    reconstructible: bool = False
    # Its name, in Spanish, for documents and pages rendered on the server.
    name: str = ""
    # Whether it summarises many records, so it can be shown outside the municipality.
    # Only aggregate indicators can be published; none is unless the dashboard says so.
    aggregate: bool = False

    @property
    def display_name(self) -> str:
        return self.name or self.key


REPORT_COLUMN_KINDS = ("text", "date", "number")


@dataclass(frozen=True)
class ReportColumn:
    title: str
    # How the values are written in the report: dates as ISO strings.
    kind: str = "text"


@dataclass(frozen=True)
class ReportTable:
    """A table a dashboard adds to a month's report, e.g. the milestones reached.

    It must hold no personal data: the report can be handed out and published.
    """

    key: str
    title: str
    columns: tuple[ReportColumn, ...]
    rows: list[tuple[str | int | float | None, ...]] = field(default_factory=list)


@dataclass(frozen=True)
class DashboardModule:
    key: str
    router: APIRouter
    # Headline indicators as of the end of the given date: today for the general overview,
    # the last day of a past month when monthly snapshots are rebuilt.
    get_summary: Callable[[RequestContext, date], list[SummaryIndicator]]
    # Every indicator get_summary may return. The platform keeps their monthly history
    # and targets without knowing the dashboard.
    indicators: tuple[IndicatorDefinition, ...] = ()
    # The dashboard's name, in Spanish, for documents and pages rendered on the server.
    name: str = ""
    # Tables for a month's report, given the first and last day of the month.
    report_tables: Callable[[RequestContext, date, date], list[ReportTable]] | None = None

    def indicator(self, key: str) -> IndicatorDefinition | None:
        return next((entry for entry in self.indicators if entry.key == key), None)


_modules: dict[str, DashboardModule] = {}


def register(module: DashboardModule) -> None:
    _modules[module.key] = module


def unregister(key: str) -> None:
    _modules.pop(key, None)


def clear() -> None:
    _modules.clear()


def all_modules() -> list[DashboardModule]:
    return list(_modules.values())


def get_module(key: str) -> DashboardModule | None:
    return _modules.get(key)


def find_indicator(key: str) -> tuple[DashboardModule, IndicatorDefinition] | None:
    """The installed module that declares an indicator, with its definition."""
    for module in _modules.values():
        definition = module.indicator(key)
        if definition is not None:
            return module, definition
    return None
