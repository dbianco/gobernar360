from sqlalchemy import func, select

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.economic.models import EconomicPerson
from gobernar360.dashboards.social.models import SocialPerson
from gobernar360.platform.models import AuditLog, Person
from tests.factories import admin_session, login, make_municipality
from tests.platform.notices import make_resident
from tests.social.factories import (
    BASE,
    EMAIL,
    make_household,
    make_person,
    make_social_person,
    social_member,
)


def _editor(client):
    municipality = social_member("editor")
    login(client, EMAIL)
    return municipality


def _names(response):
    assert response.status_code == 200, response.text
    return [item["person"]["full_name"] for item in response.json()["items"]]


def _count(municipality, model) -> int:
    with tenant_session(municipality.id) as db:
        return db.scalar(select(func.count()).select_from(model))


def _in_economic(municipality, person) -> EconomicPerson:
    """Incorporate a registry person into the economic dashboard."""
    link = EconomicPerson(
        municipality_id=municipality.id, person_id=person.id, employment_status="unknown"
    )
    with admin_session() as session, session.begin():
        session.add(link)
    return link


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
                "address": "Belgrano 45",
                "neighborhood": "Centro",
            }
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
            "cuil": None,
            "birth_date": "1990-05-01",
            "phone": "3472 555111",
            "email": "",
            "address": "Belgrano 45",
            "neighborhood": "Centro",
        },
        "household": None,
        "relationship": None,
    }
    assert body["id"] != body["person"]["id"]
    assert _count(municipality, SocialPerson) == 1


def test_invalid_person_data_is_rejected(client):
    _editor(client)

    for person in (
        {"first_name": "", "last_name": "Pérez"},
        {"first_name": "Juana"},
        {"first_name": "Juana", "last_name": "Pérez", "dni": "12"},
    ):
        assert client.post(f"{BASE}/people", json={"person": person}).status_code == 422, person


def test_registering_a_dni_already_in_the_registry_reuses_that_person(client):
    municipality = _editor(client)
    existing = make_person(municipality, "Juana", "Perez", dni="12345678", phone="111")

    response = client.post(
        f"{BASE}/people",
        json={"person": {"first_name": "Juana", "last_name": "Pérez", "dni": "12345678"}},
    )

    assert response.status_code == 201
    assert response.json()["person"]["id"] == str(existing.id)
    assert response.json()["person"]["last_name"] == "Pérez"
    # What was not sent keeps the registry's value.
    assert response.json()["person"]["phone"] == "111"
    assert _count(municipality, Person) == 1


def test_a_person_of_the_economic_dashboard_is_shared_not_duplicated(client):
    municipality = _editor(client)
    person = make_person(municipality, dni="12345678")
    _in_economic(municipality, person)

    created = client.post(
        f"{BASE}/people",
        json={"person": {"first_name": "Juana", "last_name": "Pérez", "dni": "12345678"}},
    )
    removed = client.delete(f"{BASE}/people/{created.json()['id']}")

    assert (created.status_code, removed.status_code) == (201, 204)
    assert created.json()["person"]["id"] == str(person.id)
    # The economic dashboard still uses the person, so the registry keeps them.
    assert _count(municipality, Person) == 1
    assert _count(municipality, EconomicPerson) == 1
    assert _count(municipality, SocialPerson) == 0


