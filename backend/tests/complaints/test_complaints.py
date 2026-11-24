"""Registering complaints, the areas' queues and what each member may see."""

from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog, Person
from tests.complaints.factories import (
    BASE,
    Setup,
    at,
    complaints_member,
    make_area,
    make_holiday,
    make_person,
    make_type,
    make_zone,
    pin_clock,
    signed_in,
)
from tests.factories import login


def _create(client, setup, **fields):
    body = {"type_id": str(setup.type.id), "zone_id": str(setup.zone.id), "address": "Belgrano 5"}
    return client.post(f"{BASE}/complaints", json=body | fields)


def _move(client, complaint_id, to_state, note=""):
    response = client.post(
        f"{BASE}/complaints/{complaint_id}/transitions", json={"to_state": to_state, "note": note}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_a_complaint_for_a_person_found_by_document(client):
    setup = Setup(signed_in(client), target_days=3)
    person = make_person(setup.municipality)
    pin_clock(client, at(2, hour=9))

    found = client.get(f"{BASE}/people/lookup", params={"dni": "33.123.456"}).json()
    created = _create(client, setup, person_id=found["person"]["id"], description="Sin luz")

    assert found["person"]["full_name"] == "Fernández, Lucía"
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["number"] == 1
    assert body["state"] == "received"
    assert body["person"]["id"] == str(person.id)
    assert body["person"]["dni"] == "33123456"
    assert body["area"] == {"id": str(setup.area.id), "name": setup.area.name}
    assert body["clock"] == {
        "target_days": 3,
        "used_days": 0,
        "left_days": 3,
        "deadline": "2026-03-05",
        "status": "on_time",
        "paused": False,
        "resolved_on": None,
    }
    assert body["moves"] == ["assigned", "rejected"]
    assert [(e["kind"], e["to_state"], e["to_area"]["name"]) for e in body["timeline"]] == [
        ("created", "received", setup.area.name)
    ]


def test_a_document_not_in_the_registry_finds_nobody(client):
    signed_in(client)

    assert client.get(f"{BASE}/people/lookup", params={"dni": "40111222"}).json() == {
        "person": None,
        "registered_id": None,
    }
    assert client.get(f"{BASE}/people/lookup", params={"dni": "12"}).status_code == 422


def test_a_complaint_adds_a_new_resident_to_the_registry(client):
    setup = Setup(signed_in(client))

    created = _create(
        client,
        setup,
        new_person={"first_name": "Juan", "last_name": "Paz", "dni": "40.111.222", "phone": "555"},
    )

    assert created.status_code == 201, created.text
    assert created.json()["person"]["full_name"] == "Paz, Juan"
    with tenant_session(setup.municipality.id) as db:
        assert db.scalars(select(Person.dni)).all() == ["40111222"]


def test_a_new_resident_cannot_take_a_document_already_in_the_registry(client):
    setup = Setup(signed_in(client))
    make_person(setup.municipality)

    response = _create(
        client, setup, new_person={"first_name": "Otra", "last_name": "Persona", "dni": "33123456"}
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "dni_exists"


def test_a_complaint_may_be_anonymous(client):
    setup = Setup(signed_in(client))

    body = _create(client, setup).json()

    assert body["person"] is None


def test_a_complaint_names_one_resident_at_most(client):
    setup = Setup(signed_in(client))
    person = make_person(setup.municipality)

    response = _create(
        client,
        setup,
        person_id=str(person.id),
        new_person={"first_name": "Juan", "last_name": "Paz"},
    )

    assert response.status_code == 422


def test_numbers_are_correlative_and_creation_is_audited(client):
    setup = Setup(signed_in(client))

    numbers = [_create(client, setup).json()["number"] for _ in range(3)]

    assert numbers == [1, 2, 3]
    with tenant_session(setup.municipality.id) as db:
        entries = db.scalars(
            select(AuditLog).where(AuditLog.entity_type == "complaints_complaints")
        ).all()
    assert [entry.action for entry in entries] == ["create"] * 3


def test_retired_types_are_not_used_for_new_complaints(client):
    setup = Setup(signed_in(client))
    retired = make_type(setup.municipality, setup.area, name="Viejo", is_active=False)

    response = _create(client, setup, type_id=str(retired.id))

    assert response.status_code == 422


def test_a_new_complaint_lands_in_its_types_area_queue_with_its_deadline(client):
    municipality = signed_in(client)
    lights, waste = make_area(municipality, "Alumbrado"), make_area(municipality, "Higiene")
    zone = make_zone(municipality)
    lamp = make_type(municipality, lights, "Luminaria apagada", target_days=3)
    make_type(municipality, waste, "Residuos", target_days=2)
    # Friday 6: the deadline skips the weekend and Tuesday 10, a holiday.
    make_holiday(municipality, at(10).date())
    pin_clock(client, at(6))

    created = client.post(
        f"{BASE}/complaints",
        json={"type_id": str(lamp.id), "zone_id": str(zone.id), "address": "Mitre 40"},
    ).json()
    lights_queue = client.get(f"{BASE}/queues/{lights.id}").json()
    waste_queue = client.get(f"{BASE}/queues/{waste.id}").json()
    queues = client.get(f"{BASE}/queues").json()

    assert [item["number"] for item in lights_queue] == [created["number"]]
    assert lights_queue[0]["clock"]["deadline"] == "2026-03-12"
    assert waste_queue == []
    assert [(q["area"]["name"], q["open"]) for q in queues] == [("Alumbrado", 1), ("Higiene", 0)]


def test_a_queue_puts_the_closest_to_their_deadline_first(client):
    setup = Setup(signed_in(client), target_days=5)
    # Seen on Friday 13: received Monday 2 (overdue by 4), Monday 9 (1 left), Thursday 12 (4 left).
    late = setup.complaint("assigned", received_at=at(2))
    soon = setup.complaint("assigned", received_at=at(9))
    fresh = setup.complaint("received", received_at=at(12))
    # Paused with 4 left too: after the running one.
    paused = setup.complaint("waiting", received_at=at(2), target_days=5)
    setup.complaint("resolved", received_at=at(2))
    pin_clock(client, at(13))

    queue = client.get(f"{BASE}/queues/{setup.area.id}").json()

    assert [item["number"] for item in queue] == [
        late.number,
        soon.number,
        fresh.number,
        paused.number,
    ]
    assert [item["clock"]["left_days"] for item in queue] == [-4, 1, 4, 4]
    assert [item["clock"]["status"] for item in queue] == [
        "overdue",
        "at_risk",
        "on_time",
        "on_time",
    ]
    summary = client.get(f"{BASE}/queues").json()[0]
    assert (summary["open"], summary["overdue"], summary["at_risk"], summary["paused"]) == (
        4,
        1,
        1,
        1,
    )


def test_waiting_for_the_resident_does_not_use_up_time(client):
    setup = Setup(signed_in(client), target_days=5)
    pin_clock(client, at(2, hour=9))
    complaint_id = _create(client, setup).json()["id"]
    pin_clock(client, at(3))
    _move(client, complaint_id, "assigned")
    before = client.get(f"{BASE}/complaints/{complaint_id}").json()["clock"]

    waiting = _move(client, complaint_id, "waiting", "Pedimos la altura exacta")
    pin_clock(client, at(9))
    while_waiting = client.get(f"{BASE}/complaints/{complaint_id}").json()["clock"]
    back = _move(client, complaint_id, "in_progress", "El vecino respondió")

    assert before["left_days"] == 4
    assert waiting["clock"]["paused"] is True
    assert while_waiting["left_days"] == back["clock"]["left_days"] == 4
    assert back["clock"]["paused"] is False
    assert [e["to_state"] for e in back["timeline"]] == [
        "received",
        "assigned",
        "waiting",
        "in_progress",
    ]
    assert [e["note"] for e in back["timeline"][-2:]] == [
        "Pedimos la altura exacta",
        "El vecino respondió",
    ]


def test_an_editor_reassigns_an_open_complaint(client):
    setup = Setup(signed_in(client))
    works = make_area(setup.municipality, "Obras Públicas")
    complaint = setup.complaint("in_progress")

    response = client.post(
        f"{BASE}/complaints/{complaint.id}/assignment",
        json={"area_id": str(works.id), "note": "Es un poste caído"},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["area"]["name"] == "Obras Públicas"
    assert body["state"] == "in_progress"
    last = body["timeline"][-1]
    assert (last["kind"], last["from_area"]["name"], last["to_area"]["name"], last["note"]) == (
        "reassigned",
        setup.area.name,
        "Obras Públicas",
        "Es un poste caído",
    )
    assert [c["id"] for c in client.get(f"{BASE}/queues/{works.id}").json()] == [str(complaint.id)]
    assert client.get(f"{BASE}/queues/{setup.area.id}").json() == []


def test_reassigning_to_the_same_area_or_a_finished_complaint_is_refused(client):
    setup = Setup(signed_in(client))
    other = make_area(setup.municipality, "Otra")
    open_one, closed_one = setup.complaint("assigned"), setup.complaint("closed")

    same = client.post(
        f"{BASE}/complaints/{open_one.id}/assignment", json={"area_id": str(setup.area.id)}
    )
    finished = client.post(
        f"{BASE}/complaints/{closed_one.id}/assignment", json={"area_id": str(other.id)}
    )

    assert same.status_code == 422
    assert finished.status_code == 409
    assert finished.json()["error"]["code"] == "case_not_open"


def test_changing_the_type_brings_its_target_and_is_on_the_timeline(client):
    setup = Setup(signed_in(client), target_days=5)
    pole = make_type(setup.municipality, setup.area, "Poste dañado", target_days=10)
    complaint = setup.complaint("assigned")

    body = client.patch(
        f"{BASE}/complaints/{complaint.id}",
        json={"type_id": str(pole.id), "address": "Mitre 41"},
    ).json()

    assert (body["type"]["name"], body["address"], body["clock"]["target_days"]) == (
        "Poste dañado",
        "Mitre 41",
        10,
    )
    last = body["timeline"][-1]
    assert (last["kind"], last["from_type"]["name"], last["to_type"]["name"]) == (
        "retyped",
        setup.type.name,
        "Poste dañado",
    )


def test_finished_complaints_are_not_edited_but_can_get_notes(client):
    setup = Setup(signed_in(client))
    complaint = setup.complaint("closed")
    path = f"{BASE}/complaints/{complaint.id}"

    edit = client.patch(path, json={"address": "Otra 1"})
    note = client.post(f"{path}/comments", json={"note": "El vecino agradeció"})

    assert edit.status_code == 409
    assert note.status_code == 201
    assert note.json()["timeline"][-1]["kind"] == "comment"
    assert client.post(f"{path}/comments", json={"note": " "}).status_code == 422


def test_complaints_are_listed_newest_first_and_filtered(client):
    setup = Setup(signed_in(client), target_days=5)
    north = make_zone(setup.municipality, "Norte")
    person = make_person(setup.municipality, "Pedro", "Gómez", "30111222")
    first = setup.complaint("assigned", received_at=at(2), address="Mitre 10")
    second = setup.complaint("resolved", received_at=at(3), address="Belgrano 20", person=person)
    third = setup.complaint("received", received_at=at(12), address="Mitre 30")
    setup.complaint("rejected", received_at=at(4), address="Sarmiento 1")
    pin_clock(client, at(13))

    def numbers(**params):
        response = client.get(f"{BASE}/complaints", params=params)
        assert response.status_code == 200, response.text
        return [item["number"] for item in response.json()["items"]]

    assert numbers() == [third.number, 4, second.number, first.number]
    assert numbers(state="open") == [third.number, first.number]
    assert numbers(state="resolved") == [second.number]
    assert numbers(q="mitre") == [third.number, first.number]
    assert numbers(q="gomez") == [second.number]
    assert numbers(q=str(second.number)) == [second.number]
    assert numbers(status="overdue") == [first.number]
    assert numbers(zone_id=str(north.id)) == []
    assert numbers(area_id=str(setup.area.id), state="open") == [third.number, first.number]
    page = client.get(f"{BASE}/complaints", params={"limit": 2, "offset": 1}).json()
    assert (len(page["items"]), page["total"]) == (2, 4)
    overdue_page = client.get(f"{BASE}/complaints", params={"status": "on_time", "limit": 1}).json()
    assert overdue_page["total"] == 2


def test_another_municipalitys_complaints_are_invisible(client):
    other = Setup(complaints_member("admin", email="x@saira.test", municipality_name="Saira"))
    foreign = other.complaint("assigned")
    setup = Setup(signed_in(client, "admin"))
    mine = setup.complaint("assigned")
    path = f"{BASE}/complaints/{foreign.id}"

    assert client.get(path).status_code == 404
    assert client.patch(path, json={"address": "x"}).status_code == 404
    assert client.post(f"{path}/transitions", json={"to_state": "in_progress"}).status_code == 404
    assert client.post(f"{path}/comments", json={"note": "x"}).status_code == 404
    assert (
        client.post(f"{path}/assignment", json={"area_id": str(setup.area.id)}).status_code == 404
    )
    assert client.get(f"{BASE}/queues/{other.area.id}").status_code == 404
    listed = client.get(f"{BASE}/complaints").json()
    assert [item["id"] for item in listed["items"]] == [str(mine.id)]
    assert [q["area"]["id"] for q in client.get(f"{BASE}/queues").json()] == [str(setup.area.id)]


def test_another_municipalitys_types_zones_areas_and_people_cannot_be_referenced(client):
    other = Setup(complaints_member("admin", email="x@saira.test", municipality_name="Saira"))
    their_person = make_person(other.municipality)
    setup = Setup(signed_in(client, "admin"))
    mine = setup.complaint("assigned")

    attempts = {
        "type_id": _create(client, setup, type_id=str(other.type.id)),
        "zone_id": _create(client, setup, zone_id=str(other.zone.id)),
        "person_id": _create(client, setup, person_id=str(their_person.id)),
        "reassign": client.post(
            f"{BASE}/complaints/{mine.id}/assignment", json={"area_id": str(other.area.id)}
        ),
        "retype": client.patch(
            f"{BASE}/complaints/{mine.id}", json={"type_id": str(other.type.id)}
        ),
        "rezone": client.patch(
            f"{BASE}/complaints/{mine.id}", json={"zone_id": str(other.zone.id)}
        ),
        "new type": client.post(
            f"{BASE}/types",
            json={"name": "x", "area_id": str(other.area.id), "target_days": 3},
        ),
    }

    assert {name: r.status_code for name, r in attempts.items()} == dict.fromkeys(attempts, 422)
    assert all(r.json()["error"]["code"] == "invalid_reference" for r in attempts.values())
    assert client.get(f"{BASE}/people/lookup", params={"dni": "33123456"}).json()["person"] is None
    detail = client.get(f"{BASE}/complaints/{mine.id}").json()
    assert (detail["area"]["id"], detail["type"]["id"], detail["zone"]["id"]) == (
        str(setup.area.id),
        str(setup.type.id),
        str(setup.zone.id),
    )


def test_the_other_municipalitys_member_sees_none_of_these(client):
    setup = Setup(complaints_member("admin"))
    setup.complaint("assigned")
    complaints_member("admin", email="b@saira.test", municipality_name="Saira")
    login(client, "b@saira.test")

    assert client.get(f"{BASE}/complaints").json() == {"items": [], "total": 0}
    for path in ("types", "areas", "zones", "queues"):
        assert client.get(f"{BASE}/{path}").json() == [], path
    assert client.get(f"{BASE}/summary").json()["totals"]["received"] == 0
