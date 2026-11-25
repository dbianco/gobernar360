from datetime import date

from gobernar360.platform.clock import get_today
from tests.factories import login, make_municipality
from tests.social.factories import (
    BASE,
    EMAIL,
    make_benefit,
    make_benefit_category,
    make_delivery,
    make_household,
    make_intervention,
    make_intervention_type,
    make_person,
    make_social_person,
    social_member,
)


def _viewer(client, today=date(2026, 6, 15)):
    client.app.dependency_overrides[get_today] = lambda: today
    municipality = social_member("viewer")
    login(client, EMAIL)
    return municipality


def _populate(municipality):
    """Four people in two households; five deliveries and three interventions in 2026."""
    food = make_benefit_category(municipality, "Alimentos")
    housing = make_benefit_category(municipality, "Hábitat")
    box = make_benefit(municipality, food, "Módulo alimentario")
    milk = make_benefit(municipality, food, "Leche")
    sheets = make_benefit(municipality, housing, "Chapas")
    visit = make_intervention_type(municipality, "Visita a domicilio")
    interview = make_intervention_type(municipality, "Entrevista")
    make_intervention_type(municipality, "Acompañamiento")
    perez = make_household(municipality, "Familia Pérez")
    gomez = make_household(municipality, "Familia Gómez")
    juana = make_social_person(
        municipality, "Juana", "Pérez", household=perez, relationship="head", neighborhood="Centro"
    )
    ana = make_social_person(
        municipality, "Ana", "Pérez", household=perez, relationship="child", neighborhood="Centro"
    )
    luis = make_social_person(
        municipality, "Luis", "Gómez", household=gomez, relationship="head", neighborhood="Norte"
    )
    marta = make_social_person(municipality, "Marta", "Ruiz")
    make_person(municipality, "Solo", "Padrón", neighborhood="Centro")
    make_delivery(municipality, box, juana, on=date(2026, 1, 10), quantity=2)
    make_delivery(municipality, box, juana, on=date(2026, 3, 2))
    make_delivery(municipality, box, luis, on=date(2026, 3, 20))
    make_delivery(municipality, sheets, luis, on=date(2026, 3, 21), quantity=10)
    make_delivery(municipality, milk, marta, on=date(2026, 12, 31), quantity=3)
    make_delivery(municipality, box, ana, on=date(2025, 12, 31), quantity=5)
    make_intervention(municipality, visit, juana, on=date(2026, 2, 1))
    make_intervention(municipality, visit, luis, on=date(2026, 3, 5))
    make_intervention(municipality, interview, juana, on=date(2026, 3, 6))
    make_intervention(municipality, interview, marta, on=date(2025, 6, 1))


def test_summary_counts_the_current_year(client):
    municipality = _viewer(client)
    _populate(municipality)
    other = make_municipality("Saira")
    make_delivery(other, make_benefit(other), make_social_person(other))

    response = client.get(f"{BASE}/summary")

    assert response.status_code == 200
    assert response.json() == {
        "year": 2026,
        "people": 4,
        "households": 2,
        "people_with_deliveries": 3,
        "deliveries": 5,
        "units": 17,
        "interventions": 3,
        "people_with_interventions": 2,
        "benefits": [
            {"benefit": "Módulo alimentario", "category": "Alimentos", "deliveries": 3, "units": 4},
            {"benefit": "Chapas", "category": "Hábitat", "deliveries": 1, "units": 10},
            {"benefit": "Leche", "category": "Alimentos", "deliveries": 1, "units": 3},
        ],
        "intervention_types": [
            {"name": "Visita a domicilio", "count": 2},
            {"name": "Entrevista", "count": 1},
        ],
    }


def test_summary_of_another_year(client):
    municipality = _viewer(client)
    _populate(municipality)

    body = client.get(f"{BASE}/summary", params={"year": 2025}).json()

    assert (body["year"], body["people"], body["households"]) == (2025, 4, 2)
    assert (body["deliveries"], body["units"], body["people_with_deliveries"]) == (1, 5, 1)
    assert (body["interventions"], body["people_with_interventions"]) == (1, 1)
    assert body["intervention_types"] == [{"name": "Entrevista", "count": 1}]
    assert client.get(f"{BASE}/summary", params={"year": 1800}).status_code == 422


