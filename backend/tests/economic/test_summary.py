from datetime import date

from gobernar360.platform.clock import get_today
from tests.economic.factories import (
    BASE,
    EMAIL,
    economic_member,
    make_actor,
    make_actor_type,
    make_assignment,
    make_economic_person,
    make_person,
    make_sector,
    make_tool,
    make_tool_category,
)
from tests.factories import login, make_municipality


def _viewer(client, today=date(2026, 6, 15)):
    client.app.dependency_overrides[get_today] = lambda: today
    municipality = economic_member("viewer")
    login(client, EMAIL)
    return municipality


def _populate(municipality):
    """Two tools, three actors, three people; assignments in 2026 and one in 2025."""
    finance = make_tool_category(municipality, "Financiamiento")
    training = make_tool_category(municipality, "Capacitación")
    credit = make_tool(municipality, finance, "Microcrédito")
    course = make_tool(municipality, training, "Curso de costos")
    shop = make_actor_type(municipality, "Comercio")
    food = make_sector(municipality, "Alimentos")
    bakery = make_actor(municipality, "Panadería", actor_type_id=shop.id, sector_id=food.id)
    kiosk = make_actor(municipality, "Kiosco", actor_type_id=shop.id)
    make_actor(municipality, "Taller")
    juana = make_economic_person(municipality, "Juana", "Pérez", "employed")
    luis = make_economic_person(municipality, "Luis", "Acosta", "unemployed")
    make_economic_person(municipality, "Ana", "Luna", "employed")
    make_person(municipality, "Solo", "Padrón")
    make_assignment(municipality, credit, actor=bakery, on=date(2026, 1, 10))
    make_assignment(municipality, credit, actor=bakery, on=date(2026, 3, 2))
    make_assignment(municipality, course, actor=kiosk, on=date(2026, 3, 20))
    make_assignment(municipality, course, person=juana, on=date(2026, 3, 21))
    make_assignment(municipality, course, person=luis, on=date(2026, 12, 31))
    make_assignment(municipality, credit, person=juana, on=date(2026, 12, 1))
    make_assignment(municipality, course, person=juana, on=date(2026, 7, 1))
    make_assignment(municipality, credit, actor=kiosk, on=date(2025, 12, 31))


def test_summary_counts_records_and_recipients_of_the_year(client):
    municipality = _viewer(client)
    _populate(municipality)
    other = make_municipality("Saira")
    make_assignment(other, make_tool(other), actor=make_actor(other))

    response = client.get(f"{BASE}/summary", params={"year": 2026})

    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "actors": {"total": 3, "with_assignments": 2},
        "people": {"total": 3, "with_assignments": 2},
        "tools": 2,
        "assignments": 7,
        "actor_tools": [
            {"tool": "Microcrédito", "category": "Financiamiento", "count": 2},
            {"tool": "Curso de costos", "category": "Capacitación", "count": 1},
        ],
        "person_tools": [
            {"tool": "Curso de costos", "category": "Capacitación", "count": 3},
            {"tool": "Microcrédito", "category": "Financiamiento", "count": 1},
        ],
    }


def test_summary_defaults_to_the_current_year(client):
    municipality = _viewer(client, today=date(2025, 12, 31))
    _populate(municipality)

    body = client.get(f"{BASE}/summary").json()

    assert (body["year"], body["assignments"]) == (2025, 1)
    assert body["actors"] == {"total": 3, "with_assignments": 1}
    assert body["person_tools"] == []


def test_summary_of_an_empty_dashboard(client):
    _viewer(client)

    assert client.get(f"{BASE}/summary", params={"year": 2026}).json() == {
        "year": 2026,
        "actors": {"total": 0, "with_assignments": 0},
        "people": {"total": 0, "with_assignments": 0},
        "tools": 0,
        "assignments": 0,
        "actor_tools": [],
        "person_tools": [],
    }
    assert client.get(f"{BASE}/summary", params={"year": 1800}).status_code == 422


def test_reports_group_actors_people_and_assignments(client):
    municipality = _viewer(client)
    _populate(municipality)

    response = client.get(f"{BASE}/reports", params={"year": 2026})

    assert response.status_code == 200
    body = response.json()
    assert body["year"] == 2026
    assert body["actors_by_type"] == [
        {"name": "Comercio", "count": 2},
        {"name": None, "count": 1},
    ]
    assert body["actors_by_sector"] == [
        {"name": None, "count": 2},
        {"name": "Alimentos", "count": 1},
    ]
    assert body["people_by_employment_status"] == [
        {"status": "employed", "count": 2},
        {"status": "unemployed", "count": 1},
    ]
    assert body["assignments_by_category"] == [
        {"name": "Capacitación", "count": 4},
        {"name": "Financiamiento", "count": 3},
    ]
    assert [m["count"] for m in body["assignments_by_month"]] == [
        1,
        0,
        3,
        0,
        0,
        0,
        1,
        0,
        0,
        0,
        0,
        2,
    ]
    assert [m["month"] for m in body["assignments_by_month"]] == list(range(1, 13))


def test_summary_and_reports_require_access(client):
    economic_member(None)
    login(client, EMAIL)

    assert client.get(f"{BASE}/summary").status_code == 403
    assert client.get(f"{BASE}/reports").status_code == 403


def test_overview_shows_the_economic_indicators(client):
    municipality = _viewer(client)
    _populate(municipality)

    assert client.get("/api/overview").json() == [
        {
            "dashboard_key": "economic",
            "indicators": [
                {"key": "economic.actors", "value": 3, "unit": None},
                {"key": "economic.people", "value": 3, "unit": None},
                {"key": "economic.tools", "value": 2, "unit": None},
                {"key": "economic.assignments_year", "value": 7, "unit": None},
            ],
            "status": [],
        }
    ]


def test_overview_of_an_empty_economic_dashboard_has_no_indicators(client):
    _viewer(client)

    assert client.get("/api/overview").json() == [
        {"dashboard_key": "economic", "indicators": [], "status": []}
    ]


def test_ties_are_listed_by_name(client):
    municipality = _viewer(client)
    finance = make_tool_category(municipality, "Financiamiento")
    zeta, alfa = make_tool(municipality, finance, "Zeta"), make_tool(municipality, finance, "Alfa")
    industry, shop = (
        make_actor_type(municipality, "Industria"),
        make_actor_type(municipality, "Comercio"),
    )
    services, food = make_sector(municipality, "Servicios"), make_sector(municipality, "Alimentos")
    first = make_actor(municipality, "Uno", actor_type_id=industry.id, sector_id=services.id)
    second = make_actor(municipality, "Dos", actor_type_id=shop.id, sector_id=food.id)
    make_assignment(municipality, zeta, actor=first, on=date(2026, 2, 1))
    make_assignment(municipality, alfa, actor=second, on=date(2026, 2, 1))

    summary = client.get(f"{BASE}/summary", params={"year": 2026}).json()
    reports = client.get(f"{BASE}/reports", params={"year": 2026}).json()

    assert [row["tool"] for row in summary["actor_tools"]] == ["Alfa", "Zeta"]
    assert summary["person_tools"] == []
    assert [row["name"] for row in reports["actors_by_type"]] == ["Comercio", "Industria"]
    assert [row["name"] for row in reports["actors_by_sector"]] == ["Alimentos", "Servicios"]
