"""Figures by zone, their past, and the zone profile of the overview."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from gobernar360.dashboards.social.models import Household
from gobernar360.platform.clock import get_today
from gobernar360.platform.geo import zones
from gobernar360.platform.geo.models import ZoneVersion
from tests.economic.factories import make_sector
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.platform.geo.factories import (
    at,
    make_actor_at,
    make_zone,
    point,
    signed_in_admin,
    square,
)
from tests.projects.factories import make_axis, make_department, make_project, make_term

ACTORS = "/api/dashboards/economic/geo/actors"
PROJECTS = "/api/dashboards/projects/geo/projects"
TODAY = date(2026, 6, 15)


@pytest.fixture(autouse=True)
def pinned_today(client):
    client.app.dependency_overrides[get_today] = lambda: TODAY


def _breakdown(client, base=ACTORS, **params):
    response = client.get(f"{base}/zones", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _by_name(breakdown) -> dict:
    return {row["zone"]["name"]: row["values"] for row in breakdown["zones"]}


def test_economic_actors_by_zone_and_sector(client):
    municipality = signed_in_admin(client)
    food, metal = make_sector(municipality, "Alimentos"), make_sector(municipality, "Metal")
    centro = make_zone(municipality, "Centro", square(0, 0))
    make_zone(municipality, "Ámbito", square(2, 0))
    for name, x, sector in (
        ("A", 0.1, food),
        ("B", 0.2, metal),
        ("C", 0.3, food),
        ("D", 0.4, None),
    ):
        make_actor_at(municipality, name, point(x, 0.5), sector_id=sector.id if sector else None)
    make_actor_at(municipality, "Campo", point(9, 9), sector_id=food.id)
    make_actor_at(municipality, "Sin lugar", None)

    assert _breakdown(client) == {
        "boundaries_as_of": None,
        "metrics": [{"key": "actors", "unit": None}],
        "grouping": "sector",
        "zones": [
            {
                "zone": {"id": _breakdown(client)["zones"][0]["zone"]["id"], "name": "Ámbito"},
                "values": {"actors": 0},
                "groups": [],
                "suppressed": False,
            },
            {
                "zone": {"id": str(centro.id), "name": "Centro"},
                "values": {"actors": 4},
                "groups": [
                    {"name": "Alimentos", "count": 2},
                    {"name": "Metal", "count": 1},
                    {"name": None, "count": 1},
                ],
                "suppressed": False,
            },
        ],
        "outside": {"values": {"actors": 1}, "groups": [], "suppressed": False},
        "unlocated": {"values": {"actors": 1}, "groups": [], "suppressed": False},
        "total": {"values": {"actors": 6}, "groups": [], "suppressed": False},
        "threshold": None,
    }
    assert _by_name(_breakdown(client, sector_id=str(food.id)))["Centro"] == {"actors": 2}


def _projects(municipality):
    term = make_term(municipality)
    axis, department = make_axis(municipality, term), make_department(municipality)

    def add(name, x, **fields):
        return make_project(
            municipality, term, axis, department, name=name, location=point(x, 0.5), **fields
        )

    return term, add


def test_active_projects_and_their_budget_by_zone(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Centro", square(0, 0))
    term, add = _projects(municipality)
    add("Uno", 0.1, status="in_progress", planned_budget=100, executed_budget=10)
    add("Dos", 0.2, status="not_started", planned_budget="50.25")
    add("Listo", 0.3, status="finished", planned_budget=1000, executed_budget=900)
    add("Afuera", 7, status="in_progress", planned_budget=5)

    breakdown = _breakdown(client, PROJECTS, term_id=str(term.id))

    assert breakdown["metrics"] == [
        {"key": "active", "unit": None},
        {"key": "planned_budget", "unit": "money"},
        {"key": "executed_budget", "unit": "money"},
        {"key": "projects", "unit": None},
    ]
    assert _by_name(breakdown) == {
        "Centro": {
            "active": 2,
            "planned_budget": "150.25",
            "executed_budget": "10.00",
            "projects": 3,
        }
    }
    assert breakdown["outside"]["values"]["planned_budget"] == "5.00"
    assert breakdown["total"]["values"]["active"] == 3
    assert breakdown["grouping"] is None


def test_a_new_zone_over_existing_projects_is_added_to_the_breakdown(client):
    municipality = signed_in_admin(client)
    term, add = _projects(municipality)
    add("Uno", 0.1, status="in_progress")
    before = _breakdown(client, PROJECTS)

    client.post("/api/admin/zones", json={"name": "Nueva", "boundary": square(0, 0)})
    after = _breakdown(client, PROJECTS)

    assert (before["zones"], before["outside"]["values"]["active"]) == ([], 1)
    assert (_by_name(after)["Nueva"]["active"], after["outside"]["values"]["active"]) == (1, 0)


# The past


def _set_period(zone, version: int, start: datetime, end: datetime | None) -> None:
    with admin_session() as session, session.begin():
        row = session.query(ZoneVersion).filter_by(zone_id=zone.id, version=version).one()
        row.valid_from, row.valid_to = start, end


def test_moving_a_boundary_does_not_rewrite_the_figures_of_the_past(client):
    municipality = signed_in_admin(client)
    zone = make_zone(municipality, "Centro", square(0, 0), datetime(2024, 1, 1, tzinfo=UTC))
    make_actor_at(municipality, "Viejo", point(0.5, 0.5))
    make_actor_at(municipality, "Nuevo", point(1.5, 0.5))
    make_actor_at(municipality, "Otro nuevo", point(1.6, 0.5))
    client.patch(f"/api/admin/zones/{zone.id}", json={"boundary": square(1, 0), "base_version": 1})
    moved = datetime(2026, 3, 1, 3, tzinfo=UTC)  # midnight in Argentina
    _set_period(zone, 1, datetime(2024, 1, 1, tzinfo=UTC), moved)
    _set_period(zone, 2, moved, None)

    def actors(as_of):
        breakdown = _breakdown(client, **({"as_of": as_of} if as_of else {}))
        return breakdown["boundaries_as_of"], _by_name(breakdown)["Centro"]["actors"]

    assert actors(None) == (None, 2)
    assert actors("2025-12-31") == ("2025-12-31", 1)
    # The last day of the old boundary and the first of the new one.
    assert actors("2026-02-28") == ("2026-02-28", 1)
    assert actors("2026-03-01") == ("2026-03-01", 2)
    # Today and the future are today's boundaries.
    assert actors("2026-06-15") == actors("2030-01-01") == (None, 2)
    assert actors("2026-06-14") == ("2026-06-14", 2)
    # The map of a past day is drawn with the boundaries its figures used.
    [then] = client.get("/api/zones", params={"as_of": "2025-12-31"}).json()
    [now] = client.get("/api/zones").json()
    assert (then["id"], then["version"]) == (str(zone.id), 1)
    assert (now["version"], now["boundary"]["coordinates"][0][0][0]) == (2, at(1, 0))


def test_a_retired_zone_stays_in_the_figures_of_when_it_was_used(client):
    municipality = signed_in_admin(client)
    old = make_zone(municipality, "Vieja", square(0, 0), datetime(2024, 1, 1, tzinfo=UTC))
    make_actor_at(municipality, "Taller", point(0.5, 0.5))
    client.delete(f"/api/admin/zones/{old.id}")
    _set_period(old, 1, datetime(2024, 1, 1, tzinfo=UTC), datetime(2026, 2, 1, tzinfo=UTC))
    make_zone(municipality, "Nueva", square(0, 0), datetime(2026, 2, 1, tzinfo=UTC))

    assert _by_name(_breakdown(client)) == {"Nueva": {"actors": 1}}
    assert _by_name(_breakdown(client, as_of="2025-12-31")) == {"Vieja": {"actors": 1}}
    assert _breakdown(client, as_of="2025-12-31")["outside"]["values"] == {"actors": 0}


def test_before_the_first_zone_todays_boundaries_are_used(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Centro", square(0, 0), datetime(2026, 5, 1, tzinfo=UTC))
    make_actor_at(municipality, "Taller", point(0.5, 0.5))

    breakdown = _breakdown(client, as_of="2025-12-31")

    assert (breakdown["boundaries_as_of"], _by_name(breakdown)) == (
        None,
        {"Centro": {"actors": 1}},
    )


def test_without_zones_everything_is_outside(client):
    municipality = signed_in_admin(client)
    make_actor_at(municipality, "Taller", point(0.5, 0.5))

    breakdown = _breakdown(client, as_of="2025-12-31")

    assert (breakdown["zones"], breakdown["boundaries_as_of"]) == ([], None)
    assert breakdown["outside"]["values"] == {"actors": 1}


def test_a_day_ends_at_midnight_in_argentina():
    assert zones.end_of(date(2025, 12, 31)) == datetime(2026, 1, 1, 3, tzinfo=UTC)


def test_what_was_loaded_after_a_past_day_is_not_in_its_figures(client):
    municipality = signed_in_admin(client)
    food, metal = make_sector(municipality, "Alimentos"), make_sector(municipality, "Metal")
    make_zone(municipality, "Centro", square(0, 0))
    # Midnight in Argentina: the end of April and the start of May.
    edge = datetime(2026, 5, 1, 3, tzinfo=UTC)
    before, after = edge - timedelta(seconds=1), edge

    def load(name, x, sector, created_at):
        location = None if x is None else point(x, 0.5)
        make_actor_at(municipality, name, location, sector_id=sector.id, created_at=created_at)

    for name, x in (("Centro", 0.1), ("Afuera", 7), ("Sin lugar", None)):
        load(f"{name} viejo", x, food, before)
        load(f"{name} nuevo", x, metal, after)

    def figures(as_of):
        body = _breakdown(client, **({"as_of": as_of} if as_of else {}))
        cells = [body["zones"][0], body["outside"], body["unlocated"], body["total"]]
        groups = [group["name"] for group in body["zones"][0]["groups"]]
        return [cell["values"]["actors"] for cell in cells], groups

    assert figures("2026-04-30") == ([1, 1, 1, 3], ["Alimentos"])
    assert figures("2026-05-01") == ([2, 2, 2, 6], ["Alimentos", "Metal"])
    assert figures(None) == figures("2026-06-15") == figures("2026-05-01")


def test_today_counts_what_was_loaded_today(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Centro", square(0, 0))
    # The test's today is long before the moment it runs.
    make_actor_at(municipality, "Nuevo", point(0.5, 0.5), created_at=datetime.now(UTC))

    assert _by_name(_breakdown(client)) == {"Centro": {"actors": 1}}
    assert _by_name(_breakdown(client, as_of="2026-06-15")) == {"Centro": {"actors": 1}}
    assert _by_name(_breakdown(client, as_of="2026-06-14")) == {"Centro": {"actors": 0}}


# CSV


def test_the_breakdown_downloads_as_csv(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "=Centro", square(0, 0))
    make_actor_at(municipality, "Taller", point(0.5, 0.5))
    make_actor_at(municipality, "Campo", point(5, 5))

    response = client.get(f"{ACTORS}/zones.csv", params={"q": "a"})

    assert 'filename="economic-actors-by-zone.csv"' in response.headers["content-disposition"]
    assert response.text.lstrip("\ufeff").splitlines() == [
        "zone,actors",
        "'=Centro,1",
        "(outside),1",
        "(no location),0",
        "(total),2",
    ]


# Zone profile


def _profile(client, zone):
    response = client.get(f"/api/overview/zones/{zone.id}")
    assert response.status_code == 200, response.text
    return response.json()


def test_the_zone_profile_combines_the_dashboards_the_member_can_see(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Otra", square(5, 5))
    zone = make_zone(municipality, "Centro", square(0, 0))
    sector = make_sector(municipality, "Alimentos")
    make_actor_at(municipality, "Taller", point(0.5, 0.5), sector_id=sector.id)
    term, add = _projects(municipality)
    add("Uno", 0.1, status="in_progress", planned_budget=100)
    old = make_term(municipality, "Vieja", 2015, 2019)
    make_project(
        municipality,
        old,
        make_axis(municipality, old),
        make_department(municipality),
        location=point(0.5, 0.5),
    )
    make_membership(
        make_user("leo@noetinger.test"), municipality, grants={"economic": "viewer"}, enable=[]
    )

    profile = _profile(client, zone)
    client.post("/api/auth/logout")
    login(client, "leo@noetinger.test")

    assert profile["zone"] == {"id": str(zone.id), "name": "Centro"}
    sections = {s["dashboard_key"]: s for s in profile["sections"]}
    assert list(sections) == ["economic", "projects", "social"]
    assert sections["economic"] == {
        "dashboard_key": "economic",
        "record_key": "actors",
        "metrics": [{"key": "actors", "unit": None}],
        "grouping": "sector",
        "values": {"actors": 1},
        "groups": [{"name": "Alimentos", "count": 1}],
        "suppressed": False,
        "threshold": None,
    }
    # Of the most recent term only, as the overview's indicators.
    assert sections["projects"]["values"]["projects"] == 1
    assert sections["social"]["values"] == {"households": 0, "assisted": 0}
    assert [s["dashboard_key"] for s in _profile(client, zone)["sections"]] == ["economic"]


def test_the_zone_profile_of_a_zone_that_is_not_the_municipalitys(client):
    municipality = signed_in_admin(client)
    retired = make_zone(municipality)
    theirs = make_zone(make_municipality("Saira"))
    client.delete(f"/api/admin/zones/{retired.id}")

    for zone in (retired, theirs):
        assert client.get(f"/api/overview/zones/{zone.id}").status_code == 404


def test_the_zone_profile_without_terms_has_no_projects(client):
    municipality = signed_in_admin(client, "projects")
    zone = make_zone(municipality)

    [section] = _profile(client, zone)["sections"]

    assert section["values"]["projects"] == 0


def test_files_list_the_place_of_each_record_and_no_other(client):
    from gobernar360.dashboards.economic.models import Actor
    from gobernar360.platform.geo.export import places_of

    municipality = signed_in_admin(client)
    one = make_actor_at(municipality, "Uno", point(0.5, 0.25))
    make_actor_at(municipality, "Dos", point(1.5, 0.5))
    nowhere = make_actor_at(municipality, "Nada", None)

    with admin_session() as session:
        places = places_of(session, Actor, [one.id, nowhere.id])

    longitude, latitude = at(0.5, 0.25)
    assert places == {one.id: (latitude, longitude)}


def test_the_overview_filters_of_a_record_know_the_day(client, monkeypatch):
    """They may depend on it, as a dashboard that looks at the current year would."""
    from gobernar360.platform.geo import profile_router

    seen = []

    class Record:
        def overview_filters(ctx, today):
            seen.append(today)
            return "filters"

    assert profile_router._overview_filters(None, Record, TODAY) == "filters"
    assert seen == [TODAY]


# What a breakdown counts and what it does not


def test_the_filters_apply_to_every_row_of_a_breakdown(client):
    municipality = signed_in_admin(client)
    food, metal = make_sector(municipality, "Alimentos"), make_sector(municipality, "Metal")
    make_zone(municipality, "Centro", square(0, 0))
    for sector in (food, metal, metal):
        make_actor_at(municipality, "Adentro", point(0.5, 0.5), sector_id=sector.id)
        make_actor_at(municipality, "Afuera", point(9, 9), sector_id=sector.id)
        make_actor_at(municipality, "Sin lugar", None, sector_id=sector.id)

    breakdown = _breakdown(client, sector_id=str(food.id))

    assert _by_name(breakdown) == {"Centro": {"actors": 1}}
    for row, expected in (("outside", 1), ("unlocated", 1), ("total", 3)):
        assert breakdown[row]["values"] == {"actors": expected}, row
    assert breakdown["zones"][0]["groups"] == [{"name": "Alimentos", "count": 1}]


def test_every_figure_of_a_past_day_uses_the_boundaries_of_that_day(client):
    municipality = signed_in_admin(client)
    food, metal = make_sector(municipality, "Alimentos"), make_sector(municipality, "Metal")
    zone = make_zone(municipality, "Centro", square(0, 0), datetime(2024, 1, 1, tzinfo=UTC))
    make_actor_at(municipality, "Viejo", point(0.5, 0.5), sector_id=food.id)
    for name in ("Nuevo", "Otro"):
        make_actor_at(municipality, name, point(1.5, 0.5), sector_id=metal.id)
    client.patch(f"/api/admin/zones/{zone.id}", json={"boundary": square(1, 0), "base_version": 1})
    moved = datetime(2026, 3, 1, tzinfo=UTC)
    _set_period(zone, 1, datetime(2024, 1, 1, tzinfo=UTC), moved)
    _set_period(zone, 2, moved, None)

    then, now = _breakdown(client, as_of="2025-12-31"), _breakdown(client)

    assert then["zones"][0]["groups"] == [{"name": "Alimentos", "count": 1}]
    assert now["zones"][0]["groups"] == [{"name": "Metal", "count": 2}]
    assert (then["outside"]["values"]["actors"], now["outside"]["values"]["actors"]) == (2, 1)


def test_groups_come_largest_first_and_then_by_name(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Centro", square(0, 0))
    for name, count in (("Zinc", 3), ("Textil", 1), ("Agro", 1), ("Bienes", 2)):
        sector = make_sector(municipality, name)
        for _ in range(count):
            make_actor_at(municipality, "A", point(0.5, 0.5), sector_id=sector.id)

    [row] = _breakdown(client)["zones"]

    assert [(group["name"], group["count"]) for group in row["groups"]] == [
        ("Zinc", 3),
        ("Bienes", 2),
        ("Agro", 1),
        ("Textil", 1),
    ]


def test_records_of_different_kinds_do_not_stand_for_each_other(client):
    """Assignments of every kind share a table, told apart by the kind."""
    municipality = signed_in_admin(client)
    zone = make_zone(municipality, "Centro", square(0, 0))
    shared = uuid.uuid4()
    make_actor_at(municipality, "Taller", point(0.5, 0.5), id=shared)
    with admin_session() as session, session.begin():
        session.add(
            Household(id=shared, municipality_id=municipality.id, name="F", location=point(9, 9))
        )

    households = _breakdown(client, "/api/dashboards/social/geo/households")

    assert _by_name(households)["Centro"]["households"] == 0
    assert households["outside"]["values"]["households"] == 1
    assert _by_name(_breakdown(client)) == {zone.name: {"actors": 1}}
    unzoned = client.get("/api/dashboards/social/geo/households/unzoned").json()
    assert unzoned["total"] == 1


def test_zones_with_the_same_name_once_are_told_apart(client):
    """A name is free once its zone is retired, so two may share it in the past."""
    municipality = signed_in_admin(client)
    past = datetime(2024, 1, 1, tzinfo=UTC)
    first = make_zone(municipality, "Centro", square(0, 0), past)
    client.delete(f"/api/admin/zones/{first.id}")
    second = make_zone(municipality, "Centro", square(2, 0), past)
    _set_period(first, 1, past, datetime(2026, 5, 1, tzinfo=UTC))

    rows = _breakdown(client, as_of="2025-12-31")["zones"]

    assert [row["zone"]["id"] for row in rows] == sorted([str(first.id), str(second.id)])


def test_amounts_without_records_are_zero(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Centro", square(0, 0))

    breakdown = _breakdown(client, PROJECTS)

    assert _by_name(breakdown)["Centro"] == {
        "active": 0,
        "planned_budget": "0.00",
        "executed_budget": "0.00",
        "projects": 0,
    }
    assert breakdown["total"]["values"]["planned_budget"] == "0.00"


def test_conditions_that_depend_on_the_day_get_it(client):
    municipality = signed_in_admin(client)
    make_zone(municipality, "Centro", square(0, 0))
    _, add = _projects(municipality)
    add("Atrasado", 0.1, status="in_progress", end_date=TODAY - timedelta(days=1))
    add("En fecha", 0.2, status="in_progress", end_date=TODAY)

    assert _by_name(_breakdown(client, PROJECTS, status="delayed"))["Centro"]["projects"] == 1
    assert _by_name(_breakdown(client, PROJECTS, status="in_progress"))["Centro"]["projects"] == 1


def test_the_overview_takes_the_most_recent_term_and_the_first_by_name_of_several(client):
    municipality = signed_in_admin(client, "projects")
    zone = make_zone(municipality, "Centro", square(0, 0))
    # By name alone the oldest would come first.
    for name, start, projects in (("A", 2015, 1), ("C", 2023, 2), ("B", 2023, 3)):
        term = make_term(municipality, name, start, start + 4)
        axis, department = make_axis(municipality, term), make_department(municipality)
        for _ in range(projects):
            make_project(municipality, term, axis, department, location=point(0.5, 0.5))

    [section] = _profile(client, zone)["sections"]

    assert section["values"]["projects"] == 3