def test_summary_of_an_empty_dashboard(client):
    _viewer(client)

    assert client.get(f"{BASE}/summary").json() == {
        "year": 2026,
        "people": 0,
        "households": 0,
        "people_with_deliveries": 0,
        "deliveries": 0,
        "units": 0,
        "interventions": 0,
        "people_with_interventions": 0,
        "benefits": [],
        "intervention_types": [],
    }


def test_reports_break_the_year_down(client):
    municipality = _viewer(client)
    _populate(municipality)

    response = client.get(f"{BASE}/reports")

    assert response.status_code == 200
    body = response.json()
    assert body["year"] == 2026
    assert body["deliveries_by_category"] == [
        {"name": "Alimentos", "count": 4},
        {"name": "Hábitat", "count": 1},
    ]
    assert body["interventions_by_type"] == [
        {"name": "Visita a domicilio", "count": 2},
        {"name": "Entrevista", "count": 1},
    ]
    assert body["people_by_neighborhood"] == [
        {"name": "Centro", "count": 2},
        {"name": "Norte", "count": 1},
        {"name": None, "count": 1},
    ]
    assert body["deliveries_by_neighborhood"] == [
        {"name": "Centro", "count": 2},
        {"name": "Norte", "count": 2},
        {"name": None, "count": 1},
    ]
    assert [m["count"] for m in body["deliveries_by_month"]] == [1, 0, 3, 0, 0, 0, 0, 0, 0, 0, 0, 1]
    assert [m["count"] for m in body["interventions_by_month"]] == [0, 1, 2] + [0] * 9
    assert [m["month"] for m in body["deliveries_by_month"]] == list(range(1, 13))


def test_summary_and_reports_need_access(client):
    social_member(None)
    login(client, EMAIL)

    assert client.get(f"{BASE}/summary").status_code == 403
    assert client.get(f"{BASE}/reports").status_code == 403


def test_overview_shows_the_social_indicators(client):
    municipality = _viewer(client)
    _populate(municipality)

    assert client.get("/api/overview").json() == [
        {
            "dashboard_key": "social",
            "indicators": [
                {"key": "social.people", "value": 4, "unit": None},
                {"key": "social.households", "value": 2, "unit": None},
                {"key": "social.deliveries_year", "value": 5, "unit": None},
                {"key": "social.interventions_year", "value": 3, "unit": None},
            ],
            "status": [],
        }
    ]


def test_overview_of_an_empty_social_dashboard_has_no_indicators(client):
    _viewer(client)

    assert client.get("/api/overview").json() == [
        {"dashboard_key": "social", "indicators": [], "status": []}
    ]


def test_reports_put_the_largest_first_and_ties_by_name(client):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 6, 15)
    municipality = social_member("viewer")
    login(client, EMAIL)
    people = {
        name: [make_social_person(municipality, neighborhood=name) for _ in range(count)]
        for name, count in (("Oeste", 1), ("Sur", 3), ("Centro", 1), ("Norte", 2))
    }
    for category, count in (("Salud", 1), ("Abrigo", 1), ("Vivienda", 3), ("Alimentos", 2)):
        benefit = make_benefit(
            municipality, make_benefit_category(municipality, category), category
        )
        for index in range(count):
            neighborhood = ("Sur", "Norte", "Oeste")[index]
            make_delivery(municipality, benefit, people[neighborhood][0])

    report = client.get(f"{BASE}/reports").json()

    def pairs(key):
        return [(row["name"], row["count"]) for row in report[key]]

    assert pairs("deliveries_by_category") == [
        ("Vivienda", 3),
        ("Alimentos", 2),
        ("Abrigo", 1),
        ("Salud", 1),
    ]
    assert pairs("people_by_neighborhood") == [
        ("Sur", 3),
        ("Norte", 2),
        ("Centro", 1),
        ("Oeste", 1),
    ]
    assert pairs("deliveries_by_neighborhood") == [("Sur", 4), ("Norte", 2), ("Oeste", 1)]
