"""Contract every dashboard module implements, and the registry of installed modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING

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
