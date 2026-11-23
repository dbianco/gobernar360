"""The backend's texts for people: complete, and filled only with what they ask for."""

import pytest

from gobernar360.dashboards import registry
from gobernar360.platform.texts import dashboard_name, has_text, month_name, text


def test_every_installed_dashboard_has_a_name_for_emails(client):
    for module in registry.all_modules():
        assert has_text(f"dashboards.{module.key}"), module.key


def test_a_missing_placeholder_is_an_error_not_a_blank():
    with pytest.raises(KeyError):
        text("dateTime", date="1/1/2027")


def test_texts_are_spanish_and_filled_in():
    filled = text("dateTime", date="01/01/2027", time="10:30")

    assert filled == "01/01/2027 a las 10:30"
    assert (dashboard_name("procedures"), month_name(1)) == ("Trámites", "enero")


def test_a_moment_is_written_in_argentine_time():
    from datetime import UTC, datetime

    from gobernar360.platform.texts import format_datetime

    # 02:30 UTC is still the previous evening in Argentina (UTC-3).
    assert format_datetime(datetime(2026, 3, 1, 2, 30, tzinfo=UTC)) == "28/02/2026 a las 23:30"
    assert format_datetime(datetime(2026, 7, 9, 15, 5, tzinfo=UTC)) == "09/07/2026 a las 12:05"


def test_only_texts_that_exist_are_reported_as_existing():
    assert has_text("dashboards.projects")
    assert not has_text("dashboards.lottery")
    assert not has_text("dashboards")


def test_a_missing_or_incomplete_text_says_which_one():
    with pytest.raises(KeyError, match="Missing text: nowhere.at.all"):
        text("nowhere.at.all")
    with pytest.raises(KeyError, match="Missing text: dashboards.projects.more"):
        text("dashboards.projects.more")
    with pytest.raises(KeyError, match="Not a text: dashboards"):
        text("dashboards")
    with pytest.raises(KeyError, match="Text dateTime needs time"):
        text("dateTime", date="01/01/2027")


def test_the_month_before_january_is_december_of_the_year_before():
    from datetime import date

    from gobernar360.platform.notifications import previous_month

    assert previous_month(date(2026, 1, 15)) == (2025, 12)
    assert previous_month(date(2026, 3, 1)) == (2026, 2)
