import pytest

from tests.contract import administrator, check_reference, check_trace, write
from tests.environment.factories import BASE, make_subcategory, make_value, make_variable


def test_what_is_created_leaves_a_trace_of_what_it_was(client):
    municipality = administrator(client, "environment")
    subcategory = make_subcategory(municipality)
    variable = make_variable(municipality, subcategory, frequency="monthly")

    for method, path, body in (
        ("POST", "subcategories", {"category": "water", "name": "Calidad"}),
        (
            "POST",
            "variables",
            {"subcategory_id": str(subcategory.id), "name": "Luz", "frequency": "annual"},
        ),
        (
            "PUT",
            "values",
            {"variable_id": str(variable.id), "year": 2025, "period": 3, "value": 7.0},
        ),
    ):
        check_trace(client, method, f"{BASE}/{path}", body, "create")


def test_ids_that_are_not_the_municipality_s_are_refused_by_name(client):
    municipality = administrator(client, "environment")
    variable = make_variable(municipality, make_subcategory(municipality))

    for method, path, body, field in (
        ("POST", "variables", {"name": "Luz", "frequency": "annual"}, "subcategory_id"),
        ("PATCH", f"variables/{variable.id}", {}, "subcategory_id"),
        ("PUT", "values", {"year": 2025, "period": 3, "value": 1}, "variable_id"),
    ):
        check_reference(client, method, f"{BASE}/{path}", body, field)


@pytest.mark.parametrize(("frequency", "period"), [("monthly", 0), ("annual", 1), ("annual", 12)])
def test_a_value_is_for_a_period_of_its_variable(client, frequency, period):
    municipality = administrator(client, "environment")
    variable = make_variable(municipality, make_subcategory(municipality), frequency=frequency)
    body = {"variable_id": str(variable.id), "year": 2025, "period": period, "value": 1}

    refused = client.put(f"{BASE}/values", json=body)

    assert refused.status_code == 422
    assert refused.json()["error"] == {
        "code": "validation_error",
        "message": "period does not match the variable's frequency.",
    }


def test_setting_a_value_touches_only_that_variable_year_and_month(client):
    municipality = administrator(client, "environment")
    subcategory = make_subcategory(municipality)
    ours, other = (
        make_variable(municipality, subcategory, name=name, frequency="monthly")
        for name in ("A", "B")
    )
    for variable, year, month in (
        (ours, 2025, 1),
        (ours, 2025, 2),
        (ours, 2024, 1),
        (other, 2025, 1),
    ):
        make_value(municipality, variable, year, month, 10)

    body = {"variable_id": str(ours.id), "year": 2025, "period": 1, "value": 99}
    write(client, "PUT", f"{BASE}/values", body)

    def values(year):
        rows = client.get(f"{BASE}/values", params={"year": year}).json()
        return {(r["variable_id"], r["period"]): float(r["value"]) for r in rows}

    assert values(2025) == {
        (str(ours.id), 1): 99,
        (str(ours.id), 2): 10,
        (str(other.id), 1): 10,
    }
    assert values(2024) == {(str(ours.id), 1): 10}


def test_values_come_by_variable_and_period(client):
    municipality = administrator(client, "environment")
    subcategory = make_subcategory(municipality)
    variables = [
        make_variable(municipality, subcategory, name=name, frequency="monthly")
        for name in ("A", "B", "C")
    ]
    for month in (12, 1, 7):
        for variable in reversed(variables):
            make_value(municipality, variable, 2025, month, month)

    rows = client.get(f"{BASE}/values", params={"year": 2025}).json()

    found = [(row["variable_id"], row["period"]) for row in rows]
    assert found == sorted(found)


def test_subcategories_are_listed_by_name(client):
    municipality = administrator(client, "environment")
    for name in ("Renovables", "Consumo", "Pérdidas"):
        make_subcategory(municipality, name=name)

    names = [item["name"] for item in client.get(f"{BASE}/subcategories").json()]

    assert names == ["Consumo", "Pérdidas", "Renovables"]
