"""What somebody owed when they stopped being a member: who is told and who takes it."""

import pytest
from sqlalchemy import select

from gobernar360.platform.commitment_models import CommitmentNotice
from tests.cabinet.factories import URL as CABINET
from tests.cabinet.factories import commit, prepare
from tests.factories import admin_session, login, make_membership, make_municipality, make_user
from tests.platform.test_commitments import (  # noqa: F401
    as_,
    give,
    patch,
    people,
    pinned_today,
    set_state,
)

LEFT = "/api/admin/left-commitments"
NOTHING = {"commitments": [], "hidden": 0}


def _membership(client, email: str) -> str:
    page = client.get("/api/admin/users", params={"q": email}).json()
    [member] = page["items"]
    return member["membership_id"]


def _remove(client, name: str) -> dict:
    as_(client, "admin")
    response = client.delete(f"/api/admin/users/{_membership(client, f'{name}@noetinger.test')}")
    assert response.status_code == 200, response.text
    return response.json()


def _take(client, people, name="leo", *descriptions) -> list[dict]:  # noqa: F811
    """Commitments a meeting gave to somebody."""
    as_(client, "admin")
    item = prepare(client)["items"][0]
    return [
        commit(client, item, people[name], description=description)
        for description in descriptions or ("Presentar el balance",)
    ]


def _news(client, name: str) -> list[tuple[str, str, list[str]]]:
    as_(client, name)
    rows = client.get("/api/notifications").json()
    return [
        (section, row["description"], [news["kind"] for news in row["news"]])
        for section in ("mine", "others")
        for row in rows[section]
        if row["news"]
    ]


def test_removing_a_member_reports_every_open_commitment_they_had(client, people):  # noqa: F811
    first, second = _take(client, people, "leo", "Balance", "Certificar la obra")
    done, dropped = _take_more(client, people, first)

    left = _remove(client, "leo")

    assert left == {
        "commitments": [
            {
                "id": commitment["id"],
                "description": commitment["description"],
                "owner": {"id": str(people["leo"].id), "full_name": "Leo"},
                "due_date": "2026-03-20",
                "source": "cabinet",
                "can_reassign": True,
            }
            for commitment in (first, second)
        ],
        "hidden": 0,
    }
    # And so it can be found later.
    assert client.get(LEFT).json() == left
    assert {done["id"], dropped["id"]}.isdisjoint(c["id"] for c in left["commitments"])


def _take_more(client, people, first):  # noqa: F811
    """Finished ones, of the meeting of another."""
    done, dropped = (
        commit(client, {"id": first["item_id"]}, people["leo"], description=description)
        for description in ("Hecho", "Descartado")
    )
    set_state(client, done, "done")
    set_state(client, dropped, "dropped")
    return done, dropped


def test_until_somebody_takes_it_it_says_that_its_owner_left(client, people):  # noqa: F811
    [commitment] = _take(client, people)
    other = commit(client, {"id": commitment["item_id"]}, people["zoe"], description="Otro")
    _remove(client, "leo")

    shown = {c["id"]: c["owner_left"] for c in client.get(f"{CABINET}/commitments").json()["items"]}
    assert shown == {commitment["id"]: True, other["id"]: False}
    detail = client.get(f"/api/commitments/{commitment['id']}").json()
    assert (detail["owner_left"], detail["owner"]["full_name"]) == (True, "Leo")
    assert detail["state"] == "open"


def test_giving_it_to_another_one_changes_the_owner_and_tells_them(client, people):  # noqa: F811
    [commitment] = _take(client, people)
    _remove(client, "leo")

    moved = patch(client, commitment, owner_id=str(people["zoe"].id))

    assert (moved.status_code, moved.json()["owner"]["full_name"]) == (200, "Zoe")
    assert moved.json()["owner_left"] is False
    assert client.get(LEFT).json() == NOTHING
    assert _news(client, "zoe") == [("mine", "Presentar el balance", ["assigned"])]


def test_nobody_who_left_can_be_given_it(client, people):  # noqa: F811
    [commitment] = _take(client, people)
    _remove(client, "zoe")

    refused = patch(client, commitment, owner_id=str(people["zoe"].id))

    assert (refused.status_code, refused.json()["error"]["code"]) == (422, "invalid_reference")


