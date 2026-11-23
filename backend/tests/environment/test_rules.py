from decimal import Decimal

import pytest

from gobernar360.dashboards.environment.rules import (
    achievement,
    annual_value,
    expected_loads,
    target_met,
)

D = Decimal
MONTHS = {1: D("10"), 2: D("20"), 5: D("30")}


@pytest.mark.parametrize(
    ("aggregation", "expected"), [("sum", D("60")), ("average", D("20")), ("last", D("30"))]
)
def test_annual_value_of_monthly_values(aggregation, expected):
    assert annual_value(aggregation, MONTHS) == expected


def test_annual_value_of_a_whole_year_value_is_that_value():
    for aggregation in ("sum", "average", "last"):
        assert annual_value(aggregation, {0: D("7.5")}) == D("7.5")


def test_annual_value_without_values_is_none():
    assert annual_value("sum", {}) is None


def test_expected_loads_per_frequency():
    assert (expected_loads("monthly"), expected_loads("annual")) == (12, 1)


@pytest.mark.parametrize(
    ("direction", "value", "target", "expected"),
    [
        ("higher_is_better", "150", "200", 0.75),
        ("higher_is_better", "250", "200", 1.25),
        ("higher_is_better", "-5", "200", 0.0),
        ("higher_is_better", "10", "0", None),
        ("lower_is_better", "100", "80", 0.8),
        ("lower_is_better", "50", "80", 1.0),
        ("lower_is_better", "0", "80", 1.0),
        ("lower_is_better", "0", "0", 1.0),
        ("lower_is_better", "3", "0", 0.0),
        # A target of one is an ordinary target, not a missing one.
        ("lower_is_better", "2", "1", 0.5),
        ("higher_is_better", "1", "1", 1.0),
        # Four decimals: enough for a percentage with two.
        ("lower_is_better", "3", "1", 0.3333),
        ("higher_is_better", "1", "3", 0.3333),
        ("lower_is_better", "5", "-1", 0.0),
        ("higher_is_better", "5", "-1", None),
    ],
)
def test_achievement(direction, value, target, expected):
    assert achievement(direction, D(value), D(target)) == expected


def test_achievement_needs_a_value_and_a_target():
    assert achievement("higher_is_better", None, D("1")) is None
    assert achievement("higher_is_better", D("1"), None) is None


@pytest.mark.parametrize(
    ("direction", "value", "target", "expected"),
    [
        ("higher_is_better", "200", "200", True),
        ("higher_is_better", "199.9", "200", False),
        ("lower_is_better", "80", "80", True),
        ("lower_is_better", "80.1", "80", False),
    ],
)
def test_target_met(direction, value, target, expected):
    assert target_met(direction, D(value), D(target)) is expected


def test_target_met_needs_a_value_and_a_target():
    assert target_met("lower_is_better", None, D("1")) is None
    assert target_met("lower_is_better", D("1"), None) is None
