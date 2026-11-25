"""The agenda proposed for a new meeting."""

from datetime import date

import pytest

from tests.cabinet.factories import (
    TODAY,
    URL,
    as_member,
    cabinet_member,
    close,
    commit,
    error,
    held,
    make_light,
    make_simple_project,
    month_subject,
    pin_today,
    prepare,
    project_subject,
    proposal,
)

EVERY = {key: "viewer" for key in ("projects", "environment", "economic", "social", "procedures")}


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def keys(answer: dict) -> list[str]:
    return [p["key"] for p in answer["proposals"]]


def set_state(client, commitment, state="done"):
    response = client.post(f"/api/commitments/{commitment['id']}/state", json={"state": state})
    assert response.status_code == 200, response.text


def test_it_contains_exactly_the_lights_and_commitments_that_need_attention(client):
    municipality, ana = cabinet_member(client, others=EVERY)
    make_light(municipality, "projects", 2026, 3, "yellow")
    make_light(municipality, "environment", 2026, 2, "red")
    make_light(municipality, "environment", 2026, 1, "green")
    make_light(municipality, "economic", 2026, 2, "green")
    make_light(municipality, "economic", 2026, 1, "red")  # superseded
    make_light(municipality, "social", 2026, 4, "red")  # has not started
    make_light(municipality, "social", 2026, 3, "green")
    make_light(municipality, "procedures", 2025, 12, "red")
    overdue, due_today, before, on_the_day, after, done, dropped = held(
        client,
        ana,
        date(2026, 3, 9),
        date(2026, 3, 10),
        date(2026, 3, 16),
        date(2026, 3, 17),
        date(2026, 4, 1),
        date(2026, 3, 1),
        date(2026, 3, 1),
    )
    set_state(client, done)
    set_state(client, dropped, "dropped")

    answer = proposal(client, date(2026, 3, 17))

    assert keys(answer) == [
        # Red before yellow, then commitments by due date.
        "light:environment:2026-02",
        "light:procedures:2025-12",
        "light:projects:2026-03",
        f"commitment:{overdue['id']}",
        f"commitment:{due_today['id']}",
        f"commitment:{before['id']}",
        # Carried from the previous meeting: nothing, its one item was discussed.
    ]
    assert answer["to_carry_over"] == 5
    assert answer["previous_meeting_date"] == "2026-02-10"
    assert answer["dashboards_not_considered"] == 0
    assert on_the_day["due_date"] == "2026-03-17" and after["due_date"] == "2026-04-01"


def test_each_proposal_says_what_it_is_about(client):
    municipality, ana = cabinet_member(client, others={"environment": "viewer"})
    make_light(municipality, "environment", 2026, 2, "red")
    [overdue] = held(client, ana, date(2026, 3, 1))

    light, commitment = proposal(client)["proposals"]

    assert light == {
        "key": "light:environment:2026-02",
        "source": "light",
        "title": "Ambiental, febrero de 2026",
        "subject": {
            "access": "visible",
            "kind": "month",
            "dashboard_key": "environment",
            "ref": "2026-02",
            "label": "Ambiental, febrero de 2026",
            "path": "/d/environment",
            "color": "red",
        },
        "commitment": None,
        "carried": False,
    }
    assert commitment["title"] == "Compromiso 1"
    assert commitment["source"] == "commitment"
    assert commitment["subject"] is None
    assert commitment["commitment"]["id"] == overdue["id"]
    assert commitment["commitment"]["state"] == "overdue"


def test_commitments_are_proposed_by_due_date_whatever_order_they_were_taken_in(client):
    _, ana = cabinet_member(client)
    second, first = held(client, ana, date(2026, 3, 5), date(2026, 3, 1))

    assert keys(proposal(client)) == [f"commitment:{c['id']}" for c in (first, second)]
    meeting = prepare(client, agenda=[])
    assert [c["id"] for c in meeting["carried_over"]] == [first["id"], second["id"]]


def test_of_two_meetings_on_the_same_day_the_previous_one_is_the_last_closed(client):
    cabinet_member(client)
    for title in ("Mañana", "Tarde"):
        close(client, prepare(client, date(2026, 3, 1), [title]))

    assert [p["title"] for p in proposal(client)["proposals"]] == ["Tarde"]


def test_a_commitment_delivered_since_does_not_hide_what_comes_after_it(client):
    _, ana = cabinet_member(client)
    [finished] = held(client, ana, date(2026, 2, 20))
    meeting = prepare(client, date(2026, 3, 1), [{"key": f"commitment:{finished['id']}"}, "Feria"])
    close(client, meeting)
    set_state(client, finished)

    assert [p["title"] for p in proposal(client)["proposals"]] == ["Feria"]


def test_a_meeting_recorded_late_still_proposes_what_is_overdue_today(client):
    _, ana = cabinet_member(client)
    [overdue] = held(client, ana, date(2026, 3, 8))

    assert keys(proposal(client, date(2026, 3, 1))) == [f"commitment:{overdue['id']}"]


