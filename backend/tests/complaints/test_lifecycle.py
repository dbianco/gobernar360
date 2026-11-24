"""Moving complaints between states: only valid moves, each one signed and kept."""

from datetime import datetime
from types import SimpleNamespace

import pytest

from gobernar360.dashboards.complaints.lifecycle import STATES, TRANSITIONS
from tests.complaints.factories import BASE, HISTORIES, Setup, at, pin_clock, signed_in

VALID = [(source, target) for source in STATES for target in TRANSITIONS[source]]
INVALID = [
    (source, target) for source in STATES for target in STATES if target not in TRANSITIONS[source]
]


def _move(client, complaint, to_state, note="ok"):
    return client.post(
        f"{BASE}/complaints/{complaint.id}/transitions", json={"to_state": to_state, "note": note}
    )


def test_the_table_covers_every_pair_of_states():
    assert len(VALID) + len(INVALID) == len(STATES) ** 2
    assert set(HISTORIES) == set(STATES)


@pytest.mark.parametrize(("source", "target"), INVALID)
def test_every_invalid_transition_is_rejected(client, source, target):
    setup = Setup(signed_in(client))
    complaint = setup.complaint(source)
    pin_clock(client, at(10))

    response = _move(client, complaint, target)

    assert response.status_code == 409, response.text
    assert response.json()["error"]["code"] == "invalid_transition"
    detail = client.get(f"{BASE}/complaints/{complaint.id}").json()
    assert detail["state"] == source
    assert len(detail["timeline"]) == len(HISTORIES[source]) + 1


@pytest.mark.parametrize(("source", "target"), VALID)
def test_every_valid_transition_is_accepted_and_recorded(client, source, target):
    setup = Setup(signed_in(client))
    complaint = setup.complaint(source)
    pin_clock(client, at(10, hour=11))

    response = _move(client, complaint, target, note="  Visto en el lugar  ")

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["state"] == target
    last = body["timeline"][-1]
    assert last["kind"] == "transition"
    assert (last["from_state"], last["to_state"]) == (source, target)
    assert last["note"] == "Visto en el lugar"
    assert last["user"]["full_name"] == "Ana"
    assert datetime.fromisoformat(last["at"]) == at(10, hour=11)


def test_the_moves_offered_are_exactly_the_valid_ones(client):
    setup = Setup(signed_in(client))

    for state in STATES:
        complaint = setup.complaint(state)
        moves = client.get(f"{BASE}/complaints/{complaint.id}").json()["moves"]
        assert moves == list(TRANSITIONS[state]), state


def test_a_complaint_never_resolved_cannot_be_closed(client):
    setup = Setup(signed_in(client))
    complaint = setup.complaint("in_progress")

    assert "closed" not in client.get(f"{BASE}/complaints/{complaint.id}").json()["moves"]
    response = _move(client, complaint, "closed")

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_transition"


def test_an_unknown_state_is_not_valid(client):
    setup = Setup(signed_in(client))

    response = _move(client, setup.complaint(), "archived")

    assert response.status_code == 422


@pytest.mark.parametrize(("source", "target"), [("assigned", "rejected"), ("resolved", "reopened")])
def test_rejecting_and_reopening_need_a_note(client, source, target):
    setup = Setup(signed_in(client))
    complaint = setup.complaint(source)

    response = _move(client, complaint, target, note="   ")

    assert response.status_code == 422
    assert client.get(f"{BASE}/complaints/{complaint.id}").json()["state"] == source


def test_reopening_keeps_the_timeline(client):
    setup = Setup(signed_in(client))
    pin_clock(client, at(2, hour=9))
    created = client.post(
        f"{BASE}/complaints",
        json={
            "type_id": str(setup.type.id),
            "zone_id": str(setup.zone.id),
            "address": "Belgrano 5",
        },
    ).json()
    complaint = SimpleNamespace(id=created["id"])
    steps = [
        (at(2, hour=12), "assigned", ""),
        (at(3), "in_progress", "Cuadrilla en camino"),
        (at(4), "resolved", "Se cambió la lámpara"),
        (at(9), "reopened", "Volvió a apagarse"),
        (at(10), "resolved", "Se cambió el fotocontrol"),
        (at(11), "closed", "El vecino confirmó"),
    ]
    for moment, state, note in steps:
        pin_clock(client, moment)
        assert _move(client, complaint, state, note).status_code == 201

    timeline = client.get(f"{BASE}/complaints/{complaint.id}").json()["timeline"]

    assert [(e["kind"], e["to_state"]) for e in timeline] == [("created", "received")] + [
        ("transition", state) for _, state, _ in steps
    ]
    assert [e["note"] for e in timeline[1:]] == [note for _, _, note in steps]
    assert all(e["user"]["full_name"] == "Ana" for e in timeline)


def test_reopened_work_counts_in_the_resolution_time(client):
    setup = Setup(signed_in(client), target_days=3)
    complaint = setup.complaint("received", received_at=at(2, hour=9))
    for moment, state in [
        (at(2), "assigned"),
        (at(3), "resolved"),
        (at(9), "reopened"),
        (at(10), "resolved"),
    ]:
        pin_clock(client, moment)
        _move(client, complaint, state)

    clock = client.get(f"{BASE}/complaints/{complaint.id}").json()["clock"]

    # Tuesday 3 to Tuesday 10, without subtracting the days it was wrongly resolved.
    assert clock["used_days"] == 6
    assert clock["status"] == "overdue"
    assert clock["resolved_on"] == "2026-03-10"


def test_a_viewer_cannot_change_anything(client):
    setup = Setup(signed_in(client, "viewer"))
    complaint = setup.complaint("assigned")
    path = f"{BASE}/complaints/{complaint.id}"

    attempts = [
        client.post(f"{path}/transitions", json={"to_state": "in_progress"}),
        client.post(f"{path}/assignment", json={"area_id": str(setup.area.id)}),
        client.post(f"{path}/comments", json={"note": "hola"}),
        client.patch(path, json={"address": "Otra 1"}),
        client.post(
            f"{BASE}/complaints",
            json={"type_id": str(setup.type.id), "zone_id": str(setup.zone.id), "address": "x"},
        ),
        client.get(f"{BASE}/people/lookup", params={"dni": "33123456"}),
    ]

    assert [response.status_code for response in attempts] == [403] * len(attempts)
    detail = client.get(path).json()
    assert detail["state"] == "assigned"
    assert detail["address"] == "San Martín 100"
    assert len(detail["timeline"]) == 2


def test_a_member_without_the_dashboard_reads_nothing(client):
    signed_in(client, None)

    for path in ("complaints", "types", "areas", "zones", "calendar", "queues", "summary"):
        assert client.get(f"{BASE}/{path}").status_code == 403, path
