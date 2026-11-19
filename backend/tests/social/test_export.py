import csv
import io
from datetime import date

import pytest

from gobernar360.platform.clock import get_today
from tests.factories import login, make_municipality
from tests.social.factories import (
    BASE,
    EMAIL,
    make_benefit,
    make_delivery,
    make_household,
    make_intervention,
    make_intervention_type,
    make_person,
    make_social_person,
    social_member,
)

SECRET = "Refiere situación de violencia en el hogar."
EXPORTS = ("people", "households", "deliveries", "interventions")


def _rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text.removeprefix("﻿"))))


def _member(client, level="viewer"):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 6, 15)
    municipality = social_member(level)
    login(client, EMAIL)
    return municipality


def test_people_csv_lists_the_people_of_the_dashboard(client):
    municipality = _member(client)
    household = make_household(municipality)
    make_social_person(
        municipality,
        "Juana",
        "Pérez",
        household=household,
        relationship="head",
        dni="12345678",
        birth_date=date(1990, 5, 1),
        phone="+54 3472 555",
        email="juana@example.test",
        address="=HYPERLINK(1)",
        neighborhood="Centro",
    )
    make_social_person(municipality, "Luis", "Gómez")
    make_person(municipality, "Solo", "Padrón")
    make_social_person(make_municipality("Saira"), "Ajena", "Persona")

    response = client.get(f"{BASE}/export/people.csv")

    assert 'filename="social-people.csv"' in response.headers["content-disposition"]
    assert _rows(response) == [
        [
            "last_name",
            "first_name",
            "dni",
            "birth_date",
            "phone",
            "email",
            "address",
            "neighborhood",
            "household",
            "relationship",
        ],
        ["Gómez", "Luis", "", "", "", "", "", "", "", ""],
        [
            "Pérez",
            "Juana",
            "12345678",
            "1990-05-01",
            "'+54 3472 555",
            "juana@example.test",
            "'=HYPERLINK(1)",
            "Centro",
            "Familia Pérez",
            "head",
        ],
    ]


def test_households_csv_lists_each_household(client):
    municipality = _member(client)
    perez = make_household(municipality, "Familia Pérez", address="Belgrano 45", neighborhood="Sur")
    make_household(municipality, "Familia Gómez")
    make_social_person(municipality, household=perez, relationship="head")
    make_social_person(municipality, "Ana", household=perez, relationship="child")
    make_household(make_municipality("Saira"), "Ajena")

    response = client.get(f"{BASE}/export/households.csv")

    assert 'filename="social-households.csv"' in response.headers["content-disposition"]
    assert _rows(response) == [
        ["name", "address", "neighborhood", "members", "head"],
        ["Familia Gómez", "", "", "0", ""],
        ["Familia Pérez", "Belgrano 45", "Sur", "2", "Pérez, Juana"],
    ]


def test_deliveries_csv_lists_the_year(client):
    municipality = _member(client)
    household = make_household(municipality)
    benefit = make_benefit(municipality)
    juana = make_social_person(municipality, household=household, dni="12345678")
    luis = make_social_person(municipality, "Luis", "Gómez")
    make_delivery(municipality, benefit, juana, on=date(2026, 3, 10), quantity=2, note="@nota")
    make_delivery(municipality, benefit, luis, on=date(2026, 1, 5))
    make_delivery(municipality, benefit, luis, on=date(2025, 1, 5))

    response = client.get(f"{BASE}/export/deliveries.csv")

    assert 'filename="social-deliveries-2026.csv"' in response.headers["content-disposition"]
    assert _rows(response) == [
        ["date", "benefit", "category", "quantity", "person", "document", "household", "note"],
        ["2026-01-05", "Módulo alimentario", "Alimentos", "1", "Gómez, Luis", "", "", ""],
        [
            "2026-03-10",
            "Módulo alimentario",
            "Alimentos",
            "2",
            "Pérez, Juana",
            "12345678",
            "Familia Pérez",
            "'@nota",
        ],
    ]
    assert len(_rows(client.get(f"{BASE}/export/deliveries.csv", params={"year": 2025}))) == 2


def _intervention(municipality):
    make_intervention(
        municipality,
        make_intervention_type(municipality),
        make_social_person(municipality, dni="12345678"),
        on=date(2026, 3, 10),
        description=SECRET,
        performed_by="Lic. Marta Ruiz",
    )


def test_interventions_csv_has_no_description_for_a_viewer(client):
    municipality = _member(client, "viewer")
    _intervention(municipality)

    response = client.get(f"{BASE}/export/interventions.csv")

    assert 'filename="social-interventions-2026.csv"' in response.headers["content-disposition"]
    assert SECRET not in response.text
    assert _rows(response) == [
        ["date", "type", "person", "document", "performed_by"],
        ["2026-03-10", "Visita a domicilio", "Pérez, Juana", "12345678", "Lic. Marta Ruiz"],
    ]


def test_interventions_csv_includes_the_description_for_an_editor(client):
    municipality = _member(client, "editor")
    _intervention(municipality)

    rows = _rows(client.get(f"{BASE}/export/interventions.csv"))

    assert rows[0] == ["date", "type", "person", "document", "performed_by", "description"]
    assert rows[1][-1] == SECRET
    assert len(_rows(client.get(f"{BASE}/export/interventions.csv", params={"year": 2025}))) == 1


@pytest.mark.parametrize("name", EXPORTS)
def test_exports_need_access(client, name):
    social_member(None)
    login(client, EMAIL)

    assert client.get(f"{BASE}/export/{name}.csv").status_code == 403
