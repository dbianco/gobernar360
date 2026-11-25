"""The registry of installed dashboards."""

import pytest
from fastapi import APIRouter

from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule, SummaryIndicator


@pytest.fixture(autouse=True)
def installed():
    """Puts back what was installed, whatever the test does to it."""
    modules = registry.all_modules()
    yield
    registry.clear()
    for module in modules:
        registry.register(module)


def make(key: str) -> DashboardModule:
    return DashboardModule(key=key, router=APIRouter(), get_summary=lambda ctx, today: [])


def test_dashboards_are_kept_in_the_order_they_were_installed():
    registry.clear()
    assert registry.all_modules() == []
    first, second = make("zoning"), make("archive")

    registry.register(first)
    registry.register(second)

    assert registry.all_modules() == [first, second]
    assert registry.get_module("archive") is second
    assert registry.get_module("nothing") is None


def test_installing_a_key_again_replaces_it():
    registry.clear()
    registry.register(make("zoning"))
    again = make("zoning")

    registry.register(again)

    assert registry.all_modules() == [again]


def test_one_that_is_not_installed_can_be_removed():
    registry.clear()
    registry.unregister("nothing")
    registry.register(make("zoning"))
    registry.unregister("zoning")

    assert registry.all_modules() == []


def test_a_dashboard_needs_only_its_key_its_routes_and_its_summary():
    module = make("zoning")

    assert (module.alert_kinds, module.get_alerts) == ((), None)
    assert (module.linkable, module.get_commitment_origins) == ((), None)
    assert SummaryIndicator("zoning.plots", 3).unit is None
