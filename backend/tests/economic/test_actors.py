from sqlalchemy import func, select

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.economic.models import ActorPerson
from gobernar360.platform.models import AuditLog
from tests.economic.factories import (
    BASE,
    EMAIL,
    economic_member,
    make_actor,
    make_actor_person,
    make_actor_type,
    make_economic_person,
    make_person,
    make_sector,
)
from tests.factories import login, make_municipality


def _editor(client):
    municipality = economic_member("editor")
    login(client, EMAIL)
    return municipality


def _names(response):
    assert response.status_code == 200, response.text
    return [item["name"] for item in response.json()["items"]]


def test_editor_creates_an_actor_with_only_a_name(client):
    _editor(client)

    response = client.post(f"{BASE}/actors", json={"name": "  Panadería La Espiga "})

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "name": "Panadería La Espiga",
        "actor_type": None,
        "sector": None,
        "cuit": "",
        "address": "",
        "phone": "",
        "email": "",
        "employee_count": None,
        "notes": "",
    }


def test_editor_creates_an_actor_with_every_field(client):
    municipality = _editor(client)
    actor_type, sector = make_actor_type(municipality), make_sector(municipality)

    response = client.post(
        f"{BASE}/actors",
        json={
            "name": "Metalúrgica Sur",
            "actor_type_id": str(actor_type.id),
            "sector_id": str(sector.id),
            "cuit": "30-71234567-8",
            "address": "San Martín 123",
            "phone": "3472 555111",
            "email": "info@metalurgica.test",
            "employee_count": 14,
            "notes": "Exporta a Brasil.",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["cuit"] == "30712345678"
    assert body["actor_type"] == {"id": str(actor_type.id), "name": "Comercio"}
    assert body["sector"] == {"id": str(sector.id), "name": "Alimentos"}
    assert (body["employee_count"], body["notes"]) == (14, "Exporta a Brasil.")


def test_invalid_actor_data_is_rejected(client):
    _editor(client)

    for payload in (
        {"name": ""},
        {"name": "x", "cuit": "123"},
        {"name": "x", "cuit": "30-7123456A-8"},
        {"name": "x", "employee_count": -1},
    ):
        assert client.post(f"{BASE}/actors", json=payload).status_code == 422, payload


def test_actor_list_is_searched_and_filtered(client):
    municipality = _editor(client)
    shop, industry = make_actor_type(municipality), make_actor_type(municipality, "Industria")
    food = make_sector(municipality)
    make_actor(municipality, "Panadería La Espiga", actor_type_id=shop.id, sector_id=food.id)
    make_actor(municipality, "Metalúrgica Sur", actor_type_id=industry.id, cuit="30712345678")
    make_actor(municipality, "Almacén 100%")
    make_actor(make_municipality("Saira"), "Panadería ajena")

    assert _names(client.get(f"{BASE}/actors")) == [
        "Almacén 100%",
        "Metalúrgica Sur",
        "Panadería La Espiga",
    ]
    assert _names(client.get(f"{BASE}/actors", params={"q": "panader"})) == ["Panadería La Espiga"]
    assert _names(client.get(f"{BASE}/actors", params={"q": "30-7123"})) == ["Metalúrgica Sur"]
    assert _names(client.get(f"{BASE}/actors", params={"q": "100%"})) == ["Almacén 100%"]
    assert _names(client.get(f"{BASE}/actors", params={"q": "%"})) == ["Almacén 100%"]
    assert _names(client.get(f"{BASE}/actors", params={"q": "_"})) == []
    assert _names(client.get(f"{BASE}/actors", params={"actor_type_id": str(industry.id)})) == [
        "Metalúrgica Sur"
    ]
    assert _names(client.get(f"{BASE}/actors", params={"sector_id": str(food.id)})) == [
        "Panadería La Espiga"
    ]


def test_actor_list_is_paginated(client):
    municipality = _editor(client)
    for index in range(5):
        make_actor(municipality, f"Actor {index}")

    response = client.get(f"{BASE}/actors", params={"limit": 2, "offset": 2})

    assert _names(response) == ["Actor 2", "Actor 3"]
    assert response.json()["total"] == 5
    assert client.get(f"{BASE}/actors", params={"limit": 201}).status_code == 422
    assert client.get(f"{BASE}/actors", params={"limit": 0}).status_code == 422
    assert client.get(f"{BASE}/actors", params={"offset": -1}).status_code == 422


def test_editor_updates_an_actor_and_clears_optional_fields(client):
    municipality = _editor(client)
    actor_type = make_actor_type(municipality)
    actor = make_actor(municipality, actor_type_id=actor_type.id, employee_count=3, phone="555")

    response = client.patch(
        f"{BASE}/actors/{actor.id}",
        json={"name": "La Espiga SRL", "actor_type_id": None, "employee_count": None},
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["name"], body["actor_type"], body["employee_count"], body["phone"]) == (
        "La Espiga SRL",
        None,
        None,
        "555",
    )
    assert client.patch(f"{BASE}/actors/{actor.id}", json={"name": None}).status_code == 422


def test_actor_cannot_reference_parameters_of_another_municipality(client):
    other = make_municipality("Saira")
    foreign_type, foreign_sector = make_actor_type(other), make_sector(other)
    municipality = _editor(client)
    actor = make_actor(municipality)

    created = client.post(
        f"{BASE}/actors", json={"name": "x", "actor_type_id": str(foreign_type.id)}
    )
    moved = client.patch(f"{BASE}/actors/{actor.id}", json={"sector_id": str(foreign_sector.id)})

    assert (created.status_code, moved.status_code) == (422, 422)
    assert created.json()["error"]["code"] == "invalid_reference"
    assert client.get(f"{BASE}/actors").json()["total"] == 1


def test_actor_detail_lists_its_people(client):
    municipality = _editor(client)
    actor = make_actor(municipality)
    owner = make_economic_person(municipality, "Juana", "Pérez", dni="12345678")
    employee = make_economic_person(municipality, "Luis", "Acosta")
    make_actor_person(municipality, actor, owner, "owner")
    make_actor_person(municipality, actor, employee, "employee")

    response = client.get(f"{BASE}/actors/{actor.id}")

    assert response.status_code == 200
    people = response.json()["people"]
    assert [(link["person"]["person"]["full_name"], link["role"]) for link in people] == [
        ("Acosta, Luis", "employee"),
        ("Pérez, Juana", "owner"),
    ]
    assert people[1]["person"]["id"] == str(owner.id)
    assert people[1]["person"]["person"]["dni"] == "12345678"


def test_editor_links_and_unlinks_a_person(client):
    municipality = _editor(client)
    actor = make_actor(municipality)
    person = make_economic_person(municipality)

    linked = client.post(
        f"{BASE}/actors/{actor.id}/people", json={"person_id": str(person.id), "role": "contact"}
    )
    again = client.post(
        f"{BASE}/actors/{actor.id}/people", json={"person_id": str(person.id), "role": "owner"}
    )
    bad_role = client.post(
        f"{BASE}/actors/{actor.id}/people", json={"person_id": str(person.id), "role": "boss"}
    )

    assert (linked.status_code, again.status_code, bad_role.status_code) == (201, 409, 422)
    assert linked.json()["role"] == "contact"
    assert (
        client.delete(f"{BASE}/actors/{actor.id}/people/{linked.json()['id']}").status_code == 204
    )
    assert client.get(f"{BASE}/actors/{actor.id}").json()["people"] == []


def test_person_link_rejects_people_outside_the_dashboard(client):
    other = make_municipality("Saira")
    foreign = make_economic_person(other)
    municipality = _editor(client)
    actor = make_actor(municipality)
    registry_only = make_person(municipality, "Solo", "Padrón")
    other_actor = make_actor(municipality, "Otro")
    link = make_actor_person(municipality, other_actor, make_economic_person(municipality))

    for person_id in (foreign.id, registry_only.id):
        response = client.post(
            f"{BASE}/actors/{actor.id}/people", json={"person_id": str(person_id), "role": "owner"}
        )
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "invalid_reference"
    # A link is only reachable through its own actor.
    assert client.delete(f"{BASE}/actors/{actor.id}/people/{link.id}").status_code == 404


def test_deleting_an_actor_removes_its_links_but_not_the_people(client):
    municipality = _editor(client)
    actor = make_actor(municipality)
    person = make_economic_person(municipality)
    make_actor_person(municipality, actor, person)

    assert client.delete(f"{BASE}/actors/{actor.id}").status_code == 204

    assert client.get(f"{BASE}/actors/{actor.id}").status_code == 404
    assert client.get(f"{BASE}/people/{person.id}").status_code == 200
    with tenant_session(municipality.id) as db:
        assert db.scalar(select(func.count()).select_from(ActorPerson)) == 0


def test_viewer_reads_actors_but_cannot_change_them(client):
    municipality = economic_member("viewer")
    actor = make_actor(municipality)
    person = make_economic_person(municipality)
    link = make_actor_person(municipality, actor, person)
    login(client, EMAIL)

    assert client.get(f"{BASE}/actors").json()["total"] == 1
    assert client.get(f"{BASE}/actors/{actor.id}").status_code == 200
    assert client.post(f"{BASE}/actors", json={"name": "x"}).status_code == 403
    assert client.patch(f"{BASE}/actors/{actor.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}/actors/{actor.id}").status_code == 403
    assert (
        client.post(
            f"{BASE}/actors/{actor.id}/people", json={"person_id": str(person.id), "role": "owner"}
        ).status_code
        == 403
    )
    assert client.delete(f"{BASE}/actors/{actor.id}/people/{link.id}").status_code == 403


def test_actors_of_another_municipality_are_not_reachable(client):
    foreign = make_actor(make_municipality("Saira"))
    _editor(client)

    assert client.get(f"{BASE}/actors").json() == {"items": [], "total": 0}
    assert client.get(f"{BASE}/actors/{foreign.id}").status_code == 404
    assert client.patch(f"{BASE}/actors/{foreign.id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"{BASE}/actors/{foreign.id}").status_code == 404


def test_actor_changes_are_audited(client):
    municipality = _editor(client)

    actor_id = client.post(f"{BASE}/actors", json={"name": "La Espiga"}).json()["id"]
    client.patch(f"{BASE}/actors/{actor_id}", json={"phone": "555"})
    client.delete(f"{BASE}/actors/{actor_id}")

    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.action, e.entity_type) for e in entries] == [
        ("create", "economic_actors"),
        ("update", "economic_actors"),
        ("delete", "economic_actors"),
    ]
    assert entries[1].changes == {"phone": "555"}