def test_a_person_cannot_be_registered_twice(client):
    municipality = _editor(client)
    make_social_person(municipality, dni="12345678")

    response = client.post(
        f"{BASE}/people",
        json={"person": {"first_name": "Juana", "last_name": "Pérez", "dni": "12345678"}},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "already_registered"


def test_lookup_by_dni_tells_registry_people_from_registered_ones(client):
    municipality = _editor(client)
    make_person(municipality, "Luis", "Gómez", dni="20111222")
    registered = make_social_person(municipality, dni="12345678")

    unknown = client.get(f"{BASE}/people/lookup", params={"dni": "30999888"})
    in_registry = client.get(f"{BASE}/people/lookup", params={"dni": "20.111.222"})
    incorporated = client.get(f"{BASE}/people/lookup", params={"dni": "12345678"})

    assert unknown.json() == {"person": None, "registered_id": None}
    assert in_registry.json()["person"]["full_name"] == "Gómez, Luis"
    assert in_registry.json()["registered_id"] is None
    assert incorporated.json()["registered_id"] == str(registered.id)
    assert client.get(f"{BASE}/people/lookup", params={"dni": "12"}).status_code == 422


def test_viewer_cannot_look_people_up(client):
    municipality = social_member("viewer")
    make_person(municipality, dni="12345678")
    login(client, EMAIL)

    assert client.get(f"{BASE}/people/lookup", params={"dni": "12345678"}).status_code == 403


def test_people_of_other_dashboards_are_invisible(client):
    municipality = _editor(client)
    only_registry = make_person(municipality, "Luis", "Gómez", dni="20111222")
    economic = make_person(municipality, "Marta", "Ruiz", dni="20333444")
    link = _in_economic(municipality, economic)
    make_social_person(municipality, dni="12345678")

    assert _names(client.get(f"{BASE}/people")) == ["Pérez, Juana"]
    assert _names(client.get(f"{BASE}/people", params={"q": "ruiz"})) == []
    for foreign_id in (only_registry.id, economic.id, link.id):
        assert client.get(f"{BASE}/people/{foreign_id}").status_code == 404
        assert client.delete(f"{BASE}/people/{foreign_id}").status_code == 404


def test_people_list_is_searched_filtered_and_paginated(client):
    municipality = _editor(client)
    household = make_household(municipality)
    make_social_person(municipality, "Juana", "Pérez", dni="12345678", neighborhood="Centro")
    make_social_person(municipality, "Luis", "Gómez", dni="20111222", neighborhood="Norte")
    make_social_person(
        municipality, "Ana", "Álvarez", neighborhood="Barrio Norte", household=household
    )

    everyone = client.get(f"{BASE}/people")
    assert _names(everyone) == ["Álvarez, Ana", "Gómez, Luis", "Pérez, Juana"]
    assert everyone.json()["total"] == 3
    assert everyone.json()["items"][0]["household"] == {
        "id": str(household.id),
        "name": "Familia Pérez",
    }
    assert _names(client.get(f"{BASE}/people", params={"q": "perez"})) == ["Pérez, Juana"]
    assert _names(client.get(f"{BASE}/people", params={"q": "20.111"})) == ["Gómez, Luis"]
    assert _names(client.get(f"{BASE}/people", params={"q": "ana alvarez"})) == ["Álvarez, Ana"]
    assert _names(client.get(f"{BASE}/people", params={"neighborhood": "norte"})) == [
        "Álvarez, Ana",
        "Gómez, Luis",
    ]
    assert _names(client.get(f"{BASE}/people", params={"q": "%"})) == []
    page = client.get(f"{BASE}/people", params={"limit": 1, "offset": 1})
    assert (_names(page), page.json()["total"]) == (["Gómez, Luis"], 3)
    assert client.get(f"{BASE}/people", params={"limit": 201}).status_code == 422
    assert client.get(f"{BASE}/people", params={"offset": -1}).status_code == 422


def test_editor_updates_the_common_data(client):
    municipality = _editor(client)
    person = make_social_person(municipality, dni="12345678", phone="111")

    response = client.patch(
        f"{BASE}/people/{person.id}",
        json={"person": {"last_name": "Pérez Sosa", "birth_date": None, "dni": None}},
    )

    assert response.status_code == 200
    body = response.json()["person"]
    assert (body["last_name"], body["dni"], body["phone"]) == ("Pérez Sosa", None, "111")
    assert client.get(f"{BASE}/people/{person.id}").json()["person"]["last_name"] == "Pérez Sosa"
    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog)).all()
    assert [(e.action, e.entity_type) for e in entries] == [("update", "people")]


