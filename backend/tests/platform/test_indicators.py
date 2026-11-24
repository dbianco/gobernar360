"""Indicator evolution, targets and combined indicators (`platform/indicators*.py`)."""

from datetime import date

import pytest
from sqlalchemy import select

from gobernar360.dashboards import registry
from gobernar360.platform import indicators
from gobernar360.platform.clock import get_today
from gobernar360.platform.models import AuditLog, IndicatorSnapshot, IndicatorTarget
from tests.conftest import DEMO_STATE
from tests.economic.factories import make_actor
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.procedures.factories import make_procedure
from tests.projects.factories import make_axis, make_department, make_project, make_term
from tests.social.factories import make_benefit, make_delivery, make_social_person

TODAY = date(2026, 3, 15)
DEMO = "/api/dashboards/demo"


@pytest.fixture(autouse=True)
def pinned_today(client):
    client.app.dependency_overrides[get_today] = lambda: TODAY


def member(client, grants=None, admin=False, enable=(), email="ana@noetinger.test"):
    """Sign in a member of Noetinger. The demo dashboard, the granted ones and those in
    `enable` are enabled."""
    municipality = make_municipality("Noetinger")
    grants = grants or {}
    enabled = ["demo", *grants, *enable]
    make_membership(make_user(email), municipality, admin=admin, grants=grants, enable=enabled)
    login(client, email)
    return municipality


def snapshot(municipality, key: str, year: int, month: int, value, dashboard: str = "demo"):
    with admin_session() as session, session.begin():
        session.add(
            IndicatorSnapshot(
                municipality_id=municipality.id,
                dashboard_key=dashboard,
                indicator_key=key,
                year=year,
                month=month,
                value=value,
            )
        )


def target(municipality, key: str, year: int, value, dashboard: str = "demo"):
    with admin_session() as session, session.begin():
        session.add(
            IndicatorTarget(
                municipality_id=municipality.id,
                dashboard_key=dashboard,
                indicator_key=key,
                year=year,
                value=value,
            )
        )


def by_key(items) -> dict:
    return {item["key"]: item for item in items}


# Deviation and direction


@pytest.mark.parametrize(
    ("value", "goal", "expected", "met"),
    [(6, 4, -2, False), (3, 4, 1, True), (4, 4, 0, True)],
)
def test_lower_is_better_deviation_is_negative_above_the_target(value, goal, expected, met):
    assert indicators.deviation(value, goal, higher_is_better=False) == expected
    assert indicators.on_track(value, goal, higher_is_better=False) is met


@pytest.mark.parametrize(
    ("value", "goal", "expected", "met"),
    [(10, 12, -2, False), (13, 12, 1, True), (0.5, 0.4, 0.1, True)],
)
def test_higher_is_better_deviation_is_negative_below_the_target(value, goal, expected, met):
    assert indicators.deviation(value, goal, higher_is_better=True) == expected
    assert indicators.on_track(value, goal, higher_is_better=True) is met


def test_without_a_value_or_a_target_there_is_no_deviation():
    assert indicators.deviation(None, 4, higher_is_better=False) is None
    assert indicators.deviation(4, None, higher_is_better=True) is None
    assert indicators.on_track(None, 4, higher_is_better=True) is None


# Evolution of a dashboard


def test_evolution_compares_today_with_last_month_and_last_year(client, demo_dashboard):
    municipality = member(client, {"demo": "viewer"})
    snapshot(municipality, "demo.state", 2026, 2, 9)
    snapshot(municipality, "demo.state", 2025, 3, 12)
    snapshot(municipality, "demo.state", 2025, 2, 99)  # Outside the twelve months shown.

    response = client.get(f"{DEMO}/evolution")

    assert response.status_code == 200
    state = by_key(response.json())["demo.state"]
    assert state["value"] == DEMO_STATE
    assert state["higher_is_better"] is False
    assert state["reconstructible"] is False
    assert (state["previous_value"], state["change_previous_month"]) == (9, DEMO_STATE - 9)
    assert (state["last_year_value"], state["change_last_year"]) == (12, DEMO_STATE - 12)
    assert [(p["year"], p["month"]) for p in state["series"]] == [
        (2025, 4),
        (2025, 5),
        (2025, 6),
        (2025, 7),
        (2025, 8),
        (2025, 9),
        (2025, 10),
        (2025, 11),
        (2025, 12),
        (2026, 1),
        (2026, 2),
        (2026, 3),
    ]
    assert [p["value"] for p in state["series"]][-2:] == [9, DEMO_STATE]
    assert all(p["value"] is None for p in state["series"][:-2])