def test_an_informal_one_is_counted_and_told_to_whoever_gave_it_and_to_nobody_else(
    client,
    people,  # noqa: F811
):
    """Not even an administrator learns what it was about."""
    as_(client, "ana")
    given = give(client, people["leo"], description="Asunto reservado")

    left = _remove(client, "leo")

    assert left == {"commitments": [], "hidden": 1} == client.get(LEFT).json()
    assert client.get(f"/api/commitments/{given['id']}").status_code == 404
    assert _news(client, "ana") == [("others", "Asunto reservado", ["owner_left"])]
    [shown] = client.get("/api/commitments", params={"relation": "given"}).json()["items"]
    assert shown["owner_left"] is True
    for name in ("zoe", "max"):
        assert _news(client, name) == []
    # Whoever gave it gives it to another one, and there is nothing left to tell.
    as_(client, "ana")
    assert patch(client, given, owner_id=str(people["zoe"].id)).status_code == 200
    assert _news(client, "ana") == []
    as_(client, "admin")
    assert client.get(LEFT).json() == NOTHING


def test_those_one_gave_oneself_are_nobodys_to_be_told_about(client, people):  # noqa: F811
    as_(client, "leo")
    give(client, people["leo"])

    assert _remove(client, "leo") == {"commitments": [], "hidden": 1}
    with admin_session() as session:
        kinds = session.scalars(select(CommitmentNotice.kind)).all()
    assert kinds == []


def test_whoever_gave_it_and_left_before_is_not_told(client, people):  # noqa: F811
    as_(client, "zoe")
    give(client, people["leo"])
    _remove(client, "zoe")
    _remove(client, "leo")

    with admin_session() as session:
        kinds = session.scalars(select(CommitmentNotice.kind)).all()
    assert kinds == ["assigned"]


def test_an_administrator_sees_the_informal_ones_they_gave(client, people):  # noqa: F811
    as_(client, "admin")
    given = give(client, people["leo"], description="Lo mío")
    as_(client, "ana")
    give(client, people["leo"], follower_ids=[str(people["admin"].id)], description="Lo sigo")

    left = _remove(client, "leo")

    # Being attached is for reading: only who gave it may give it to another one.
    assert [(c["description"], c["source"], c["can_reassign"]) for c in left["commitments"]] == [
        ("Lo mío", None, True),
        ("Lo sigo", None, False),
    ]
    assert left["commitments"][0]["id"] == given["id"]
    # Whoever does it is not told what they did.
    assert _news(client, "admin") == []
    assert _news(client, "ana") == [("others", "Lo sigo", ["owner_left"])]


@pytest.mark.parametrize("state", ["done", "dropped"])
def test_finishing_it_takes_back_what_was_told(client, people, state):  # noqa: F811
    as_(client, "ana")
    given = give(client, people["leo"])
    _remove(client, "leo")
    as_(client, "ana")

    if state == "dropped":
        assert set_state(client, given, "dropped").status_code == 200
        assert _news(client, "ana") == []
    else:
        # The one who gave it may not say it is done; the reason to be told is still there.
        assert set_state(client, given, "done").status_code == 403
        assert len(_news(client, "ana")) == 1


def test_somebody_who_comes_back_owes_it_again(client, people):  # noqa: F811
    as_(client, "ana")
    give(client, people["leo"])
    [taken] = _take(client, people)
    _remove(client, "leo")
    back = {
        "email": "leo@noetinger.test",
        "full_name": "Leo",
        "is_admin": False,
        "grants": {},
    }
    assert client.post("/api/admin/users", json=back).status_code == 201

    assert client.get(LEFT).json() == NOTHING
    assert client.get(f"/api/commitments/{taken['id']}").json()["owner_left"] is False
    assert _news(client, "ana") == []


def test_what_was_read_is_not_taken_back_from_anybody_else(client, people):  # noqa: F811
    """Leo coming back says nothing of Max, who also left."""
    as_(client, "ana")
    give(client, people["leo"], description="De Leo")
    give(client, people["max"], description="De Max")
    _remove(client, "leo")
    _remove(client, "max")
    back = {"email": "leo@noetinger.test", "full_name": "Leo", "is_admin": False, "grants": {}}
    client.post("/api/admin/users", json=back)

    assert _news(client, "ana") == [("others", "De Max", ["owner_left"])]


def test_an_administrator_who_removes_themselves_is_answered_too(client, people):  # noqa: F811
    as_(client, "admin")
    make_membership(make_user("otra@noetinger.test"), people["municipality"], admin=True, enable=[])
    [commitment] = _take(client, people, "admin")

    left = _remove(client, "admin")

    assert [c["id"] for c in left["commitments"]] == [commitment["id"]]
    assert client.get(LEFT).status_code == 403


