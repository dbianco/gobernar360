from datetime import date

import pytest

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.cabinet import summary as cabinet_summary
from gobernar360.platform.access import system_context
from tests.cabinet.factories import (
    TODAY,
    URL,
    as_member,
    cabinet_member,
    close,
    commit,
    held,
    pin_today,
    prepare,
)
from tests.factories import current_overview, make_membership, make_user


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def set_state(client, commitment, state, **fields):
    response = client.post(
        f"/api/commitments/{commitment['id']}/state", json={"state": state} | fields
    )
    assert response.status_code == 200, response.text


def scenario(client):
    """Ana: one on time, one late, one dropped. Leo: one overdue, one still in time."""
    municipality, ana = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    meeting = prepare(client, date(2026, 2, 1))
    item = meeting["items"][0]
    on_time = commit(client, item, ana, date(2026, 2, 20), description="A tiempo")
    late = commit(client, item, ana, date(2026, 2, 20), description="Tarde")
    dropped = commit(client, item, ana, date(2026, 2, 20), description="Descartado")
    overdue = commit(client, item, leo, date(2026, 3, 9), description="Vencido")
    pending = commit(client, item, leo, date(2026, 3, 10), description="Pendiente")
    close(client, meeting)
    set_state(client, on_time, "done", completed_on="2026-02-20")
    set_state(client, late, "done", completed_on="2026-02-21")
    set_state(client, dropped, "dropped")
    return municipality, ana, leo, overdue, pending


def test_it_counts_by_state_and_owner_and_the_share_on_time(client):
    _, ana, leo, _, _ = scenario(client)

    summary = client.get(f"{URL}/summary").json()

    assert summary == {
        "total": 5,
        "by_state": {"overdue": 1, "open": 1, "done": 2, "dropped": 1},
        "on_time_share": 0.3333,
        "by_owner": [
            {
                "owner": {"id": str(leo.id), "full_name": "Leo"},
                "by_state": {"overdue": 1, "open": 1, "done": 0, "dropped": 0},
                "on_time_share": 0.0,
            },
            {
                "owner": {"id": str(ana.id), "full_name": "Ana"},
                "by_state": {"overdue": 0, "open": 0, "done": 2, "dropped": 1},
                "on_time_share": 0.5,
            },
        ],
        "most_postponed": [],
        "closed_meetings": 1,
        "last_meeting": "2026-02-01",
    }


def _indicators(municipality) -> dict:
    with tenant_session(municipality.id) as db:
        ctx = system_context(db, municipality.id)
        return {i.key: i.value for i in cabinet_summary.get_summary(ctx, TODAY)}


def _move(client, commitment, due_date: str, url: str = "/api") -> dict:
    response = client.patch(f"{url}/commitments/{commitment['id']}", json={"due_date": due_date})
    assert response.status_code == 200, response.text
    return response.json()


def test_moving_the_date_does_not_change_the_figures_and_its_history_tells_it(client):
    municipality, _ = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    late, *_ = held(client, leo, date(2026, 2, 20), date(2026, 4, 1))
    before = client.get(f"{URL}/summary").json(), _indicators(municipality)
    assert before[1] == {
        "cabinet.pending": 2,
        "cabinet.overdue": 1,
        "cabinet.done": 0,
        "cabinet.on_time_ratio": 0.0,
    }

    as_member(client, "leo@noetinger.test")
    moved = _move(client, late, "2026-03-15")
    as_member(client)

    # What it is due by now, apart from what was agreed.
    assert (moved["due_date"], moved["agreed_due_date"], moved["state"]) == (
        "2026-03-15",
        "2026-02-20",
        "open",
    )
    assert (client.get(f"{URL}/summary").json(), _indicators(municipality)) == before
    history = client.get(f"/api/commitments/{late['id']}").json()["history"]
    assert history[-1]["changes"] == {"due_date": ["2026-02-20", "2026-03-15"]}
    assert history[-1]["author"] == "Leo"

    # Delivered by the new date and not by the one agreed.
    set_state(client, late, "done", completed_on="2026-03-10")
    after = client.get(f"{URL}/summary").json()
    assert (after["on_time_share"], after["by_owner"][0]["on_time_share"]) == (0.0, 0.0)
    assert after["by_state"] == {"overdue": 0, "open": 1, "done": 1, "dropped": 0}
    assert _indicators(municipality)["cabinet.on_time_ratio"] == 0.0


def test_neither_does_moving_it_closer(client):
    municipality, ana = cabinet_member(client)
    [commitment] = held(client, ana, date(2026, 3, 20))

    moved = _move(client, commitment, "2026-03-01", URL)

    assert (moved["state"], moved["agreed_due_date"]) == ("overdue", "2026-03-20")
    assert _indicators(municipality)["cabinet.overdue"] == 0
    summary = client.get(f"{URL}/summary").json()
    assert summary["by_state"] == {"overdue": 0, "open": 1, "done": 0, "dropped": 0}
    # The list shows how it stands with the date it has.
    [listed] = client.get(f"{URL}/commitments").json()["items"]
    assert (listed["state"], listed["due_date"]) == ("overdue", "2026-03-01")