def test_evolution_lists_the_whole_catalogue_in_order(client, demo_dashboard):
    member(client, {"demo": "viewer"})

    evolution = client.get(f"{DEMO}/evolution").json()

    assert [item["key"] for item in evolution] == ["demo.day", "demo.state"]
    assert evolution[0]["value"] == TODAY.day


def test_a_target_below_the_value_of_a_lower_is_better_indicator_is_missed(client, demo_dashboard):
    member(client, {"demo": "admin"})

    response = client.put(f"{DEMO}/targets/2026/demo.state", json={"value": 4})

    assert response.status_code == 204
    state = by_key(client.get(f"{DEMO}/evolution").json())["demo.state"]
    assert state["target"] == 4
    assert state["deviation"] == 4 - DEMO_STATE
    assert state["deviation_ratio"] == round((4 - DEMO_STATE) / 4, 4)
    assert state["on_track"] is False
    client.put(f"{DEMO}/targets/2026/demo.state", json={"value": 8})
    state = by_key(client.get(f"{DEMO}/evolution").json())["demo.state"]
    assert (state["deviation"], state["on_track"]) == (1, True)


def test_the_target_line_follows_the_year_of_each_month(client, demo_dashboard):
    municipality = member(client, {"demo": "viewer"})
    target(municipality, "demo.day", 2025, 10)
    target(municipality, "demo.day", 2026, 20)

    day = by_key(client.get(f"{DEMO}/evolution").json())["demo.day"]

    assert day["target"] == 20
    assert [p["target"] for p in day["series"]] == [10] * 9 + [20] * 3
    assert (day["deviation"], day["on_track"]) == (TODAY.day - 20, False)


def test_evolution_of_another_municipality_is_not_visible(client, demo_dashboard):
    member(client, {"demo": "viewer"})
    saira = make_municipality("Saira")
    snapshot(saira, "demo.state", 2026, 2, 1)
    target(saira, "demo.state", 2026, 1)

    state = by_key(client.get(f"{DEMO}/evolution").json())["demo.state"]

    assert state["previous_value"] is None
    assert state["target"] is None


READ_PATHS = ["/evolution", "/evolution/months?year=2026", "/targets?year=2026"]


@pytest.mark.parametrize("path", READ_PATHS)
def test_reading_needs_access_to_the_dashboard(client, demo_dashboard, path):
    member(client, {})

    assert client.get(f"{DEMO}{path}").status_code == 403
    assert client.get(f"/api/dashboards/unknown{path}").status_code == 403


# Numbers of each month, next to the status lights


def test_each_month_of_the_year_has_its_recorded_numbers(client, demo_dashboard):
    municipality = member(client, {"demo": "viewer"})
    snapshot(municipality, "demo.day", 2026, 1, 31)
    snapshot(municipality, "demo.state", 2026, 2, None)
    snapshot(municipality, "demo.state", 2025, 2, 5)

    response = client.get(f"{DEMO}/evolution/months", params={"year": 2026})

    assert response.status_code == 200
    body = response.json()
    assert body["year"] == 2026
    assert [i["key"] for i in body["indicators"]] == ["demo.day", "demo.state"]
    months = {m["month"]: m["values"] for m in body["months"]}
    assert sorted(months) == list(range(1, 13))
    assert months[1] == {"demo.day": 31}
    assert months[2] == {"demo.state": None}
    # The current month, as of today; later ones are empty.
    assert months[3] == {"demo.day": TODAY.day, "demo.state": DEMO_STATE}
    assert months[4] == {}
    other_year = client.get(f"{DEMO}/evolution/months", params={"year": 2025}).json()
    assert {m["month"]: m["values"] for m in other_year["months"]}[2] == {"demo.state": 5}


