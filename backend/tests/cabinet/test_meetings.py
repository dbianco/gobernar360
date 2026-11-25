import uuid
from datetime import date
from types import SimpleNamespace

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.cabinet.meetings_router import _open_meeting
from gobernar360.dashboards.cabinet.models import Meeting
from gobernar360.platform.models import AuditLog
from tests.cabinet.factories import (
    TODAY,
    URL,
    as_member,
    cabinet_member,
    close,
    commit,
    error,
    held,
    make_simple_project,
    pin_today,
    prepare,
    project_subject,
)
from tests.factories import admin_session, make_membership, make_municipality, make_user


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def get(client, meeting) -> dict:
    return client.get(f"{URL}/meetings/{meeting['id']}").json()


def postponed(client, commitment) -> int:
    return client.get(f"/api/commitments/{commitment['id']}").json()["times_postponed"]


def test_a_meeting_is_prepared_with_its_date_attendees_guests_and_agenda(client):
    municipality, ana = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)

    meeting = prepare(
        client,
        agenda=["Obras", "Feria"],
        attendee_ids=[str(leo.id), str(ana.id), str(leo.id)],
        guests=" Ing. Funes ",
    )

    assert meeting | {"items": None, "id": None} == {
        "id": None,
        "date": "2026-03-10",
        "closed": False,
        "closed_at": None,
        "attendees": [
            {"id": str(ana.id), "full_name": "Ana"},
            {"id": str(leo.id), "full_name": "Leo"},
        ],
        "guests": "Ing. Funes",
        "notes": "",
        "items": None,
        "carried_over": [],
    }
    assert [i["title"] for i in meeting["items"]] == ["Obras", "Feria"]
    assert get(client, meeting) == meeting


def test_only_one_meeting_is_open_at_a_time(client):
    cabinet_member(client)
    meeting = prepare(client)

    second = client.post(f"{URL}/meetings", json={"date": "2026-03-11"})

    assert second.status_code == 409
    assert second.json()["error"] == {
        "code": "meeting_already_open",
        "message": "Close the open meeting before preparing another.",
    }
    close(client, meeting)
    prepare(client, date(2026, 3, 11))


def test_two_municipalities_may_each_have_an_open_meeting(client):
    cabinet_member(client)
    prepare(client)
    cabinet_member(client, email="beto@saira.test", municipality_name="Saira")

    prepare(client)


def test_a_meeting_is_never_dated_before_the_last_one(client):
    cabinet_member(client)
    close(client, prepare(client, date(2026, 3, 5)))

    early = client.post(f"{URL}/meetings", json={"date": "2026-03-04"})
    assert early.status_code == 422
    assert early.json()["error"] == {
        "code": "meeting_before_last",
        "message": "A meeting cannot be dated before the last one.",
    }
    meeting = prepare(client, date(2026, 3, 5))  # the same day is fine
    moved = client.patch(f"{URL}/meetings/{meeting['id']}", json={"date": "2026-03-04"})
    assert error(moved) == (422, "meeting_before_last")


def test_meetings_are_listed_latest_first_with_their_counts(client):
    _, ana = cabinet_member(client)
    first = prepare(client, date(2026, 2, 1), ["Obras", "Feria"])
    commit(client, first["items"][0], ana)
    commit(client, first["items"][1], ana)
    close(client, first)
    second = prepare(client, date(2026, 2, 1), [])

    page = client.get(f"{URL}/meetings").json()

    assert page["total"] == 2
    assert [
        (m["id"], m["date"], m["closed"], m["items"], m["commitments"]) for m in page["items"]
    ] == [
        (second["id"], "2026-02-01", False, 0, 0),
        (first["id"], "2026-02-01", True, 2, 2),
    ]
    assert page["items"][0]["closed_at"] is None and page["items"][1]["closed_at"]
    paged = client.get(f"{URL}/meetings", params={"limit": 1, "offset": 1}).json()
    assert [m["id"] for m in paged["items"]] == [first["id"]]


