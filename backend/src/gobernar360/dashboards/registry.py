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


@dataclass(frozen=True)
class SummaryIndicator:
    """One headline number a dashboard contributes to the general overview."""

    key: str
    value: float | int | None
    unit: str | None = None


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
    # Headline indicators for the general overview, as of the given date.
    get_summary: Callable[[RequestContext, date], list[SummaryIndicator]]
    # Kinds of email notification the dashboard raises; users may turn each one off.
    alert_kinds: tuple[str, ...] = ()
    # Current alerts, given a session scoped to one municipality and today's date.
    get_alerts: Callable[[Session, date], list[Alert]] | None = None
    # Records of this dashboard that others may point at.
    linkable: tuple[LinkableRecord, ...] = ()
    # Where the commitments it recorded (`Commitment.source`) were taken, by their id.
    # Only members with access to the dashboard are shown the label and the path.
    get_commitment_origins: (
        Callable[[RequestContext, Collection[uuid.UUID]], dict[uuid.UUID, CommitmentOrigin]] | None
    ) = None


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
