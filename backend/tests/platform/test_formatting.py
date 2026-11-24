"""Argentine formats of documents made on the server (`platform/formatting.py`)."""

from datetime import date

import pytest

from gobernar360.platform.formatting import (
    format_change,
    format_date,
    format_indicator,
    format_number,
    month_and_year,
    month_name,
)


def test_months_start_a_line_capitalised_and_go_lower_case_inside_a_sentence():
    assert month_name(10) == "Octubre"
    assert month_and_year(2026, 1) == "enero de 2026"


@pytest.mark.parametrize(
    ("value", "decimals", "written"),
    [
        (1234.5, 2, "1.234,5"),
        (1200000, 2, "1.200.000"),
        (0.4167, 2, "0,42"),
        (-2, 2, "-2"),
        (-0.001, 2, "0"),
        (0, 2, "0"),
        (None, 2, "—"),
        (2.25, 1, "2,2"),
    ],
)
def test_numbers_use_dots_for_thousands_and_a_comma_for_decimals(value, decimals, written):
    assert format_number(value, decimals) == written


def test_indicators_are_written_in_their_unit():
    assert format_indicator(None, "ratio") == "—"
    assert format_indicator(43, "percent") == "43 %"
    assert format_indicator(0.4645, "ratio") == "46,5 %"
    assert format_indicator(3, None) == "3"


def test_changes_carry_their_sign_and_percentage_points():
    assert format_change(None, None) == "—"
    assert format_change(2, None) == "+2"
    assert format_change(-0.0084, "ratio") == "-0,8 p.p."
    assert format_change(3, "percent") == "+3 p.p."
    assert format_change(0, None) == "0"
    assert format_change(0.0001, "ratio") == "0 p.p."


def test_dates_are_day_month_year():
    assert format_date("2026-11-03") == "03/11/2026"
    assert format_date("2026-11-03T14:30:00Z") == "03/11/2026"
    assert format_date(date(2026, 1, 9)) == "09/01/2026"
    assert format_date(None) == "—"
