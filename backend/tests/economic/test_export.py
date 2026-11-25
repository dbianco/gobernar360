import csv
import io
from datetime import date

import pytest

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
)
from tests.factories import login, make_municipality


def _rows(response):
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    text = response.content.decode("utf-8")
    assert text.startswith("﻿")
    return list(csv.reader(io.StringIO(text.removeprefix("﻿"))))


def _viewer(client):
    municipality = economic_member("viewer")
    login(client, EMAIL)
    return municipality


def test_actors_csv_lists_every_actor(client):
    municipality = _viewer(client)
    make_actor(
        municipality,
        "Panadería",
        actor_type_id=make_actor_type(municipality).id,
        sector_id=make_sector(municipality).id,
        cuit="30712345678",
        address="San Martín 1",
        phone="+54 3472 555",
        email="pan@example.test",
        employee_count=4,
        notes="=SUM(1)",
    )
    make_actor(municipality, "Almacén")
    make_actor(make_municipality("Saira"), "Ajeno")

    response = client.get(f"{BASE}/export/actors.csv")

    assert 'filename="economic-actors.csv"' in response.headers["content-disposition"]
    assert _rows(response) == [
        ["name", "type", "sector", "cuit", "address", "phone", "email", "employees", "notes"],
        ["Almacén", "", "", "", "", "", "", "", ""],
        [
            "Panadería",
            "Comercio",
            "Alimentos",
            "30712345678",
            "San Martín 1",
            "'+54 3472 555",
            "pan@example.test",
            "4",
            "'=SUM(1)",
        ],
    ]


def test_people_csv_lists_only_the_people_of_the_dashboard(client):
    municipality = _viewer(client)
    make_economic_person(
        municipality,
        "Juana",
        "Pérez",
        "self_employed",
        "Costurera",
        dni="12345678",
        birth_date=date(1990, 5, 1),
        neighborhood="Centro",
    )
    make_person(municipality, "Solo", "Padrón")
    make_economic_person(make_municipality("Saira"), "Ajena", "Ajena")

    response = client.get(f"{BASE}/export/people.csv")

    assert 'filename="economic-people.csv"' in response.headers["content-disposition"]
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
            "employment_status",
            "occupation",
        ],
        [
            "Pérez",
            "Juana",
            "12345678",
            "1990-05-01",
            "",
            "",
            "",
            "Centro",
            "self_employed",
            "Costurera",
        ],
    ]


def test_assignments_csv_lists_the_assignments_of_the_year(client):
    municipality = _viewer(client)
    tool = make_tool(municipality)
    actor = make_actor(municipality, cuit="30712345678")
    person = make_economic_person(municipality, dni="12345678")
    make_assignment(municipality, tool, actor=actor, on=date(2026, 3, 10), note="Primera cuota")
    make_assignment(municipality, tool, person=person, on=date(2026, 1, 2))
    make_assignment(municipality, tool, actor=actor, on=date(2025, 3, 10))

    response = client.get(f"{BASE}/export/assignments.csv", params={"year": 2026})

    assert 'filename="economic-assignments-2026.csv"' in response.headers["content-disposition"]
    assert _rows(response) == [
        ["date", "tool", "category", "recipient_type", "recipient", "document", "note"],
        [
            "2026-01-02",
            "Microcrédito productivo",
            "Financiamiento",
            "person",
            "Pérez, Juana",
            "12345678",
            "",
        ],
        [
            "2026-03-10",
            "Microcrédito productivo",
            "Financiamiento",
            "actor",
            "Panadería La Espiga",
            "30712345678",
            "Primera cuota",
        ],
    ]


@pytest.mark.parametrize("name", ["actors", "people", "assignments"])
def test_exports_require_access(client, name):
    economic_member(None)
    login(client, EMAIL)

    assert client.get(f"{BASE}/export/{name}.csv").status_code == 403


def test_people_csv_has_every_detail_by_last_and_first_name(client):
    municipality = _viewer(client)
    for first, last in (("Zoe", "Gómez"), ("Ana", "Pérez"), ("Bea", "Gómez")):
        make_economic_person(
            municipality,
            first,
            last,
            phone=f"tel {first}",
            email=f"{first}@example.test",
            address=f"calle {first}",
        )

    header, *rows = _rows(client.get(f"{BASE}/export/people.csv"))

    columns = [header.index(c) for c in ("last_name", "first_name", "phone", "email", "address")]
    assert [[row[c] for c in columns] for row in rows] == [
        ["Gómez", "Bea", "tel Bea", "Bea@example.test", "calle Bea"],
        ["Gómez", "Zoe", "tel Zoe", "Zoe@example.test", "calle Zoe"],
        ["Pérez", "Ana", "tel Ana", "Ana@example.test", "calle Ana"],
    ]
    blank = [header.index(c) for c in ("dni", "birth_date")]
    assert [[row[c] for c in blank] for row in rows] == [["", ""]] * 3


def test_actors_csv_tells_no_employees_from_not_known(client):
    municipality = _viewer(client)
    make_actor(municipality, "Uno", employee_count=0)
    make_actor(municipality, "Otro")

    header, *rows = _rows(client.get(f"{BASE}/export/actors.csv"))

    column = header.index("employees")
    assert {row[0]: row[column] for row in rows} == {"Uno": "0", "Otro": ""}


def test_assignments_csv_is_of_the_year_asked_or_the_current_one_by_date(client):
    client.app.dependency_overrides[get_today] = lambda: date(2026, 6, 15)
    municipality = _viewer(client)
    tool, person = make_tool(municipality), make_economic_person(municipality)
    for on in (date(2026, 5, 2), date(2025, 1, 1), date(2026, 1, 3), date(2026, 3, 9)):
        make_assignment(municipality, tool, person=person, on=on)

    def dates(**params):
        header, *rows = _rows(client.get(f"{BASE}/export/assignments.csv", params=params))
        document = header.index("document")
        assert {row[document] for row in rows} == {""}
        return [row[header.index("date")] for row in rows]

    assert dates() == ["2026-01-03", "2026-03-09", "2026-05-02"]
    assert dates(year=2025) == ["2025-01-01"]