def test_the_day_agreed_is_on_time_and_the_next_one_is_not(client):
    municipality, ana = cabinet_member(client)
    exact, late = held(client, ana, date(2026, 2, 20), date(2026, 2, 20))
    for commitment in (exact, late):
        _move(client, commitment, "2026-03-30", URL)
    set_state(client, exact, "done", completed_on="2026-02-20")
    set_state(client, late, "done", completed_on="2026-02-21")

    assert client.get(f"{URL}/summary").json()["on_time_share"] == 0.5
    assert _indicators(municipality)["cabinet.on_time_ratio"] == 0.5


def test_a_date_corrected_while_the_meeting_is_open_is_the_one_agreed(client):
    municipality, ana = cabinet_member(client)
    meeting = prepare(client, date(2026, 2, 1))
    commitment = commit(client, meeting["items"][0], ana, date(2026, 2, 20))

    during = _move(client, commitment, "2026-02-25", URL)
    close(client, meeting)
    after = _move(client, commitment, "2026-03-30", URL)

    assert (during["due_date"], during["agreed_due_date"]) == ("2026-02-25", "2026-02-25")
    assert (after["due_date"], after["agreed_due_date"]) == ("2026-03-30", "2026-02-25")


def test_its_owner_agrees_on_nothing_even_while_the_meeting_is_open(client):
    municipality, _ = cabinet_member(client)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    commitment = commit(client, prepare(client)["items"][0], leo, date(2026, 3, 20))
    as_member(client, "leo@noetinger.test")

    assert _move(client, commitment, "2026-04-01")["agreed_due_date"] == "2026-03-20"


def test_owners_are_ordered_by_what_they_owe_then_by_name(client):
    municipality, ana = cabinet_member(client)
    users = [make_user(f"{name}@noetinger.test") for name in ("zoe", "beto", "caro")]
    for user in users:
        make_membership(user, municipality)
    zoe, beto, caro = users
    item = prepare(client)["items"][0]
    commit(client, item, zoe, date(2026, 3, 1))
    commit(client, item, ana, date(2026, 4, 1))
    commit(client, item, caro, date(2026, 4, 1))
    commit(client, item, caro, date(2026, 4, 1))
    commit(client, item, beto, date(2026, 4, 1))

    rows = client.get(f"{URL}/summary").json()["by_owner"]

    assert [row["owner"]["full_name"] for row in rows] == ["Zoe", "Caro", "Ana", "Beto"]


def test_the_most_postponed_are_those_still_open_most_times_first(client):
    _, ana = cabinet_member(client)
    old, done = held(client, ana, date(2026, 5, 1), date(2026, 5, 1), on=date(2026, 1, 1))
    newer = held(client, ana, date(2026, 4, 1), date(2026, 3, 1), on=date(2026, 2, 1))
    set_state(client, done, "done")
    meeting = prepare(client)
    commit(client, meeting["items"][0], ana)

    rows = client.get(f"{URL}/summary").json()["most_postponed"]

    assert [(c["id"], c["times_postponed"]) for c in rows] == [
        (old["id"], 2),
        (newer[1]["id"], 1),
        (newer[0]["id"], 1),
    ]


def test_only_ten_of_the_most_postponed_are_shown(client):
    _, ana = cabinet_member(client)
    held(client, ana, *[date(2026, 4, 1)] * 11)
    prepare(client)

    assert len(client.get(f"{URL}/summary").json()["most_postponed"]) == 10


def test_an_empty_summary(client):
    cabinet_member(client, "viewer")

    assert client.get(f"{URL}/summary").json() == {
        "total": 0,
        "by_state": {"overdue": 0, "open": 0, "done": 0, "dropped": 0},
        "on_time_share": None,
        "by_owner": [],
        "most_postponed": [],
        "closed_meetings": 0,
        "last_meeting": None,
    }


def test_the_overview_shows_the_headline_indicators(client):
    scenario(client)

    [section] = current_overview(client.get("/api/overview").json())

    assert section == {
        "dashboard_key": "cabinet",
        "indicators": [
            {"key": "cabinet.pending", "value": 2, "unit": None},
            {"key": "cabinet.overdue", "value": 1, "unit": None},
            {"key": "cabinet.done", "value": 2, "unit": None},
            {"key": "cabinet.on_time_ratio", "value": 0.3333, "unit": "ratio"},
        ],
        "status": [],
    }


def test_the_overview_has_no_indicators_without_commitments(client):
    cabinet_member(client)
    prepare(client)

    assert client.get("/api/overview").json()[0]["indicators"] == []


def test_the_last_meeting_is_the_latest_closed(client):
    cabinet_member(client)
    for day in (3, 10, 17):
        close(client, prepare(client, date(2026, 2, day)))
    prepare(client, date(2026, 2, 24))

    summary = client.get(f"{URL}/summary").json()

    assert (summary["closed_meetings"], summary["last_meeting"]) == (3, "2026-02-17")


def test_the_indicators_are_computed_without_a_member_for_the_monthly_snapshot(client):
    municipality, *_ = scenario(client)

    with tenant_session(municipality.id) as db:
        indicators = cabinet_summary.get_summary(system_context(db, municipality.id), TODAY)

    assert [(i.key, i.value, i.unit) for i in indicators] == [
        ("cabinet.pending", 2, None),
        ("cabinet.overdue", 1, None),
        ("cabinet.done", 2, None),
        ("cabinet.on_time_ratio", 0.3333, "ratio"),
    ]
