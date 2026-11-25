from sqlalchemy import func, select

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.social.models import Household, SocialPerson
from gobernar360.platform.models import AuditLog, Person
from tests.factories import login, make_municipality
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


def _count(municipality, model) -> int:
    with tenant_session(municipality.id) as db:
        return db.scalar(select(func.count()).select_from(model))


def _put(client, household, person, relationship):
    return client.put(
        f"{BASE}/households/{household.id}/members/{person.id}",
        json={"relationship": relationship},
    )


def test_editor_creates_a_household(client):
    municipality = _editor(client)

    response = client.post(
        f"{BASE}/households",
        json={"name": " Familia Pérez ", "address": "Belgrano 45", "neighborhood": "Centro"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "name": "Familia Pérez",
        "address": "Belgrano 45",
        "neighborhood": "Centro",
        "member_count": 0,
        "head": None,
        "zones": [],
    }
    assert client.post(f"{BASE}/households", json={"name": "  "}).status_code == 422
    assert _count(municipality, Household) == 1


def test_households_are_listed_with_their_size_and_head(client):
    municipality = _editor(client)
    perez = make_household(municipality, "Familia Pérez", address="Belgrano 45")
    make_household(municipality, "Familia Álvarez", address="San Martín 10")
    head = make_social_person(municipality, household=perez, relationship="head")
    make_social_person(municipality, "Luis", household=perez, relationship="child")

    response = client.get(f"{BASE}/households")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 2
    assert [(h["name"], h["member_count"]) for h in body["items"]] == [
        ("Familia Álvarez", 0),
        ("Familia Pérez", 2),
    ]
    assert body["items"][0]["head"] is None
    assert body["items"][1]["head"] == {"id": str(head.id), "full_name": "Pérez, Juana"}
    names = lambda params: [  # noqa: E731
        h["name"] for h in client.get(f"{BASE}/households", params=params).json()["items"]
    ]
    assert names({"q": "alvarez"}) == ["Familia Álvarez"]
    assert names({"q": "belgrano"}) == ["Familia Pérez"]
    assert names({"limit": 1, "offset": 1}) == ["Familia Pérez"]
    assert client.get(f"{BASE}/households", params={"limit": 0}).status_code == 422


def test_household_detail_lists_members_head_first(client):
    municipality = _editor(client)
    household = make_household(municipality)
    make_social_person(municipality, "Ana", "Álvarez", household=household, relationship="child")
    head = make_social_person(
        municipality, "Juana", "Pérez", household=household, relationship="head", dni="12345678"
    )
    make_social_person(municipality, "Luis", "Gómez", household=household, relationship="partner")
    make_social_person(municipality, "Sin", "Grupo")

    response = client.get(f"{BASE}/households/{household.id}")

    assert response.status_code == 200
    assert [(m["full_name"], m["relationship"]) for m in response.json()["members"]] == [
        ("Pérez, Juana", "head"),
        ("Álvarez, Ana", "child"),
        ("Gómez, Luis", "partner"),
    ]
    assert response.json()["members"][0] == {
        "id": str(head.id),
        "full_name": "Pérez, Juana",
        "dni": "12345678",
        "relationship": "head",
    }
    assert response.json()["member_count"] == 3


def test_members_are_added_changed_and_removed(client):
    municipality = _editor(client)
    household = make_household(municipality)
    person = make_social_person(municipality)

    added = _put(client, household, person, "child")
    changed = _put(client, household, person, "head")

    assert (added.status_code, changed.status_code) == (200, 200)
    assert [m["relationship"] for m in added.json()["members"]] == ["child"]
    assert changed.json()["head"] == {"id": str(person.id), "full_name": "Pérez, Juana"}
    detail = client.get(f"{BASE}/people/{person.id}").json()
    assert (detail["household"]["name"], detail["relationship"]) == ("Familia Pérez", "head")

    removed = client.delete(f"{BASE}/households/{household.id}/members/{person.id}")

    assert removed.status_code == 204
    assert client.get(f"{BASE}/households/{household.id}").json()["members"] == []
    assert client.get(f"{BASE}/people/{person.id}").json()["household"] is None
    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.action, e.entity_type) for e in entries] == [("update", "social_people")] * 3
    assert entries[0].changes == {"household_id": str(household.id), "relationship": "child"}
    assert entries[2].changes == {"household_id": None, "relationship": None}