def test_last_month_in_red_is_proposed_though_this_month_is_already_green(client):
    municipality, _ = cabinet_member(client, others=EVERY)
    make_light(municipality, "environment", 2026, 2, "red")
    make_light(municipality, "environment", 2026, 3, "green")
    make_light(municipality, "social", 2026, 2, "yellow")
    make_light(municipality, "social", 2026, 3, "green")

    assert keys(proposal(client)) == ["light:environment:2026-02"]


def test_lights_of_dashboards_the_member_cannot_open_are_not_proposed(client):
    municipality, _ = cabinet_member(client, others={"projects": "viewer"})
    make_light(municipality, "environment", 2026, 2, "red")
    make_light(municipality, "projects", 2026, 2, "red")

    answer = proposal(client)

    assert keys(answer) == ["light:projects:2026-02"]
    # Said, without saying which or how they are.
    assert answer["dashboards_not_considered"] == 4
    assert "environment" not in str(answer)


def test_the_dashboard_s_own_light_and_only_this_municipality_s_count(client):
    other, _ = cabinet_member(client, email="beto@saira.test", municipality_name="Saira")
    make_light(other, "cabinet", 2026, 2, "red")
    municipality, _ = cabinet_member(client)

    assert keys(proposal(client)) == []
    make_light(municipality, "cabinet", 2026, 2, "yellow")
    assert keys(proposal(client)) == ["light:cabinet:2026-02"]


def test_undiscussed_items_of_the_previous_meeting_come_last_in_their_order(client):
    municipality, ana = cabinet_member(client, others=EVERY)
    first = prepare(client, date(2026, 2, 1), ["Vieja"])
    close(client, first)
    meeting = prepare(client, date(2026, 2, 10), ["Feria", "Tránsito", "Clima"])
    client.patch(f"{URL}/items/{meeting['items'][1]['id']}", json={"discussed": True})
    close(client, meeting)
    make_light(municipality, "environment", 2026, 2, "red")

    answer = proposal(client)

    feria, clima = meeting["items"][0], meeting["items"][2]
    assert keys(answer) == [
        "light:environment:2026-02",
        f"item:{feria['id']}",
        f"item:{clima['id']}",
    ]
    assert [p["title"] for p in answer["proposals"][1:]] == ["Feria", "Clima"]
    assert [p["carried"] for p in answer["proposals"]] == [False, True, True]


def test_something_carried_that_is_proposed_anyway_appears_once(client):
    municipality, ana = cabinet_member(client, others=EVERY)
    make_light(municipality, "environment", 2026, 2, "red")
    [overdue, finished] = held(client, ana, date(2026, 2, 20), date(2026, 2, 20))
    meeting = prepare(
        client,
        date(2026, 3, 1),
        [
            {"key": "light:environment:2026-02"},
            {"key": f"commitment:{overdue['id']}"},
            {"key": f"commitment:{finished['id']}"},
        ],
    )
    close(client, meeting)
    set_state(client, finished)

    # The one delivered since is not worth carrying.
    assert keys(proposal(client)) == [
        "light:environment:2026-02",
        f"commitment:{overdue['id']}",
    ]


def test_an_undiscussed_commitment_given_more_time_is_still_carried(client):
    _, ana = cabinet_member(client)
    [late] = held(client, ana, date(2026, 2, 20))
    meeting = prepare(client, date(2026, 3, 1), [{"key": f"commitment:{late['id']}"}])
    item = meeting["items"][0]
    close(client, meeting)
    client.patch(f"{URL}/commitments/{late['id']}", json={"due_date": "2026-05-01"})

    [carried] = proposal(client)["proposals"]

    assert carried["key"] == f"item:{item['id']}"
    assert carried["title"] == "Compromiso 1"
    assert carried["commitment"]["id"] == late["id"]
    accepted = prepare(client, agenda=[{"key": carried["key"]}])["items"][0]
    assert (accepted["source"], accepted["carried"]) == ("commitment", True)
    assert accepted["topic"]["id"] == late["id"]


def test_a_light_undiscussed_and_no_longer_the_latest_is_carried(client):
    municipality, _ = cabinet_member(client, others=EVERY)
    make_light(municipality, "environment", 2026, 1, "red")
    pin_today(client, date(2026, 2, 5))
    meeting = prepare(client, date(2026, 2, 5), [{"key": "light:environment:2026-01"}])
    close(client, meeting)
    make_light(municipality, "environment", 2026, 2, "green")
    pin_today(client, TODAY)

    [carried] = proposal(client)["proposals"]

    assert carried["key"] == f"item:{meeting['items'][0]['id']}"
    assert carried["title"] == "Ambiental, enero de 2026"