def test_the_operator_learns_how_many_and_nothing_else(client, people):  # noqa: F811
    _take(client, people, "leo", "Balance", "Obra")
    membership = _membership(client, "leo@noetinger.test")
    make_user("operador@example.test", operator=True)
    client.cookies.clear()
    login(client, "operador@example.test")
    url = f"/api/platform/municipalities/{people['municipality'].id}/users/{membership}"

    assert client.delete(url).json() == {"commitments": [], "hidden": 2}
    assert client.get(LEFT).status_code == 403


def test_what_the_dashboard_that_recorded_it_hides_is_hidden(client, people):  # noqa: F811
    """Of a dashboard the operator disabled since, there is only how many."""
    from gobernar360.platform.models import MunicipalityDashboard

    _take(client, people)
    with admin_session() as session, session.begin():
        for row in session.scalars(select(MunicipalityDashboard)):
            if row.dashboard_key == "cabinet":
                session.delete(row)

    assert _remove(client, "leo") == {"commitments": [], "hidden": 1}


def test_members_of_other_municipalities_left_nothing_here(client, people):  # noqa: F811
    """Leo is still a member of Saira, and left Noetinger."""
    _take(client, people)
    saira = make_municipality("Saira")
    make_membership(people["leo"], saira)
    make_membership(make_user("admin@saira.test"), saira, admin=True, enable=[])

    assert len(_remove(client, "leo")["commitments"]) == 1
    client.cookies.clear()
    login(client, "admin@saira.test")
    assert client.get(LEFT).json() == NOTHING


def test_only_administrators_list_them(client, people):  # noqa: F811
    assert client.get(LEFT).status_code == 401
    as_(client, "ana")

    assert client.get(LEFT).status_code == 403


def test_they_come_by_date_and_then_by_text(client, people):  # noqa: F811
    from datetime import date

    as_(client, "admin")
    item = prepare(client)["items"][0]
    for description, day in (("B", 21), ("C", 20), ("A", 21)):
        commit(client, item, people["leo"], date(2026, 3, day), description=description)

    left = _remove(client, "leo")

    assert [c["description"] for c in left["commitments"]] == ["C", "A", "B"]


def test_only_what_is_open_and_informal_is_told_about(client, people):  # noqa: F811
    """What was done needs nobody, and what a meeting gave is on the administrator's list."""
    make_membership(
        make_user("gabi@noetinger.test"),
        people["municipality"],
        grants={"cabinet": "editor"},
        enable=[],
    )
    as_(client, "gabi")
    commit(client, prepare(client)["items"][0], people["leo"], description="De una reunión")
    as_(client, "ana")
    done = give(client, people["leo"], description="Hecho")
    as_(client, "leo")
    set_state(client, done, "done")

    _remove(client, "leo")

    with admin_session() as session:
        told = session.scalars(
            select(CommitmentNotice).where(CommitmentNotice.kind == "owner_left")
        ).all()
    assert told == []


def test_reopening_what_was_dropped_does_not_tell_it_again(client, people):  # noqa: F811
    as_(client, "ana")
    given = give(client, people["leo"])
    _remove(client, "leo")
    as_(client, "ana")
    set_state(client, given, "dropped")

    assert set_state(client, given, "open").status_code == 200

    assert _news(client, "ana") == []


def test_coming_back_takes_back_nothing_else(client, people):  # noqa: F811
    """Not that Leo had delivered something, nor what was already read."""
    as_(client, "ana")
    delivered = give(client, people["leo"], description="Entregado")
    pending = give(client, people["leo"], description="Pendiente")
    as_(client, "leo")
    set_state(client, delivered, "done")
    _remove(client, "leo")
    as_(client, "ana")
    client.post("/api/notifications/read", json={"commitment_id": pending["id"]})
    as_(client, "admin")
    back = {"email": "leo@noetinger.test", "full_name": "Leo", "is_admin": False, "grants": {}}
    client.post("/api/admin/users", json=back)

    assert _news(client, "ana") == [("others", "Entregado", ["done"])]
    with admin_session() as session:
        kept = session.scalars(
            select(CommitmentNotice.kind).where(CommitmentNotice.read_at.is_not(None))
        ).all()
    assert kept == ["owner_left"]