def test_meetings_are_searched_by_what_was_written_in_them(client):
    _, ana = cabinet_member(client)
    first = prepare(client, date(2026, 2, 1), ["Señalización", "Feria"], guests="Ing. Funes")
    commit(client, first["items"][0], ana, description="Comprar carteles")
    client.patch(f"{URL}/items/{first['items'][1]['id']}", json={"notes": "En la plaza"})
    client.patch(f"{URL}/meetings/{first['id']}", json={"notes": "Cierre breve"})
    close(client, first)
    second = prepare(client, agenda=["Feria"])

    def found(q):
        page = client.get(f"{URL}/meetings", params={"q": q}).json()
        assert page["total"] == len(page["items"])
        return [m["id"] for m in page["items"]]

    for q in ("senalizacion", "carteles", "PLAZA", "breve", "funes", "feria carteles"):
        assert found(q) == [first["id"]], q
    assert found("feria") == [second["id"], first["id"]]
    assert found("feria nada") == []


def test_an_open_meeting_is_edited(client):
    municipality, ana = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    meeting = prepare(client, attendee_ids=[str(ana.id)])

    response = client.patch(
        f"{URL}/meetings/{meeting['id']}",
        json={
            "date": "2026-03-12",
            "attendee_ids": [str(leo.id)],
            "guests": "Prensa",
            "notes": "Se aprobó todo.",
        },
    )

    assert response.status_code == 200
    assert response.json() == get(client, meeting)
    edited = response.json()
    assert (edited["date"], edited["guests"], edited["notes"]) == (
        "2026-03-12",
        "Prensa",
        "Se aprobó todo.",
    )
    assert [a["full_name"] for a in edited["attendees"]] == ["Leo"]
    client.patch(f"{URL}/meetings/{meeting['id']}", json={"attendee_ids": []})
    assert get(client, meeting)["attendees"] == []


def test_attendees_and_owners_must_be_active_members_of_the_municipality(client):
    municipality, _ = cabinet_member(client)
    stranger = make_user("beto@saira.test")
    make_membership(stranger, make_municipality("Saira"))
    inactive = make_user("ida@noetinger.test", active=False)
    make_membership(inactive, municipality)
    meeting = prepare(client)

    for user in (stranger, inactive):
        ids = [str(user.id)]
        refused = client.patch(f"{URL}/meetings/{meeting['id']}", json={"attendee_ids": ids})
        assert refused.status_code == 422
        assert refused.json()["error"] == {
            "code": "invalid_reference",
            "message": "attendee_ids does not reference a member of the municipality.",
        }
        refused = client.post(
            f"{URL}/items/{meeting['items'][0]['id']}/commitments",
            json={"description": "x", "owner_id": str(user.id), "due_date": "2026-03-20"},
        )
        assert refused.json()["error"] == {
            "code": "invalid_reference",
            "message": "owner_id does not reference a member of the municipality.",
        }


def test_an_attendee_who_left_the_municipality_stays_in_the_meeting(client):
    municipality, ana = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    membership = make_membership(leo, municipality)
    meeting = prepare(client, attendee_ids=[str(leo.id)])
    with admin_session() as session, session.begin():
        session.delete(session.merge(membership))

    response = client.patch(
        f"{URL}/meetings/{meeting['id']}", json={"attendee_ids": [str(leo.id), str(ana.id)]}
    )

    assert [a["full_name"] for a in response.json()["attendees"]] == ["Ana", "Leo"]


def test_agenda_items_are_added_changed_ordered_and_removed(client):
    municipality, _ = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    meeting = prepare(client, agenda=["Obras", "Feria"])
    url = f"{URL}/meetings/{meeting['id']}/items"

    added = client.post(url, json={"title": "Clima", "subject": project_subject(project)})
    assert added.status_code == 201
    obras, feria, clima = added.json()["items"]
    assert (clima["title"], clima["subject"]["label"]) == ("Clima", "Pavimentación")

    ids = [clima["id"], obras["id"], feria["id"]]
    ordered = client.put(f"{url}/order", json={"item_ids": ids}).json()
    assert [i["id"] for i in ordered["items"]] == ids

    changed = client.patch(
        f"{URL}/items/{clima['id']}", json={"title": "Obra vial", "subject": None}
    ).json()
    assert (changed["items"][0]["title"], changed["items"][0]["subject"]) == ("Obra vial", None)

    assert client.delete(f"{URL}/items/{obras['id']}").status_code == 204
    assert [i["id"] for i in get(client, meeting)["items"]] == [clima["id"], feria["id"]]