def test_the_accepted_agenda_keeps_the_order_and_what_was_added(client):
    municipality, ana = cabinet_member(client, others=EVERY)
    make_light(municipality, "environment", 2026, 2, "red")
    make_light(municipality, "projects", 2026, 2, "yellow")
    [overdue] = held(client, ana, date(2026, 3, 1))

    meeting = prepare(
        client,
        agenda=[
            "Feria del libro",
            {"key": f"commitment:{overdue['id']}"},
            {"key": "light:environment:2026-02"},
        ],
    )

    assert [(i["source"], i["title"], i["discussed"]) for i in meeting["items"]] == [
        ("manual", "Feria del libro", False),
        ("commitment", "Compromiso 1", False),
        ("light", "Ambiental, febrero de 2026", False),
    ]
    assert meeting["items"][1]["topic"]["id"] == overdue["id"]
    assert meeting["items"][2]["subject"]["color"] == "red"
    assert all(i["carried"] is False for i in meeting["items"])


def test_only_what_is_proposed_can_be_accepted_and_once(client):
    municipality, _ = cabinet_member(client, others={"projects": "viewer"})
    make_light(municipality, "environment", 2026, 2, "red")

    def create(*keys):
        return client.post(
            f"{URL}/meetings",
            json={"date": "2026-03-10", "agenda": [{"key": key} for key in keys]},
        )

    # A light of a dashboard the member cannot open is not theirs to accept either.
    for key in ("light:environment:2026-02", "light:projects:2026-02", "nonsense"):
        assert error(create(key)) == (409, "agenda_changed")
    make_light(municipality, "projects", 2026, 2, "red")
    twice = create("light:projects:2026-02", "light:projects:2026-02")
    assert twice.status_code == 422
    assert twice.json()["error"] == {
        "code": "validation_error",
        "message": "A proposal cannot be accepted twice.",
    }
    assert client.get(f"{URL}/meetings").json()["total"] == 0


@pytest.mark.parametrize("entry", [{}, {"key": "x", "title": "y"}, {"title": " "}])
def test_an_agenda_entry_is_a_proposal_or_a_title(client, entry):
    cabinet_member(client)

    response = client.post(f"{URL}/meetings", json={"date": "2026-03-10", "agenda": [entry]})

    assert error(response) == (422, "validation_error")


def test_looking_at_the_proposal_changes_nothing_and_needs_an_editor(client):
    municipality, ana = cabinet_member(client)
    [taken] = held(client, ana, date(2026, 3, 1))
    for _ in range(3):
        proposal(client)

    assert client.get(f"/api/commitments/{taken['id']}").json()["times_postponed"] == 0
    cabinet_member(client, "viewer", "leo@noetinger.test", municipality)
    assert client.get(f"{URL}/agenda-proposal?date=2026-03-10").status_code == 403


def test_a_carried_light_stays_hidden_from_whoever_prepares_without_access(client):
    municipality, ana = cabinet_member(client, others={"environment": "viewer"})
    make_light(municipality, "environment", 2026, 2, "red")
    meeting = prepare(client, date(2026, 3, 1), [{"key": "light:environment:2026-02"}])
    close(client, meeting)
    cabinet_member(client, "editor", "leo@noetinger.test", municipality)

    [carried] = proposal(client)["proposals"]

    assert carried["title"] == "Estado mensual de un tablero al que no tenés acceso"
    assert carried["subject"] == {
        "access": "restricted",
        "kind": "month",
        "dashboard_key": None,
        "ref": None,
        "label": None,
        "path": None,
        "color": None,
    }
    # It can be accepted all the same, and whoever has access sees what it is.
    accepted = prepare(client, agenda=[{"key": carried["key"]}])
    assert accepted["items"][0]["title"] == "Estado mensual de un tablero al que no tenés acceso"
    as_member(client)
    seen = client.get(f"{URL}/meetings/{accepted['id']}").json()
    assert seen["items"][0]["title"] == "Ambiental, febrero de 2026"


def test_a_manual_item_carried_keeps_what_it_was_linked_to(client):
    municipality, _ = cabinet_member(client, others={"projects": "viewer"})
    project = make_simple_project(municipality)
    meeting = prepare(client, date(2026, 3, 1), [])
    client.post(
        f"{URL}/meetings/{meeting['id']}/items",
        json={"title": "Obra", "subject": project_subject(project)},
    )
    close(client, meeting)

    [carried] = proposal(client)["proposals"]
    accepted = prepare(client, agenda=[{"key": carried["key"]}])["items"][0]

    assert accepted["title"] == "Obra"
    assert accepted["subject"]["label"] == "Pavimentación"


def test_a_commitment_from_a_light_can_be_linked_to_that_month(client):
    municipality, ana = cabinet_member(client, others=EVERY)
    make_light(municipality, "environment", 2026, 2, "red")
    meeting = prepare(client, agenda=[{"key": "light:environment:2026-02"}])

    taken = commit(
        client, meeting["items"][0], ana, subject=month_subject("environment", "2026-02")
    )

    assert taken["subject"]["label"] == "Ambiental, febrero de 2026"
