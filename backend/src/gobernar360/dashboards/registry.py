"""Contract every dashboard module implements, and the registry of installed modules."""

from __future__ import annotations

import uuid
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Literal

from fastapi import APIRouter

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from gobernar360.platform.access import RequestContext
    from gobernar360.platform.geo.contract import LocatedRecord


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
class Alert:
    """Something in a dashboard its administrators are told about by email."""

    kind: str
    # Identifies the event. Nobody is emailed twice about the same key.
    event_key: str
    # Placeholders of the kind's `item` text in the backend locale file.
    params: dict[str, str] = field(default_factory=dict)


# The kind of subject every dashboard has without declaring it: one of its months.
MONTH = "month"


@dataclass(frozen=True)
class SubjectRecord:
    """A record of a dashboard as the others show it: its name and where it opens."""

    id: uuid.UUID
    label: str
    # Path in the web app, for whoever may open it.
    path: str


@dataclass(frozen=True)
class LinkableRecord:
    """A kind of record that other modules may point at, e.g. the projects of Projects.

    The functions only read the session's municipality; neither checks who is asking:
    `platform.subjects` does, with `min_level`, before calling or showing anything.
    """

    kind: str
    # Records whose name matches the text typed, at most `limit`, in the order to offer them.
    search: Callable[[RequestContext, str, int], list[SubjectRecord]]
    # The records with these ids; ids that do not exist in the municipality are left out.
    describe: Callable[[RequestContext, Collection[uuid.UUID]], list[SubjectRecord]]
    # Level on the declaring dashboard a member needs to know what the record is.
    min_level: Literal["viewer", "editor", "admin"] = "viewer"

    def __post_init__(self) -> None:
        if self.kind == MONTH:
            raise ValueError(f"{MONTH!r} is every dashboard's own month, not a kind of record.")


@dataclass(frozen=True)
class CommitmentOrigin:
    """Where a dashboard recorded a commitment, e.g. a meeting."""

    label: str
    # Path in the web app, for whoever may open it.
    path: str
    times_postponed: int = 0


@dataclass(frozen=True)
class DashboardModule:
    key: str
    router: APIRouter
    # Headline indicators as of the end of the given date: today for the general overview,
    # the last day of a past month when monthly snapshots are rebuilt.
    get_summary: Callable[[RequestContext, date], list[SummaryIndicator]]
    # Kinds of email notification the dashboard raises; users may turn each one off.
    alert_kinds: tuple[str, ...] = ()
    # Current alerts, given a session scoped to one municipality and today's date.
    get_alerts: Callable[[Session, date], list[Alert]] | None = None
    # Kinds of notice to residents the dashboard asks for (`platform.resident_notices`). Each
    # needs its text, `email.templates.notice.<kind>`.
    notice_kinds: tuple[str, ...] = ()
    # Every indicator get_summary may return. The platform keeps their monthly history
    # and targets without knowing the dashboard.
    indicators: tuple[IndicatorDefinition, ...] = ()
    # The dashboard's name, in Spanish, for documents and pages rendered on the server.
    name: str = ""
    # Tables for a month's report, given the first and last day of the month.
    report_tables: Callable[[RequestContext, date, date], list[ReportTable]] | None = None

    def indicator(self, key: str) -> IndicatorDefinition | None:
        return next((entry for entry in self.indicators if entry.key == key), None)

    # Records of this dashboard that others may point at.
    linkable: tuple[LinkableRecord, ...] = ()
    # Where the commitments it recorded (`Commitment.source`) were taken, by their id.
    # Only members with access to the dashboard are shown the label and the path.
    get_commitment_origins: (
        Callable[[RequestContext, Collection[uuid.UUID]], dict[uuid.UUID, CommitmentOrigin]] | None
    ) = None
    # Records with a place: they get maps, zones and breakdowns by zone from the platform.
    located: tuple[LocatedRecord, ...] = ()


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
