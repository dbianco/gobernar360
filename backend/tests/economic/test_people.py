from sqlalchemy import func, select

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.economic.models import EconomicPerson
from gobernar360.platform.models import AuditLog, Person
from tests.economic.factories import (
    BASE,
    EMAIL,
    economic_member,
    make_actor,
    make_actor_person,
    make_economic_person,
    make_person,
)
from tests.factories import login, make_municipality


def _editor(client):
    municipality = economic_member("editor")
    login(client, EMAIL)
    return municipality


def _names(response):
    assert response.status_code == 200, response.text
    return [item["person"]["full_name"] for item in response.json()["items"]]


def _count(municipality, model) -> int:
    with tenant_session(municipality.id) as db:
        return db.scalar(select(func.count()).select_from(model))


def test_editor_registers_a_new_person(client):
    municipality = _editor(client)

    response = client.post(
        f"{BASE}/people",
        json={
            "person": {
                "first_name": " Juana ",
                "last_name": "Pérez",
                "dni": "12.345.678",
                "birth_date": "1990-05-01",
                "phone": "3472 555111",
                "email": "juana@example.test",
                "address": "Belgrano 45",
                "neighborhood": "Centro",
            },
            "employment_status": "self_employed",
            "occupation": "Costurera",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body == {
        "id": body["id"],
        "person": {
            "id": body["person"]["id"],
            "first_name": "Juana",
            "last_name": "Pérez",
            "full_name": "Pérez, Juana",
            "dni": "12345678",
            "birth_date": "1990-05-01",
            "phone": "3472 555111",
            "email": "juana@example.test",
            "address": "Belgrano 45",
            "neighborhood": "Centro",
        },
        "employment_status": "self_employed",
        "occupation": "Costurera",
    }
    assert (_count(municipality, Person), _count(municipality, EconomicPerson)) == (1, 1)


def test_person_defaults_to_unknown_employment_status(client):
    _editor(client)

    response = client.post(
        f"{BASE}/people", json={"person": {"first_name": "Luis", "last_name": "Acosta"}}
    )

    assert response.status_code == 201
    body = response.json()
    assert (body["employment_status"], body["occupation"], body["person"]["dni"]) == (
        "unknown",
        "",
        None,
    )


def test_invalid_person_data_is_rejected(client):
    _editor(client)

    for payload in (
        {"person": {"first_name": "", "last_name": "Pérez"}},
        {"person": {"first_name": "Juana", "last_name": "Pérez", "dni": "12"}},
        {"person": {"first_name": "Juana", "last_name": "Pérez"}, "employment_status": "rich"},
        {"employment_status": "employed"},
    ):
        assert client.post(f"{BASE}/people", json=payload).status_code == 422, payload


def test_registering_a_dni_already_in_the_registry_reuses_that_person(client):
    municipality = _editor(client)
    existing = make_person(
        municipality, "Juana", "Perez", dni="12345678", address="Belgrano 45", phone="555"
    )

    response = client.post(
        f"{BASE}/people",
        json={
            "person": {
                "first_name": "Juana",
                "last_name": "Pérez",
                "dni": "12.345.678",
                "phone": "",
            },
            "occupation": "Costurera",
        },
    )

    assert response.status_code == 201
    person = response.json()["person"]
    assert person["id"] == str(existing.id)
    # Sent fields update the registry; fields left out keep what it had.
    assert (person["last_name"], person["phone"], person["address"]) == ("Pérez", "", "Belgrano 45")
    assert (_count(municipality, Person), _count(municipality, EconomicPerson)) == (1, 1)


def test_a_person_cannot_be_registered_twice(client):
    municipality = _editor(client)
    make_economic_person(municipality, dni="12345678")

    response = client.post(
        f"{BASE}/people",
        json={"person": {"first_name": "Juana", "last_name": "Otra", "dni": "12345678"}},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_registered"
    assert _names(client.get(f"{BASE}/people")) == ["Pérez, Juana"]


def test_lookup_by_dni_tells_registry_people_from_registered_ones(client):
    municipality = _editor(client)
    registry_only = make_person(municipality, "Solo", "Padrón", dni="11111111")
    registered = make_economic_person(municipality, "Juana", "Pérez", dni="22222222")
    make_economic_person(make_municipality("Saira"), "Ajena", "Ajena", dni="33333333")

    def lookup(dni):
        response = client.get(f"{BASE}/people/lookup", params={"dni": dni})
        assert response.status_code == 200, response.text
        return response.json()

    found = lookup("11.111.111")
    assert (found["person"]["id"], found["registered_id"]) == (str(registry_only.id), None)
    assert found["person"]["full_name"] == "Padrón, Solo"
    assert lookup("22222222")["registered_id"] == str(registered.id)
    assert lookup("33333333") == {"person": None, "registered_id": None}
    assert lookup("44444444") == {"person": None, "registered_id": None}
    assert client.get(f"{BASE}/people/lookup", params={"dni": "12"}).status_code == 422
    assert client.get(f"{BASE}/people/lookup").status_code == 422


def test_viewer_cannot_look_people_up(client):
    economic_member("viewer")
    login(client, EMAIL)

    assert client.get(f"{BASE}/people/lookup", params={"dni": "11111111"}).status_code == 403


def test_registry_people_not_incorporated_are_invisible(client):
    municipality = _editor(client)
    registry_only = make_person(municipality, "Solo", "Padrón", dni="11111111")
    make_economic_person(municipality)

    assert _names(client.get(f"{BASE}/people")) == ["Pérez, Juana"]
    assert _names(client.get(f"{BASE}/people", params={"q": "Padrón"})) == []
    assert _names(client.get(f"{BASE}/people", params={"q": "11111111"})) == []
    assert client.get(f"{BASE}/people/{registry_only.id}").status_code == 404
    assert (
        client.patch(f"{BASE}/people/{registry_only.id}", json={"occupation": "x"}).status_code
        == 404
    )
    assert client.delete(f"{BASE}/people/{registry_only.id}").status_code == 404


def test_people_list_is_searched_filtered_and_paginated(client):
    municipality = _editor(client)
    make_economic_person(municipality, "Juana", "Pérez", "employed", dni="12345678")
    make_economic_person(municipality, "Luis", "Acosta", "unemployed", dni="22333444")
    make_economic_person(municipality, "Ana", "Pérez Luna", "employed")

    assert _names(client.get(f"{BASE}/people")) == [
        "Acosta, Luis",
        "Pérez, Juana",
        "Pérez Luna, Ana",
    ]
    assert _names(client.get(f"{BASE}/people", params={"q": "pérez"})) == [
        "Pérez, Juana",
        "Pérez Luna, Ana",
    ]
    assert _names(client.get(f"{BASE}/people", params={"q": "juana pérez"})) == ["Pérez, Juana"]
    assert _names(client.get(f"{BASE}/people", params={"q": "22.333"})) == ["Acosta, Luis"]
    assert _names(client.get(f"{BASE}/people", params={"employment_status": "employed"})) == [
        "Pérez, Juana",
        "Pérez Luna, Ana",
    ]
    assert client.get(f"{BASE}/people", params={"employment_status": "rich"}).status_code == 422
    page = client.get(f"{BASE}/people", params={"limit": 1, "offset": 1})
    assert (_names(page), page.json()["total"]) == (["Pérez, Juana"], 3)


def test_person_detail_lists_their_actors(client):
    municipality = _editor(client)
    person = make_economic_person(municipality)
    make_actor_person(municipality, make_actor(municipality, "Zapatería"), person, "employee")
    make_actor_person(municipality, make_actor(municipality, "Almacén"), person, "owner")

    response = client.get(f"{BASE}/people/{person.id}")

    assert response.status_code == 200
    assert [(link["actor"]["name"], link["role"]) for link in response.json()["actors"]] == [
        ("Almacén", "owner"),
        ("Zapatería", "employee"),
    ]


def test_editor_updates_common_and_economic_data(client):
    municipality = _editor(client)
    person = make_economic_person(municipality, dni="12345678", phone="555")

    response = client.patch(
        f"{BASE}/people/{person.id}",
        json={
            "person": {"neighborhood": "Norte", "dni": None},
            "employment_status": "retired",
            "occupation": "Docente",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["employment_status"], body["occupation"]) == ("retired", "Docente")
    assert (body["person"]["neighborhood"], body["person"]["dni"], body["person"]["phone"]) == (
        "Norte",
        None,
        "555",
    )
    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert sorted((e.action, e.entity_type) for e in entries) == [
        ("update", "economic_people"),
        ("update", "people"),
    ]


def test_dni_of_another_person_cannot_be_taken(client):
    municipality = _editor(client)
    make_person(municipality, "Solo", "Padrón", dni="11111111")
    person = make_economic_person(municipality, dni="12345678")

    response = client.patch(f"{BASE}/people/{person.id}", json={"person": {"dni": "11.111.111"}})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "dni_exists"


def test_removing_a_person_also_clears_them_from_the_registry(client):
    municipality = _editor(client)
    person = make_economic_person(municipality)
    make_actor_person(municipality, make_actor(municipality), person)

    assert client.delete(f"{BASE}/people/{person.id}").status_code == 204

    assert client.get(f"{BASE}/people").json() == {"items": [], "total": 0}
    assert (_count(municipality, Person), _count(municipality, EconomicPerson)) == (0, 0)
    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog)).all()
    assert sorted((e.action, e.entity_type) for e in entries) == [
        ("delete", "economic_people"),
        ("delete", "people"),
    ]


def test_viewer_reads_people_but_cannot_change_them(client):
    municipality = economic_member("viewer")
    person = make_economic_person(municipality)
    login(client, EMAIL)

    assert client.get(f"{BASE}/people").json()["total"] == 1
    assert client.get(f"{BASE}/people/{person.id}").status_code == 200
    payload = {"person": {"first_name": "x", "last_name": "y"}}
    assert client.post(f"{BASE}/people", json=payload).status_code == 403
    assert client.patch(f"{BASE}/people/{person.id}", json={"occupation": "x"}).status_code == 403
    assert client.delete(f"{BASE}/people/{person.id}").status_code == 403


def test_people_of_another_municipality_are_not_reachable(client):
    foreign = make_economic_person(make_municipality("Saira"), dni="12345678")
    municipality = _editor(client)

    assert client.get(f"{BASE}/people").json() == {"items": [], "total": 0}
    assert client.get(f"{BASE}/people/{foreign.id}").status_code == 404
    assert client.patch(f"{BASE}/people/{foreign.id}", json={"occupation": "x"}).status_code == 404
    assert client.delete(f"{BASE}/people/{foreign.id}").status_code == 404
    # The same document in this municipality is a different person.
    created = client.post(
        f"{BASE}/people",
        json={"person": {"first_name": "Otra", "last_name": "Persona", "dni": "12345678"}},
    )
    assert created.status_code == 201
    assert created.json()["person"]["id"] != str(foreign.person_id)
    assert _count(municipality, Person) == 1


def test_search_ignores_accents(client):
    municipality = _editor(client)
    make_economic_person(municipality, "Juana", "Pérez")
    make_economic_person(municipality, "Raul", "Gomez")

    assert _names(client.get(f"{BASE}/people", params={"q": "perez"})) == ["Pérez, Juana"]
    assert _names(client.get(f"{BASE}/people", params={"q": "PÉREZ"})) == ["Pérez, Juana"]
    assert _names(client.get(f"{BASE}/people", params={"q": "raúl gómez"})) == ["Gomez, Raul"]