def test_household_cannot_be_set_through_the_person(client):
    municipality = _editor(client)
    person = make_social_person(municipality)
    household = make_household(municipality)

    response = client.patch(f"{BASE}/people/{person.id}", json={"household_id": str(household.id)})

    assert response.status_code == 422


def test_dni_of_another_person_cannot_be_taken(client):
    municipality = _editor(client)
    make_person(municipality, "Luis", "Gómez", dni="20111222")
    person = make_social_person(municipality, dni="12345678")

    response = client.patch(f"{BASE}/people/{person.id}", json={"person": {"dni": "20111222"}})

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "dni_exists"


def test_removing_a_person_also_clears_them_from_the_registry(client):
    municipality = _editor(client)
    household = make_household(municipality)
    person = make_social_person(municipality, household=household, relationship="head")

    response = client.delete(f"{BASE}/people/{person.id}")

    assert response.status_code == 204
    assert _count(municipality, SocialPerson) == 0
    assert _count(municipality, Person) == 0
    assert client.get(f"{BASE}/households/{household.id}").json()["members"] == []


def test_viewer_reads_people_but_cannot_change_them(client):
    municipality = social_member("viewer")
    person = make_social_person(municipality)
    login(client, EMAIL)

    assert _names(client.get(f"{BASE}/people")) == ["Pérez, Juana"]
    assert client.get(f"{BASE}/people/{person.id}").status_code == 200
    new = {"person": {"first_name": "Luis", "last_name": "Gómez"}}
    assert client.post(f"{BASE}/people", json=new).status_code == 403
    assert client.patch(f"{BASE}/people/{person.id}", json={"person": {}}).status_code == 403
    assert client.delete(f"{BASE}/people/{person.id}").status_code == 403


def test_people_of_another_municipality_are_not_reachable(client):
    other = make_municipality("Saira")
    foreign = make_social_person(other, dni="12345678")
    municipality = _editor(client)

    assert _names(client.get(f"{BASE}/people")) == []
    assert client.get(f"{BASE}/people/{foreign.id}").status_code == 404
    assert client.patch(f"{BASE}/people/{foreign.id}", json={"person": {}}).status_code == 404
    assert client.get(f"{BASE}/people/lookup", params={"dni": "12345678"}).json() == {
        "person": None,
        "registered_id": None,
    }
    # The same document in this municipality is a different person.
    created = client.post(
        f"{BASE}/people",
        json={"person": {"first_name": "Otra", "last_name": "Persona", "dni": "12345678"}},
    )
    assert created.status_code == 201
    assert _count(municipality, Person) == 1


def test_a_change_with_nothing_in_it_leaves_the_person_as_they_were(client):
    municipality = social_member("editor")
    login(client, EMAIL)
    person = make_social_person(municipality, phone="111")
    url = f"{BASE}/people/{person.id}"
    before = client.get(url).json()

    assert client.patch(url, json={}).json() == before
    assert client.patch(url, json={"person": {}}).json() == before
    changed = client.patch(url, json={"person": {"phone": "222"}}).json()
    assert changed["person"]["phone"] == "222"


def test_a_person_of_the_registry_is_incorporated_by_their_cuil(client):
    municipality = _editor(client)
    person = make_resident(municipality, "20123456786", first="Juana", last="Pérez")

    created = client.post(
        f"{BASE}/people",
        json={
            "person": {
                "first_name": "Juana",
                "last_name": "Pérez",
                "dni": "12345678",
                "cuil": "20-12345678-6",
            }
        },
    )

    assert created.status_code == 201, created.text
    # The same person, who now has a document too.
    assert (created.json()["person"]["id"], created.json()["person"]["dni"]) == (
        str(person.id),
        "12345678",
    )
    found = client.get(f"{BASE}/people/lookup", params={"cuil": "20123456786"}).json()
    assert found["registered_id"] == created.json()["id"]
