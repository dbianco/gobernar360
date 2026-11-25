from datetime import date

import pytest
from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform import status
from gobernar360.platform.clock import get_today
from gobernar360.platform.models import AuditLog, DashboardStatus
from tests.factories import admin_session, login, make_membership, make_municipality, make_user

URL = "/api/dashboards/demo/status"


@pytest.fixture(autouse=True)
def pinned_today(client, demo_dashboard):
    client.app.dependency_overrides[get_today] = lambda: date(2025, 6, 15)


def member(client, level: str | None, email: str = "ana@noetinger.test", municipality=None):
    """Sign in a member of Noetinger with the given level on the demo dashboard."""
    municipality = municipality or make_municipality("Noetinger")
    grants = {"demo": level} if level else {}
    make_membership(make_user(email), municipality, grants=grants, enable=["demo"])
    login(client, email)
    return municipality


def make_status(municipality, year: int, month: int, color: str = "green", key: str = "demo"):
    with admin_session() as session, session.begin():
        session.add(
            DashboardStatus(
                municipality_id=municipality.id,
                dashboard_key=key,
                year=year,
                month=month,
                color=color,
            )
        )


def put(client, year: int, month: int, color: str | None):
    return client.put(f"{URL}/{year}/{month}", json={"color": color})


def test_admin_sets_a_month_and_a_viewer_reads_it(client):
    municipality = member(client, "admin")

    assert put(client, 2025, 3, "green").status_code == 204

    member(client, "viewer", "leo@noetinger.test", municipality)
    response = client.get(URL, params={"year": 2025})
    assert response.status_code == 200
    assert response.json() == [{"month": 3, "color": "green"}]


def test_setting_a_month_again_replaces_its_color(client):
    municipality = member(client, "admin")
    put(client, 2025, 3, "green")

    assert put(client, 2025, 3, "red").status_code == 204

    assert client.get(URL, params={"year": 2025}).json() == [{"month": 3, "color": "red"}]
    with tenant_session(municipality.id) as db:
        assert len(db.scalars(select(DashboardStatus)).all()) == 1


def test_null_clears_a_month(client):
    member(client, "admin")
    put(client, 2025, 3, "green")

    assert put(client, 2025, 3, None).status_code == 204

    assert client.get(URL, params={"year": 2025}).json() == []


def test_clearing_a_month_without_a_light_succeeds(client):
    member(client, "admin")

    assert put(client, 2025, 3, None).status_code == 204


def test_months_are_listed_in_calendar_order(client):
    member(client, "admin")
    put(client, 2025, 5, "yellow")
    put(client, 2025, 2, "red")

    assert client.get(URL, params={"year": 2025}).json() == [
        {"month": 2, "color": "red"},
        {"month": 5, "color": "yellow"},
    ]


@pytest.mark.parametrize("level", ["viewer", "editor"])
def test_viewer_and_editor_cannot_set(client, level):
    member(client, level)

    assert put(client, 2025, 3, "green").status_code == 403
    assert client.get(URL, params={"year": 2025}).json() == []


def test_member_without_access_cannot_read(client):
    member(client, None)

    assert client.get(URL, params={"year": 2025}).status_code == 403


def test_unknown_dashboard_key_is_forbidden(client):
    municipality = make_municipality("Noetinger")
    make_membership(make_user("ana@noetinger.test"), municipality, admin=True, enable=["demo"])
    login(client, "ana@noetinger.test")

    response = client.put("/api/dashboards/nope/status/2025/3", json={"color": "green"})

    assert response.status_code == 403
    assert client.get("/api/dashboards/nope/status", params={"year": 2025}).status_code == 403
    with tenant_session(municipality.id) as db:
        assert db.scalars(select(DashboardStatus)).all() == []


def test_a_dashboard_not_enabled_for_the_municipality_is_forbidden(client):
    municipality = make_municipality("Noetinger")
    make_membership(make_user("ana@noetinger.test"), municipality, admin=True, enable=[])
    login(client, "ana@noetinger.test")

    assert put(client, 2025, 3, "green").status_code == 403


def test_a_future_month_is_rejected(client):
    member(client, "admin")

    for year, month in [(2025, 7), (2026, 1)]:
        response = put(client, year, month, "green")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "future_month"
    assert put(client, 2025, 6, "green").status_code == 204