def test_the_first_item_of_an_empty_agenda_can_be_added(client):
    cabinet_member(client)
    meeting = prepare(client, agenda=[])

    added = client.post(f"{URL}/meetings/{meeting['id']}/items", json={"title": "Clima"})

    assert [i["title"] for i in added.json()["items"]] == ["Clima"]


def test_ordering_takes_every_item_of_the_meeting_once(client):
    cabinet_member(client)
    meeting = prepare(client, agenda=["Obras", "Feria"])
    url = f"{URL}/meetings/{meeting['id']}/items/order"
    first, second = (i["id"] for i in meeting["items"])

    for ids in ([first], [first, first], [first, second, second]):
        refused = client.put(url, json={"item_ids": ids})
        assert refused.json()["error"] == {
            "code": "invalid_reference",
            "message": "item_ids must be the items of the meeting, each once.",
        }


def test_writing_notes_marks_an_item_as_discussed_unless_told_otherwise(client):
    cabinet_member(client)
    meeting = prepare(client, agenda=["Obras", "Feria", "Clima"])
    obras, feria, clima = (f"{URL}/items/{i['id']}" for i in meeting["items"])

    client.patch(obras, json={"notes": "Avanza."})
    client.patch(feria, json={"notes": "Queda para la próxima.", "discussed": False})
    client.patch(clima, json={"notes": "  "})

    items = get(client, meeting)["items"]
    assert [(i["notes"], i["discussed"]) for i in items] == [
        ("Avanza.", True),
        ("Queda para la próxima.", False),
        ("", False),
    ]


def test_taking_a_commitment_marks_its_item_as_discussed(client):
    _, ana = cabinet_member(client)
    meeting = prepare(client, agenda=["Obras", "Feria"])

    taken = commit(client, meeting["items"][0], ana)

    items = get(client, meeting)["items"]
    assert [i["discussed"] for i in items] == [True, False]
    assert items[0]["commitments"] == [taken]


def test_items_proposed_by_the_system_cannot_be_renamed_or_linked(client):
    _, ana = cabinet_member(client)
    [late] = held(client, ana, date(2026, 3, 1))
    meeting = prepare(client, agenda=[{"key": f"commitment:{late['id']}"}])
    url = f"{URL}/items/{meeting['items'][0]['id']}"

    for change in ({"title": "Otro"}, {"subject": None}):
        refused = client.patch(url, json=change)
        assert refused.status_code == 422
        assert refused.json()["error"] == {
            "code": "validation_error",
            "message": "Only items typed by a person can be renamed or linked.",
        }
    assert client.patch(url, json={"notes": "Falta poco."}).status_code == 200


def test_an_item_with_commitments_cannot_be_removed_nor_its_meeting_discarded(client):
    _, ana = cabinet_member(client)
    meeting = prepare(client)
    commit(client, meeting["items"][0], ana)

    assert error(client.delete(f"{URL}/items/{meeting['items'][0]['id']}")) == (409, "in_use")
    assert error(client.delete(f"{URL}/meetings/{meeting['id']}")) == (409, "in_use")


# Carrying over


def test_open_commitments_carry_over_to_the_next_meeting_and_count_once(client):
    _, ana = cabinet_member(client)
    late, later, done, dropped = held(
        client, ana, date(2026, 3, 1), date(2026, 9, 1), date(2026, 3, 1), date(2026, 3, 1)
    )
    client.post(f"/api/commitments/{done['id']}/state", json={"state": "done"})
    client.post(f"/api/commitments/{dropped['id']}/state", json={"state": "dropped"})

    meeting = prepare(client)

    # Whatever its due date: it was not done by the next meeting.
    assert [(c["id"], c["times_postponed"]) for c in meeting["carried_over"]] == [
        (late["id"], 1),
        (later["id"], 1),
    ]
    assert [postponed(client, c) for c in (late, later, done, dropped)] == [1, 1, 0, 0]
    # Nothing done to that meeting counts again: looking, editing, failing to prepare another.
    get(client, meeting)
    client.patch(f"{URL}/meetings/{meeting['id']}", json={"date": "2026-03-15"})
    client.post(f"{URL}/meetings", json={"date": "2026-03-20"})
    close(client, meeting)
    assert [postponed(client, c) for c in (late, later)] == [1, 1]

    prepare(client, date(2026, 3, 20))
    assert [postponed(client, c) for c in (late, later)] == [2, 2]


