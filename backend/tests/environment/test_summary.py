from datetime import date

from gobernar360.platform.clock import get_today
from tests.environment.factories import (
    BASE,
    environment_member,
    make_subcategory,
    make_value,
    make_variable,
)
from tests.factories import login, make_municipality


def _known_data(municipality):
    """Three variables in 2026: one within its cap, one short of its goal, one without target."""
    energy = make_variable(
        municipality,
        make_subcategory(municipality, "energy", "Consumo"),
        "Consumo eléctrico",
        direction="lower_is_better",
        target=1000,
    )
    make_value(municipality, energy, 2026, 1, 100)
    make_value(municipality, energy, 2026, 2, 150)
    make_value(municipality, energy, 2025, 1, 999)
    water = make_variable(
        municipality,
        make_subcategory(municipality, "water", "Red"),
        "Conexiones nuevas",
        frequency="annual",
        target=200,
    )
    make_value(municipality, water, 2026, 0, 150)
    air = make_variable(
        municipality,
        make_subcategory(municipality, "air", "Calidad"),
        "Material particulado",
        annual_aggregation="average",
    )
    for month, value in ((1, 10), (2, 20), (3, 30)):
        make_value(municipality, air, 2026, month, value)
    return energy, water, air


def test_summary_of_a_year(client):
    municipality = environment_member("viewer")
    _known_data(municipality)
    login(client, "ana@noetinger.test")

    summary = client.get(f"{BASE}/summary", params={"year": 2026}).json()

    totals = {key: summary[key] for key in summary if key != "categories"}
    assert totals == {
        "year": 2026,
        "variable_count": 3,
        "loaded": 6,
        "expected": 25,
        "targets_met": 1,
        "targets_missed": 1,
    }
    assert [c["category"] for c in summary["categories"]] == [
        "energy",
        "waste",
        "water",
        "air",
        "mobility",
        "biodiversity",
        "governance",
    ]
    by_category = {c["category"]: c for c in summary["categories"]}
    assert (by_category["energy"]["loaded"], by_category["energy"]["expected"]) == (2, 12)
    energy = by_category["energy"]["variables"][0]
    assert energy["variable"]["name"] == "Consumo eléctrico"
    assert (energy["value"], energy["achievement"], energy["target_met"]) == (250.0, 1.0, True)
    water = by_category["water"]["variables"][0]
    assert (water["value"], water["loaded"], water["expected"]) == (150.0, 1, 1)
    assert (water["achievement"], water["target_met"]) == (0.75, False)
    air = by_category["air"]["variables"][0]
    assert (air["value"], air["achievement"], air["target_met"]) == (20.0, None, None)
    assert by_category["waste"] == {
        "category": "waste",
        "loaded": 0,
        "expected": 0,
        "variables": [],
    }


def test_summary_defaults_to_the_current_year(client):
    client.app.dependency_overrides[get_today] = lambda: date(2025, 3, 1)
    municipality = environment_member("viewer")
    _known_data(municipality)
    login(client, "ana@noetinger.test")

    summary = client.get(f"{BASE}/summary").json()

    assert (summary["year"], summary["loaded"]) == (2025, 1)


def test_summary_without_variables_lists_every_category_empty(client):
    environment_member("viewer")
    login(client, "ana@noetinger.test")

    summary = client.get(f"{BASE}/summary", params={"year": 2026}).json()

    assert (summary["variable_count"], summary["loaded"], summary["expected"]) == (0, 0, 0)
    assert len(summary["categories"]) == 7
    assert all(category["variables"] == [] for category in summary["categories"])


def test_summary_excludes_other_municipalities_and_requires_access(client):
    other = make_municipality("Saira")
    _known_data(other)
    environment_member("viewer")
    environment_member(None, email="sin@noetinger.test", municipality=make_municipality("Otra"))
    login(client, "ana@noetinger.test")

    assert client.get(f"{BASE}/summary", params={"year": 2026}).json()["variable_count"] == 0
    client.post("/api/auth/logout")
    login(client, "sin@noetinger.test")
    assert client.get(f"{BASE}/summary").status_code == 403


def test_overview_includes_environment_indicators(client):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 6, 15)
    municipality = environment_member("viewer")
    _known_data(municipality)
    login(client, "ana@noetinger.test")

    overview = client.get("/api/overview").json()

    assert overview == [
        {
            "dashboard_key": "environment",
            "indicators": [
                {"key": "environment.variables", "value": 3, "unit": None},
                {"key": "environment.load_completion", "value": 0.24, "unit": "ratio"},
                {"key": "environment.targets_met", "value": 1, "unit": None},
                {"key": "environment.targets_missed", "value": 1, "unit": None},
            ],
            "status": [],
        }
    ]


def test_overview_has_no_environment_indicators_before_any_variable_exists(client):
    environment_member("viewer")
    login(client, "ana@noetinger.test")

    assert client.get("/api/overview").json() == [
        {"dashboard_key": "environment", "indicators": [], "status": []}
    ]