# Targets


def test_admin_sets_changes_and_clears_a_target(client, demo_dashboard):
    member(client, {"demo": "admin"})
    url = f"{DEMO}/targets/2026/demo.day"

    assert client.put(url, json={"value": 12.5}).status_code == 204
    assert client.put(url, json={"value": 14}).status_code == 204
    listed = by_key(client.get(f"{DEMO}/targets", params={"year": 2026}).json())
    assert listed["demo.day"]["target"] == 14
    assert listed["demo.state"]["target"] is None
    assert listed["demo.state"]["higher_is_better"] is False
    assert client.get(f"{DEMO}/targets", params={"year": 2025}).json()[0]["target"] is None

    assert client.put(url, json={"value": None}).status_code == 204
    assert client.put(url, json={"value": None}).status_code == 204
    listed = by_key(client.get(f"{DEMO}/targets", params={"year": 2026}).json())
    assert listed["demo.day"]["target"] is None


def test_setting_a_target_is_audited(client, demo_dashboard):
    municipality = member(client, {"demo": "admin"})

    client.put(f"{DEMO}/targets/2026/demo.day", json={"value": 3})

    with admin_session() as session:
        entry = session.scalar(select(AuditLog).where(AuditLog.entity_type == "indicator_targets"))
    assert entry.municipality_id == municipality.id
    assert entry.action == "create"
    assert entry.changes["value"] == 3


@pytest.mark.parametrize("level", ["viewer", "editor"])
def test_only_dashboard_admins_set_targets(client, demo_dashboard, level):
    member(client, {"demo": level})

    assert client.put(f"{DEMO}/targets/2026/demo.day", json={"value": 3}).status_code == 403


def test_a_municipality_admin_sets_targets_of_every_dashboard(client, demo_dashboard):
    member(client, admin=True)

    assert client.put(f"{DEMO}/targets/2026/demo.day", json={"value": 3}).status_code == 204


def test_a_target_needs_an_indicator_of_that_dashboard(client, demo_dashboard):
    member(client, {"demo": "admin"})

    response = client.put(f"{DEMO}/targets/2026/projects.delayed", json={"value": 3})

    assert response.status_code == 404
    assert client.put(f"{DEMO}/targets/2026/nothing", json={"value": 3}).status_code == 404


@pytest.mark.parametrize(
    ("year", "body"),
    [(2026, {"value": 1e15}), (2026, {"value": "mucho"}), (2026, {}), (1800, {"value": 1})],
)
def test_an_invalid_target_is_rejected(client, demo_dashboard, year, body):
    member(client, {"demo": "admin"})

    response = client.put(f"{DEMO}/targets/{year}/demo.day", json=body)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_targets_of_another_municipality_are_invisible(client, demo_dashboard):
    member(client, {"demo": "admin"})
    target(make_municipality("Saira"), "demo.day", 2026, 99)

    assert client.get(f"{DEMO}/targets", params={"year": 2026}).json()[0]["target"] is None
    # Setting ours does not touch theirs.
    assert client.put(f"{DEMO}/targets/2026/demo.day", json={"value": 1}).status_code == 204
    with admin_session() as session:
        assert sorted(session.scalars(select(IndicatorTarget.value))) == [1, 99]


# The general overview