def test_the_commitments_of_a_meeting_are_not_carried_over_to_itself(client):
    _, ana = cabinet_member(client)
    meeting = prepare(client)
    taken = commit(client, meeting["items"][0], ana)
    close(client, meeting)

    assert get(client, meeting)["carried_over"] == []
    assert postponed(client, taken) == 0


def test_discarding_a_meeting_undoes_what_it_carried_over(client):
    _, ana = cabinet_member(client)
    [late] = held(client, ana, date(2026, 3, 1))
    meeting = prepare(client, agenda=[{"key": f"commitment:{late['id']}"}, "Feria"])
    assert postponed(client, late) == 1

    assert client.delete(f"{URL}/meetings/{meeting['id']}").status_code == 204

    assert postponed(client, late) == 0
    assert client.get(f"{URL}/meetings/{meeting['id']}").status_code == 404
    prepare(client)
    assert postponed(client, late) == 1


# Closing


def test_a_closed_meeting_cannot_be_edited(client):
    municipality, ana = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    meeting = prepare(client, agenda=["Obras", "Feria"])
    obras, feria = meeting["items"]
    taken = commit(client, obras, ana)
    closed = close(client, meeting)
    assert closed["closed"] is True and closed["closed_at"]

    meeting_url = f"{URL}/meetings/{meeting['id']}"
    commitment_url = f"{URL}/commitments/{taken['id']}"
    new_commitment = {"description": "x", "owner_id": str(ana.id), "due_date": "2026-04-01"}
    attempts = [
        client.patch(meeting_url, json={"notes": "Otra cosa"}),
        client.patch(meeting_url, json={"date": "2026-03-15"}),
        client.patch(meeting_url, json={"attendee_ids": []}),
        client.patch(meeting_url, json={}),
        client.delete(meeting_url),
        client.post(f"{meeting_url}/close"),
        client.post(f"{meeting_url}/items", json={"title": "Tarde"}),
        client.put(f"{meeting_url}/items/order", json={"item_ids": [feria["id"], obras["id"]]}),
        client.patch(f"{URL}/items/{obras['id']}", json={"notes": "Otra cosa"}),
        client.patch(f"{URL}/items/{obras['id']}", json={"discussed": False}),
        client.delete(f"{URL}/items/{feria['id']}"),
        client.post(f"{URL}/items/{obras['id']}/commitments", json=new_commitment),
        # Nor what was agreed in it.
        client.patch(commitment_url, json={"description": "Otra cosa"}),
        client.patch(commitment_url, json={"subject": project_subject(project)}),
        client.delete(commitment_url),
    ]
    for response in attempts:
        assert response.status_code == 409, response.request.url
        assert response.json()["error"] == {
            "code": "meeting_closed",
            "message": "The meeting is closed: its minutes are frozen.",
        }
    assert get(client, meeting) == closed


def test_writing_to_a_meeting_waits_for_whoever_is_closing_it(client):
    """Without the lock a commitment could slip in after the minutes were copied."""
    municipality, _ = cabinet_member(client)
    meeting = prepare(client)
    with admin_session() as closing, closing.begin():
        closing.get(Meeting, uuid.UUID(meeting["id"]), with_for_update=True)
        with pytest.raises(OperationalError, match="lock timeout"):
            with tenant_session(municipality.id) as db:
                db.execute(text("SET LOCAL lock_timeout = '100ms'"))
                _open_meeting(SimpleNamespace(db=db), uuid.UUID(meeting["id"]))


