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


def _editor(client):
    municipality = environment_member("editor")
    login(client, "ana@noetinger.test")
    return municipality


def _put(client, variable, period=3, value="12.5", year=2026):
    return client.put(
        f"{BASE}/values",
        json={"variable_id": str(variable.id), "year": year, "period": period, "value": value},
    )


def test_editor_loads_and_replaces_a_value(client):
    municipality = _editor(client)
    variable = make_variable(municipality)

    first = _put(client, variable, value="12.5")
    second = _put(client, variable, value="20")

    assert (first.status_code, second.status_code) == (200, 200)
    assert client.get(f"{BASE}/values", params={"year": 2026}).json() == [
        {"variable_id": str(variable.id), "year": 2026, "period": 3, "value": 20.0}
    ]


def test_null_value_clears_the_period(client):
    municipality = _editor(client)
    variable = make_variable(municipality)
    _put(client, variable)

    cleared = _put(client, variable, value=None)
    cleared_again = _put(client, variable, value=None)

    assert (cleared.status_code, cleared_again.status_code) == (204, 204)
    assert client.get(f"{BASE}/values", params={"year": 2026}).json() == []


def test_zero_is_a_value_not_an_empty_period(client):
    municipality = _editor(client)
    variable = make_variable(municipality)

    _put(client, variable, value="0")

    assert client.get(f"{BASE}/values", params={"year": 2026}).json()[0]["value"] == 0.0


def test_viewer_cannot_load_values(client):
    municipality = environment_member("viewer")
    variable = make_variable(municipality)
    login(client, "ana@noetinger.test")

    assert _put(client, variable).status_code == 403
    assert client.get(f"{BASE}/values", params={"year": 2026}).status_code == 200


def test_period_must_match_the_variable_frequency(client):
    municipality = _editor(client)
    subcategory = make_subcategory(municipality)
    monthly = make_variable(municipality, subcategory, "Mensual")
    annual = make_variable(municipality, subcategory, "Anual", frequency="annual")

    assert _put(client, monthly, period=0).status_code == 422
    assert _put(client, annual, period=3).status_code == 422
    assert _put(client, annual, period=0).status_code == 200
    assert _put(client, monthly, period=12).status_code == 200


def test_out_of_range_period_year_and_number_are_rejected(client):
    municipality = _editor(client)
    variable = make_variable(municipality)

    assert _put(client, variable, period=13).status_code == 422
    assert _put(client, variable, period=-1).status_code == 422
    assert _put(client, variable, year=99999).status_code == 422
    assert _put(client, variable, value="1" + "0" * 20).status_code == 422
    assert _put(client, variable, value="abc").status_code == 422
    assert client.get(f"{BASE}/values", params={"year": 99999999999}).status_code == 422
    assert client.get(f"{BASE}/summary", params={"year": 99999999999}).status_code == 422


def test_value_cannot_reference_variable_of_another_municipality(client):
    other = make_municipality("Saira")
    foreign = make_variable(other)
    _editor(client)

    response = _put(client, foreign)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"


def test_values_of_another_municipality_are_not_listed(client):
    other = make_municipality("Saira")
    make_value(other, make_variable(other), 2026, 1, 99)
    _editor(client)

    assert client.get(f"{BASE}/values", params={"year": 2026}).json() == []


def test_values_can_be_filtered_by_variable_and_year(client):
    municipality = _editor(client)
    subcategory = make_subcategory(municipality)
    first = make_variable(municipality, subcategory, "Uno")
    second = make_variable(municipality, subcategory, "Dos")
    make_value(municipality, first, 2026, 1, 1)
    make_value(municipality, first, 2025, 1, 2)
    make_value(municipality, second, 2026, 1, 3)

    values = client.get(
        f"{BASE}/values", params={"year": 2026, "variable_id": str(first.id)}
    ).json()

    assert [v["value"] for v in values] == [1.0]


def test_series_of_a_monthly_variable(client):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 6, 15)
    municipality = _editor(client)
    variable = make_variable(municipality, annual_aggregation="average", target=15)
    make_value(municipality, variable, 2025, 1, 10)
    make_value(municipality, variable, 2026, 2, 20)
    make_value(municipality, variable, 2026, 4, 40)

    series = client.get(f"{BASE}/variables/{variable.id}/series").json()
    older = client.get(f"{BASE}/variables/{variable.id}/series", params={"year": 2025}).json()

    assert series["year"] == 2026
    assert series["variable"]["id"] == str(variable.id)
    assert [point["period"] for point in series["monthly"]] == list(range(1, 13))
    assert [point["value"] for point in series["monthly"]][:4] == [None, 20.0, None, 40.0]
    assert series["annual"] == [
        {"year": 2025, "value": 10.0, "loaded": 1, "expected": 12},
        {"year": 2026, "value": 30.0, "loaded": 2, "expected": 12},
    ]
    assert older["monthly"][0] == {"period": 1, "value": 10.0}


def test_series_of_an_annual_variable_has_no_months(client):
    municipality = _editor(client)
    variable = make_variable(municipality, frequency="annual")
    make_value(municipality, variable, 2024, 0, 5)

    series = client.get(f"{BASE}/variables/{variable.id}/series").json()

    assert series["monthly"] == []
    assert series["annual"] == [{"year": 2024, "value": 5.0, "loaded": 1, "expected": 1}]


def test_series_of_a_variable_of_another_municipality_is_not_found(client):
    other = make_municipality("Saira")
    foreign = make_variable(other)
    _editor(client)

    assert client.get(f"{BASE}/variables/{foreign.id}/series").status_code == 404
