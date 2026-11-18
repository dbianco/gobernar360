"""Contract every dashboard module implements, and the registry of installed modules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
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


@dataclass(frozen=True)
class DashboardModule:
    key: str
    router: APIRouter
    get_summary: Callable[[RequestContext], list[SummaryIndicator]]


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
