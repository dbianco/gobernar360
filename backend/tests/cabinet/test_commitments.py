from datetime import date

import pytest

from tests.cabinet.factories import (
    URL,
    as_member,
    cabinet_member,
    close,
    commit,
    error,
    held,
    pin_today,
    prepare,
)
from tests.factories import make_membership, make_user


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def get(client, commitment) -> dict:
    return client.get(f"{URL}/commitments/{commitment['id']}").json()


def set_state(client, commitment, state, **fields):
    return client.post(
        f"{URL}/commitments/{commitment['id']}/state", json={"state": state} | fields
    )


def add_note(client, commitment, note="Avanza."):
    return client.post(f"{URL}/commitments/{commitment['id']}/notes", json={"note": note})


def test_a_commitment_says_what_who_when_and_where_it_was_taken(client):
    _, ana = cabinet_member(client)
    meeting = prepare(client)
    item = meeting["items"][0]

    taken = commit(client, item, ana, description="  Certificar la obra ")

    assert taken == {
        "id": taken["id"],
        "description": "Certificar la obra",
        "owner": {"id": str(ana.id), "full_name": "Ana"},
        "due_date": "2026-03-20",
        "state": "open",
        "completed_on": None,
        "times_postponed": 0,
        "subject": None,
        "item_id": item["id"],
        "meeting": {"id": meeting["id"], "date": "2026-03-10", "closed": False},
    }
    assert get(client, taken) == taken | {"history": []}


def test_a_commitment_becomes_overdue_by_itself(client):
    _, ana = cabinet_member(client)
    [taken] = held(client, ana, date(2026, 3, 10))

    assert get(client, taken)["state"] == "open"
    pin_today(client, date(2026, 3, 11))
    assert get(client, taken)["state"] == "overdue"


@pytest.mark.parametrize(
    "change", [{"description": " "}, {"description": "x" * 501}, {"due_date": None}, {"extra": 1}]
)
def test_a_commitment_needs_a_description_and_a_date(client, change):
    _, ana = cabinet_member(client)
    item = prepare(client)["items"][0]
    body = {"description": "x", "owner_id": str(ana.id), "due_date": "2026-04-01"} | change

    response = client.post(f"{URL}/items/{item['id']}/commitments", json=body)

    assert error(response) == (422, "validation_error")


def test_while_its_meeting_is_open_a_commitment_is_corrected_or_removed(client):
    _, ana = cabinet_member(client)
    meeting = prepare(client)
    taken = commit(client, meeting["items"][0], ana)
    other = commit(client, meeting["items"][0], ana, description="Por error")

    patched = client.patch(f"{URL}/commitments/{taken['id']}", json={"description": "Firmar"})
    assert (patched.status_code, patched.json()["description"]) == (200, "Firmar")
    assert client.delete(f"{URL}/commitments/{other['id']}").status_code == 204
    assert error(client.get(f"{URL}/commitments/{other['id']}")) == (404, "not_found")


# Follow-up


def test_it_is_marked_done_today_or_on_the_day_given(client):
    _, ana = cabinet_member(client)
    first, second = held(client, ana, date(2026, 3, 20), date(2026, 3, 20))

    assert set_state(client, first, "done").json()["completed_on"] == "2026-03-10"
    answer = set_state(client, second, "done", completed_on="2026-03-05").json()
    assert (answer["state"], answer["completed_on"]) == ("done", "2026-03-05")


def test_it_is_not_delivered_in_the_future_and_only_done_has_a_date(client):
    _, ana = cabinet_member(client)
    [taken] = held(client, ana, date(2026, 3, 20))

    future = set_state(client, taken, "done", completed_on="2026-03-11")
    assert future.json()["error"] == {
        "code": "validation_error",
        "message": "completed_on must not be in the future.",
    }
    assert set_state(client, taken, "done", completed_on="2026-03-10").status_code == 200
    dropped = set_state(client, taken, "dropped", completed_on="2026-03-05")
    assert error(dropped) == (422, "validation_error")
    # "overdue" comes from the date; nobody sets it.
    assert error(set_state(client, taken, "overdue")) == (422, "validation_error")


def test_its_history_keeps_every_change_and_note_newest_first(client):
    municipality, ana = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    [taken] = held(client, ana, date(2026, 3, 1))

    add_note(client, taken, " Pidieron prórroga. ")
    client.patch(
        f"{URL}/commitments/{taken['id']}",
        json={"due_date": "2026-04-01", "owner_id": str(leo.id)},
    )
    set_state(client, taken, "done", completed_on="2026-03-09", note="Firmado.")
    set_state(client, taken, "done", completed_on="2026-03-08")
    answer = set_state(client, taken, "open").json()

    assert (answer["state"], answer["completed_on"]) == ("open", None)
    assert [(e["author"], e["note"], e["changes"]) for e in answer["history"]] == [
        ("Ana", "", {"state": ["done", "open"]}),
        ("Ana", "", {"completed_on": ["2026-03-09", "2026-03-08"]}),
        ("Ana", "Firmado.", {"state": ["open", "done"], "completed_on": [None, "2026-03-09"]}),
        (
            "Ana",
            "",
            {"owner": ["Ana", "Leo"], "due_date": ["2026-03-01", "2026-04-01"]},
        ),
        ("Ana", "Pidieron prórroga.", {}),
    ]
    assert answer["history"] == get(client, taken)["history"]