def test_a_meeting_that_does_not_exist_cannot_be_written_to(client):
    cabinet_member(client)
    nowhere = "00000000-0000-0000-0000-000000000000"

    assert error(client.post(f"{URL}/meetings/{nowhere}/close")) == (404, "not_found")
    assert error(client.patch(f"{URL}/items/{nowhere}", json={})) == (404, "not_found")
    assert error(client.get(f"{URL}/meetings/{nowhere}")) == (404, "not_found")


# Access and isolation


def test_viewers_read_but_do_not_write(client):
    municipality, ana = cabinet_member(client)
    meeting = prepare(client)
    item = meeting["items"][0]
    taken = commit(client, item, ana)
    cabinet_member(client, "viewer", "leo@noetinger.test", municipality)

    assert client.get(f"{URL}/meetings").status_code == 200
    assert get(client, meeting)["id"] == meeting["id"]
    commitment_url = f"{URL}/commitments/{taken['id']}"
    for response in (
        client.post(f"{URL}/meetings", json={"date": "2026-03-10"}),
        client.patch(f"{URL}/meetings/{meeting['id']}", json={"notes": "x"}),
        client.delete(f"{URL}/meetings/{meeting['id']}"),
        client.post(f"{URL}/meetings/{meeting['id']}/close"),
        client.post(f"{URL}/meetings/{meeting['id']}/items", json={"title": "x"}),
        client.put(f"{URL}/meetings/{meeting['id']}/items/order", json={"item_ids": []}),
        client.patch(f"{URL}/items/{item['id']}", json={"notes": "x"}),
        client.delete(f"{URL}/items/{item['id']}"),
        client.post(
            f"{URL}/items/{item['id']}/commitments",
            json={"description": "x", "owner_id": str(ana.id), "due_date": "2026-04-01"},
        ),
        client.patch(commitment_url, json={"description": "x"}),
        client.delete(commitment_url),
        client.post(f"/api/commitments/{taken['id']}/state", json={"state": "done"}),
    ):
        assert error(response) == (403, "forbidden"), response.request.url


def test_members_without_the_dashboard_see_nothing(client):
    cabinet_member(client, None, others={"projects": "admin"})

    for path in ("meetings", "commitments", "summary", "export/commitments.csv"):
        assert client.get(f"{URL}/{path}").status_code == 403, path


def test_another_municipality_s_meetings_are_not_found(client):
    _, ana = cabinet_member(client)
    meeting = prepare(client, attendee_ids=[str(ana.id)])
    item = meeting["items"][0]
    taken = commit(client, item, ana)
    _, beto = cabinet_member(client, email="beto@saira.test", municipality_name="Saira")

    assert client.get(f"{URL}/meetings").json() == {"items": [], "total": 0}
    assert client.get(f"{URL}/commitments").json() == {"items": [], "total": 0}
    new_commitment = {"description": "x", "owner_id": str(beto.id), "due_date": "2026-04-01"}
    for response in (
        client.get(f"{URL}/meetings/{meeting['id']}"),
        client.get(f"{URL}/meetings/{meeting['id']}/minutes.html"),
        client.patch(f"{URL}/meetings/{meeting['id']}", json={"notes": "x"}),
        client.post(f"{URL}/meetings/{meeting['id']}/close"),
        client.post(f"{URL}/items/{item['id']}/commitments", json=new_commitment),
        client.get(f"/api/commitments/{taken['id']}"),
        client.post(f"/api/commitments/{taken['id']}/state", json={"state": "done"}),
        client.post(f"/api/commitments/{taken['id']}/notes", json={"note": "x"}),
    ):
        assert error(response) == (404, "not_found"), response.request.url
    as_member(client)
    assert get(client, meeting)["items"][0]["commitments"] == [taken]


def test_what_is_done_is_audited_without_repeating_the_minutes(client):
    cabinet_member(client)
    meeting = prepare(client, TODAY)
    close(client, meeting)

    with admin_session() as session:
        entries = session.execute(
            select(AuditLog.action, AuditLog.changes).where(
                AuditLog.entity_type == "cabinet_meetings", AuditLog.entity_id == meeting["id"]
            )
        ).all()
    by_action = {action: changes for action, changes in entries}
    assert by_action["create"]["date"] == "2026-03-10"
    assert list(by_action["update"]) == ["closed_at"]