def test_overview_indicators_carry_their_evolution(client, demo_dashboard):
    municipality = member(client, {"demo": "viewer"})
    snapshot(municipality, "demo.state", 2026, 2, 9)
    target(municipality, "demo.state", 2026, 8)

    section = client.get("/api/overview").json()[0]

    assert section["dashboard_key"] == "demo"
    state = by_key(section["indicators"])["demo.state"]
    assert state["value"] == DEMO_STATE
    assert state["change_previous_month"] == DEMO_STATE - 9
    assert (state["target"], state["on_track"]) == (8, True)
    assert len(state["series"]) == 12


def _combined_data(municipality):
    """Two online procedures, four actors, six deliveries and three active projects."""
    for name in ("Libre deuda", "Plan de pago"):
        make_procedure(municipality, name=name, channel="online")
    make_procedure(municipality, name="Habilitación", channel="in_person")
    for n in range(4):
        make_actor(municipality, f"Actor {n}")
    person, benefit = make_social_person(municipality), make_benefit(municipality)
    for day in range(1, 7):
        make_delivery(municipality, benefit, person, on=date(2026, 2, day))
    term = make_term(municipality, start_year=2025, end_year=2029)
    axis, department = make_axis(municipality, term), make_department(municipality)
    for name in ("Uno", "Dos", "Tres"):
        make_project(municipality, term, axis, department, name=name)


ALL_FOUR = {"procedures": "viewer", "economic": "viewer", "social": "viewer", "projects": "viewer"}


def test_combined_indicators_relate_two_dashboards(client):
    municipality = member(client, ALL_FOUR)
    _combined_data(municipality)
    snapshot(municipality, "procedures.online", 2026, 2, 1, "procedures")
    snapshot(municipality, "economic.actors", 2026, 2, 4, "economic")

    response = client.get("/api/overview/combined")

    assert response.status_code == 200
    combined = by_key(response.json())
    assert list(combined) == [
        "combined.online_procedures_per_actor",
        "combined.deliveries_per_active_project",
    ]
    online = combined["combined.online_procedures_per_actor"]
    assert online["dashboard_keys"] == ["procedures", "economic"]
    assert online["value"] == 0.5
    assert online["higher_is_better"] is True
    assert (online["previous_value"], online["change_previous_month"]) == (0.25, 0.25)
    assert online["target"] is None
    deliveries = combined["combined.deliveries_per_active_project"]
    assert deliveries["dashboard_keys"] == ["social", "projects"]
    assert deliveries["value"] == 2
    assert deliveries["higher_is_better"] is None
    assert deliveries["previous_value"] is None


def test_a_combined_indicator_is_hidden_from_a_member_lacking_one_of_its_dashboards(client):
    without_economic = {key: level for key, level in ALL_FOUR.items() if key != "economic"}
    municipality = member(client, without_economic, enable=["economic"])
    _combined_data(municipality)

    keys = [item["key"] for item in client.get("/api/overview/combined").json()]

    assert keys == ["combined.deliveries_per_active_project"]


def test_a_member_with_a_single_dashboard_sees_no_combined_indicator(client):
    member(client, {"projects": "admin"})

    assert client.get("/api/overview/combined").json() == []


def test_a_combined_indicator_needs_both_dashboards_enabled(client):
    # An administrator sees every enabled dashboard, but projects and economic are not.
    member(client, admin=True, enable=["social", "procedures"])

    assert client.get("/api/overview/combined").json() == []


def test_combined_indicators_need_a_signed_in_member(client):
    assert client.get("/api/overview/combined").status_code == 401


# The catalogue contract


def test_every_dashboard_declares_its_catalogue(client):
    for module in registry.all_modules():
        keys = [definition.key for definition in module.indicators]
        assert keys, module.key
        assert len(keys) == len(set(keys)), module.key
        assert all(key.startswith(f"{module.key}.") for key in keys), module.key
        assert all(d.unit in registry.UNITS for d in module.indicators), module.key


def test_combined_indicators_are_built_from_catalogue_keys(client):
    for combined in indicators.COMBINED_INDICATORS:
        assert combined.dashboards() is not None, combined.key
        assert combined.key.startswith("combined."), combined.key