def test_saying_the_same_again_adds_nothing_to_the_history(client):
    _, ana = cabinet_member(client)
    [taken] = held(client, ana, date(2026, 3, 1))

    client.patch(
        f"{URL}/commitments/{taken['id']}",
        json={"due_date": "2026-03-01", "owner_id": str(ana.id)},
    )
    set_state(client, taken, "open")
    set_state(client, taken, "dropped")
    set_state(client, taken, "dropped")

    history = get(client, taken)["history"]
    assert [e["changes"] for e in history] == [{"state": ["open", "dropped"]}]
    answer = set_state(client, taken, "dropped", note="Lo pidió el intendente.").json()
    assert answer["history"][0]["note"] == "Lo pidió el intendente."


def test_a_finished_commitment_is_not_given_another_date_or_owner(client):
    _, ana = cabinet_member(client)
    done, dropped = held(client, ana, date(2026, 3, 1), date(2026, 3, 1))
    set_state(client, done, "done")
    set_state(client, dropped, "dropped")

    for commitment in (done, dropped):
        refused = client.patch(
            f"{URL}/commitments/{commitment['id']}", json={"due_date": "2027-01-01"}
        )
        assert refused.status_code == 409
        assert refused.json()["error"] == {
            "code": "commitment_finished",
            "message": "The commitment is no longer open.",
        }
        assert get(client, commitment)["due_date"] == "2026-03-01"


def test_whoever_owes_it_adds_notes_whatever_their_level_and_others_need_to_be_editors(client):
    municipality, ana = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality, grants={"cabinet": "viewer"}, enable=[])
    meeting = prepare(client)
    his = commit(client, meeting["items"][0], leo)
    hers = commit(client, meeting["items"][0], ana)
    close(client, meeting)
    as_member(client, "leo@noetinger.test")

    noted = add_note(client, his)
    assert noted.status_code == 201
    assert [(e["author"], e["note"]) for e in noted.json()["history"]] == [("Leo", "Avanza.")]
    assert error(add_note(client, hers)) == (403, "forbidden")
    # Saying it is done is not his call.
    assert error(set_state(client, his, "done")) == (403, "forbidden")
    as_member(client)
    assert add_note(client, his).status_code == 201
    assert error(add_note(client, his, "  ")) == (422, "validation_error")


# Lists


def test_commitments_are_listed_open_first_by_due_date_and_filtered(client):
    municipality, ana = cabinet_member(client)
    late, soon, done, dropped = held(
        client,
        ana,
        date(2026, 3, 9),
        date(2026, 3, 10),
        date(2026, 1, 1),
        date(2026, 1, 2),
    )
    set_state(client, done, "done")
    set_state(client, dropped, "dropped")
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    meeting = prepare(client)
    his = commit(
        client, meeting["items"][0], leo, date(2026, 5, 1), description="Señalización vial"
    )

    def listed(**params):
        page = client.get(f"{URL}/commitments", params=params).json()
        assert page["total"] == len(page["items"])
        return [c["id"] for c in page["items"]]

    late, soon, done, dropped, his = (c["id"] for c in (late, soon, done, dropped, his))
    assert listed() == [late, soon, his, done, dropped]
    assert listed(state="pending") == [late, soon, his]
    assert listed(state="overdue") == [late]
    assert listed(state="open") == [soon, his]
    assert listed(state="done") == [done]
    assert listed(state="dropped") == [dropped]
    assert listed(owner_id=str(leo.id)) == [his]
    assert listed(mine="true") == [late, soon, done, dropped]
    assert listed(mine="true", state="pending") == [late, soon]
    assert listed(q="senalizacion") == [his]
    assert listed(q="leo vial") == [his]
    assert listed(q="nada") == []
    page = client.get(f"{URL}/commitments", params={"limit": 2, "offset": 1}).json()
    assert (page["total"], [c["id"] for c in page["items"]]) == (5, [soon, his])
    assert client.get(f"{URL}/commitments?state=late").status_code == 422


def test_the_list_goes_by_due_date_and_only_open_ones_are_in_time(client):
    _, ana = cabinet_member(client)
    second, first, done = held(client, ana, date(2026, 5, 2), date(2026, 5, 1), date(2026, 6, 1))
    set_state(client, done, "done")

    def listed(**params):
        page = client.get(f"{URL}/commitments", params=params).json()
        return [c["id"] for c in page["items"]]

    assert listed() == [first["id"], second["id"], done["id"]]
    assert listed(state="open") == [first["id"], second["id"]]


def test_my_commitments_are_mine_whoever_is_asked_for(client):
    municipality, ana = cabinet_member(client)
    held(client, ana, date(2026, 3, 9))
    _, leo = cabinet_member(client, "viewer", "leo@noetinger.test", municipality)

    page = client.get(f"{URL}/commitments?mine=true&owner_id={ana.id}").json()

    assert page == {"items": [], "total": 0}