@pytest.mark.parametrize(
    ("year", "month", "color"),
    [(2025, 3, "blue"), (2025, 13, "green"), (2025, 0, "green"), (1800, 3, "green")],
)
def test_invalid_color_month_and_year_are_rejected(client, year, month, color):
    member(client, "admin")

    assert put(client, year, month, color).status_code == 422


def test_lights_of_another_municipality_are_invisible(client):
    make_status(make_municipality("Saira"), 2025, 3, "red")
    member(client, "admin")

    assert client.get(URL, params={"year": 2025}).json() == []
    put(client, 2025, 3, "green")
    assert client.get(URL, params={"year": 2025}).json() == [{"month": 3, "color": "green"}]


def test_other_years_and_other_dashboards_are_not_listed(client):
    municipality = member(client, "admin")
    make_status(municipality, 2024, 3, "red")
    make_status(municipality, 2025, 4, "red", key="other")

    assert client.get(URL, params={"year": 2025}).json() == []


def test_setting_a_month_is_audited(client):
    municipality = member(client, "admin")

    put(client, 2025, 3, "yellow")

    with tenant_session(municipality.id) as db:
        entry = db.scalars(select(AuditLog)).one()
    assert (entry.action, entry.entity_type) == ("create", "dashboard_statuses")
    assert entry.changes == {
        "dashboard_key": "demo",
        "year": 2025,
        "month": 3,
        "color": "yellow",
    }


def test_recent_returns_latest_and_previous_five_months_across_years():
    municipality = make_municipality("Noetinger")
    for year, month in [(2024, 7), (2024, 9), (2024, 12), (2025, 1), (2025, 7)]:
        make_status(municipality, year, month)

    with tenant_session(municipality.id) as db:
        recent = status.recent(db, "demo", date(2025, 1, 20))

    assert [(row.year, row.month) for row in recent] == [(2025, 1), (2024, 12), (2024, 9)]


def test_recent_is_empty_without_lights():
    municipality = make_municipality("Noetinger")

    with tenant_session(municipality.id) as db:
        assert status.recent(db, "demo", date(2025, 1, 20)) == []


def test_a_month_set_by_someone_else_meanwhile_ends_as_one_row(client, monkeypatch):
    municipality = member(client, "admin")
    make_status(municipality, 2025, 3, "green")
    real_find, calls = status.find, []

    def find_missing_the_first_time(*args):
        calls.append(args)
        return None if len(calls) == 1 else real_find(*args)

    monkeypatch.setattr(status, "find", find_missing_the_first_time)

    assert put(client, 2025, 3, "red").status_code == 204

    assert client.get(URL, params={"year": 2025}).json() == [{"month": 3, "color": "red"}]


def test_setting_or_clearing_a_month_touches_only_that_dashboard_year_and_month(client):
    municipality = member(client, "admin")
    others = [("projects", 2025, 3), ("demo", 2024, 3), ("demo", 2025, 4)]
    for key, year, month in others:
        make_status(municipality, year, month, "yellow", key)

    assert put(client, 2025, 3, "red").status_code == 204
    assert put(client, 2025, 3, "green").status_code == 204

    def lights():
        with tenant_session(municipality.id) as db:
            rows = db.scalars(select(DashboardStatus)).all()
        return {(r.dashboard_key, r.year, r.month): r.color for r in rows}

    untouched = dict.fromkeys(others, "yellow")
    assert lights() == untouched | {("demo", 2025, 3): "green"}
    put(client, 2025, 3, None)
    assert lights() == untouched


def test_the_recent_lights_are_the_latest_and_those_of_the_five_months_before(client):
    municipality = member(client, "viewer")
    for month in (1, 2, 3, 4, 5, 6, 7):
        make_status(municipality, 2025, month, "green")
    make_status(municipality, 2024, 12, "red")

    def months(today, **options):
        with tenant_session(municipality.id) as db:
            return [(row.year, row.month) for row in status.recent(db, "demo", today, **options)]

    assert months(date(2025, 6, 15)) == [(2025, month) for month in (6, 5, 4, 3, 2, 1)]
    assert months(date(2025, 2, 1)) == [(2025, 2), (2025, 1), (2024, 12)]
    assert months(date(2025, 6, 15), previous=1) == [(2025, 6), (2025, 5)]