def test_a_household_has_a_single_head(client):
    municipality = _editor(client)
    household = make_household(municipality)
    make_social_person(municipality, household=household, relationship="head")
    other = make_social_person(municipality, "Luis", "Gómez")

    response = _put(client, household, other, "head")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "household_has_head"
    assert _put(client, household, other, "partner").status_code == 200


def test_a_person_belongs_to_one_household(client):
    municipality = _editor(client)
    first, second = make_household(municipality), make_household(municipality, "Familia Gómez")
    person = make_social_person(municipality, household=first, relationship="child")

    response = _put(client, second, person, "child")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "in_another_household"
    assert client.get(f"{BASE}/households/{first.id}").json()["member_count"] == 1


def test_invalid_members_are_rejected(client):
    other = make_municipality("Saira")
    foreign = make_social_person(other, dni="20111222")
    municipality = _editor(client)
    household = make_household(municipality)
    person = make_social_person(municipality)
    registry_only = make_person(municipality, "Luis", "Gómez")
    stranger = make_social_person(municipality, "Marta", "Ruiz")

    assert _put(client, household, person, "cousin").status_code == 422
    assert _put(client, household, foreign, "child").status_code == 404
    assert _put(client, household, registry_only, "child").status_code == 404
    # Removing someone who is not a member of this household.
    assert (
        client.delete(f"{BASE}/households/{household.id}/members/{stranger.id}").status_code == 404
    )


def test_deleting_a_household_frees_its_members(client):
    municipality = _editor(client)
    household = make_household(municipality)
    person = make_social_person(municipality, household=household, relationship="head")

    response = client.delete(f"{BASE}/households/{household.id}")

    assert response.status_code == 204
    assert _count(municipality, Household) == 0
    assert (_count(municipality, SocialPerson), _count(municipality, Person)) == (1, 1)
    detail = client.get(f"{BASE}/people/{person.id}").json()
    assert (detail["household"], detail["relationship"]) == (None, None)
    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert sorted((e.action, e.entity_type) for e in entries) == [
        ("delete", "social_households"),
        ("update", "social_people"),
    ]


def test_editor_updates_a_household(client):
    municipality = _editor(client)
    household = make_household(municipality, address="Belgrano 45")

    response = client.patch(
        f"{BASE}/households/{household.id}", json={"name": "Familia Pérez Sosa", "address": ""}
    )

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["address"]) == ("Familia Pérez Sosa", "")
    assert client.patch(f"{BASE}/households/{household.id}", json={"name": None}).status_code == 422


def test_viewer_reads_households_but_cannot_change_them(client):
    municipality = social_member("viewer")
    household = make_household(municipality)
    person = make_social_person(municipality)
    login(client, EMAIL)

    assert client.get(f"{BASE}/households").json()["total"] == 1
    assert client.get(f"{BASE}/households/{household.id}").status_code == 200
    assert client.post(f"{BASE}/households", json={"name": "x"}).status_code == 403
    assert client.patch(f"{BASE}/households/{household.id}", json={"name": "x"}).status_code == 403
    assert client.delete(f"{BASE}/households/{household.id}").status_code == 403
    assert _put(client, household, person, "child").status_code == 403
    assert client.delete(f"{BASE}/households/{household.id}/members/{person.id}").status_code == 403


def test_households_of_another_municipality_are_not_reachable(client):
    other = make_municipality("Saira")
    foreign = make_household(other)
    municipality = _editor(client)
    person = make_social_person(municipality)

    assert client.get(f"{BASE}/households").json() == {"items": [], "total": 0}
    assert client.get(f"{BASE}/households/{foreign.id}").status_code == 404
    assert client.patch(f"{BASE}/households/{foreign.id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"{BASE}/households/{foreign.id}").status_code == 404
    assert _put(client, foreign, person, "child").status_code == 404


def test_members_who_share_a_last_name_are_listed_by_first_name(client):
    municipality = _editor(client)
    household = make_household(municipality)
    for first_name in ("Zoe", "Ana", "Luis"):
        make_social_person(
            municipality, first_name, "Pérez", household=household, relationship="child"
        )

    members = client.get(f"{BASE}/households/{household.id}").json()["members"]

    assert [member["full_name"] for member in members] == [
        "Pérez, Ana",
        "Pérez, Luis",
        "Pérez, Zoe",
    ]
