import csv
import io
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


def _rows(response):
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text.removeprefix("﻿"))))


def test_values_csv_lists_the_values_of_the_year(client):
    municipality = environment_member("viewer")
    subcategory = make_subcategory(municipality, "energy", "Consumo")
    monthly = make_variable(municipality, subcategory, "Consumo eléctrico")
    annual = make_variable(municipality, subcategory, "Luminarias LED", frequency="annual", unit="")
    make_value(municipality, monthly, 2026, 2, "1500.5")
    make_value(municipality, monthly, 2026, 1, 1000)
    make_value(municipality, monthly, 2025, 1, 1)
    make_value(municipality, annual, 2026, 0, 40)
    other = make_municipality("Saira")
    make_value(other, make_variable(other, name="Ajena"), 2026, 1, 5)
    login(client, "ana@noetinger.test")

    response = client.get(f"{BASE}/export/values.csv", params={"year": 2026})

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert 'filename="environment-values-2026.csv"' in response.headers["content-disposition"]
    assert _rows(response) == [
        ["category", "subcategory", "variable", "unit", "frequency", "year", "period", "value"],
        ["energy", "Consumo", "Consumo eléctrico", "kWh", "monthly", "2026", "1", "1000"],
        ["energy", "Consumo", "Consumo eléctrico", "kWh", "monthly", "2026", "2", "1500.5"],
        ["energy", "Consumo", "Luminarias LED", "", "annual", "2026", "", "40"],
    ]


def test_values_csv_neutralises_formulas_in_names(client):
    municipality = environment_member("viewer")
    variable = make_variable(
        municipality, make_subcategory(municipality, "air", "+Aire"), "=HYPERLINK(1)", unit="@u"
    )
    make_value(municipality, variable, 2026, 1, -3)
    login(client, "ana@noetinger.test")

    row = _rows(client.get(f"{BASE}/export/values.csv", params={"year": 2026}))[1]

    assert row[1:4] == ["'+Aire", "'=HYPERLINK(1)", "'@u"]
    assert row[-1] == "-3"


def test_values_csv_requires_access(client):
    environment_member(None)
    login(client, "ana@noetinger.test")

    assert client.get(f"{BASE}/export/values.csv").status_code == 403


def test_values_csv_is_of_the_year_asked_or_the_current_one_in_the_order_of_the_screens(client):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 6, 15)
    municipality = environment_member("viewer")
    login(client, "ana@noetinger.test")
    for category, name, variable in (
        ("water", "A", "Uno"),
        ("energy", "B", "Dos"),
        ("energy", "A", "Zeta"),
        ("energy", "A", "Beta"),
    ):
        made = make_variable(municipality, make_subcategory(municipality, category, name), variable)
        for year, month in ((2026, 2), (2026, 1), (2025, 1)):
            make_value(municipality, made, year, month, 1)

    def rows(**params):
        _, *found = _rows(client.get(f"{BASE}/export/values.csv", params=params))
        return [(row[0], row[1], row[2], row[6]) for row in found]

    order = [
        ("energy", "A", "Beta"),
        ("energy", "A", "Zeta"),
        ("energy", "B", "Dos"),
        ("water", "A", "Uno"),
    ]
    assert rows() == [(*variable, month) for variable in order for month in ("1", "2")]
    assert rows(year=2025) == [(*variable, "1") for variable in order]
