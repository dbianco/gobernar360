"""What people are told, inside the app, about the commitments they have to do with."""

import threading
from datetime import date

import pytest
from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform import commitments
from gobernar360.platform.access import RequestContext
from gobernar360.platform.commitment_models import CommitmentNotice
from gobernar360.platform.models import EmailOutbox, Membership, User
from tests.cabinet.factories import cabinet_member, commit, pin_today, prepare
from tests.factories import admin_session, make_membership, make_user
from tests.platform.test_commitments import as_, give, patch, people, set_state

__all__ = ["people"]


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


def news(client, name: str) -> dict[str, list]:
    """What a member sees in their notifications: (what, state, [(kind, who did it)])."""
    as_(client, name)
    response = client.get("/api/notifications")
    assert response.status_code == 200, response.text
    return {
        section: [
            (row["description"], row["state"], [(n["kind"], n["actor"]) for n in row["news"]])
            for row in rows
        ]
        for section, rows in response.json().items()
    }


def read(client, commitment=None):
    body = {"commitment_id": commitment["id"]} if commitment else {}
    assert client.post("/api/notifications/read", json=body).status_code == 204


def stored() -> list[tuple[str, str]]:
    """Every unread notice there is, shown to somebody or not: (who, what)."""
    with admin_session() as session:
        rows = session.execute(
            select(User.email, CommitmentNotice.kind)
            .join(User, User.id == CommitmentNotice.user_id)
            .where(CommitmentNotice.read_at.is_(None))
        )
        return sorted((email.split("@")[0], kind) for email, kind in rows)


def test_whoever_is_given_one_is_told_and_the_others_see_it_in_their_list(client, people):
    as_(client, "ana")
    give(client, people["leo"], follower_ids=[str(people["zoe"].id)])

    assert news(client, "leo") == {
        "mine": [("Enviar nota", "open", [("assigned", "Ana")])],
        "others": [],
    }
    for name in ("ana", "zoe"):
        assert news(client, name) == {"mine": [], "others": [("Enviar nota", "open", [])]}
    assert news(client, "max") == {"mine": [], "others": []}
    # Informal ones concern those involved, not the administrator.
    assert news(client, "admin") == {"mine": [], "others": []}


def test_a_row_has_what_the_page_shows(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], date(2026, 3, 9))
    as_(client, "leo")

    [row] = client.get("/api/notifications").json()["mine"]

    assert row | {"news": None} == {
        "id": given["id"],
        "description": "Enviar nota",
        "owner": {"id": str(people["leo"].id), "full_name": "Leo"},
        "due_date": "2026-03-09",
        "state": "overdue",
        "completed_on": None,
        "news": None,
    }
    assert set(row["news"][0]) == {"kind", "actor", "at"}


def test_when_it_is_done_its_creator_and_those_attached_are_told(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    as_(client, "leo")
    set_state(client, given, "done")

    assert news(client, "leo") == {"mine": [], "others": []}
    for name in ("ana", "zoe"):
        assert news(client, name)["others"] == [("Enviar nota", "done", [("done", "Leo")])]


def test_one_delivered_leaves_the_list_when_it_is_read(client, people):
    as_(client, "ana")
    first = give(client, people["leo"], description="Primero")
    second = give(client, people["leo"], description="Segundo")
    as_(client, "leo")
    for commitment in (first, second):
        set_state(client, commitment, "done")
    assert len(news(client, "ana")["others"]) == 2

    read(client, first)
    assert news(client, "ana")["others"] == [("Segundo", "done", [("done", "Leo")])]
    read(client)
    assert news(client, "ana")["others"] == []


def test_one_read_leaves_the_list_though_others_have_not_read_about_it(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    as_(client, "leo")
    set_state(client, given, "done")
    as_(client, "ana")
    read(client)

    assert news(client, "ana") == {"mine": [], "others": []}
    assert len(news(client, "zoe")["others"]) == 1


def test_reopening_takes_back_only_what_was_said_of_that_one(client, people):
    as_(client, "ana")
    first = give(client, people["leo"], description="Primero")
    second = give(client, people["leo"], description="Segundo")
    as_(client, "leo")
    for commitment in (first, second):
        set_state(client, commitment, "done")
    as_(client, "ana")
    set_state(client, first, "open")

    assert stored() == [("ana", "done")]
    assert [row[0] for row in news(client, "ana")["others"] if row[2]] == ["Segundo"]


def test_reading_that_one_was_given_leaves_it_in_the_list(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    as_(client, "leo")
    read(client, given)

    assert news(client, "leo")["mine"] == [("Enviar nota", "open", [])]


def test_nobody_is_told_about_what_they_did_themselves(client, people):
    as_(client, "ana")
    given = give(client, people["ana"], follower_ids=[str(people["ana"].id)])
    assert news(client, "ana")["mine"] == [("Enviar nota", "open", [])]
    set_state(client, given, "done")

    assert news(client, "ana") == {"mine": [], "others": []}


def test_someone_attached_who_also_gave_it_is_told_once(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["ana"].id)])
    as_(client, "leo")
    set_state(client, given, "done")

    assert news(client, "ana")["others"] == [("Enviar nota", "done", [("done", "Leo")])]


def test_giving_it_to_another_tells_them_and_takes_back_what_was_not_read(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    patch(client, given, owner_id=str(people["zoe"].id))

    assert stored() == [("zoe", "assigned")]
    assert news(client, "leo") == {"mine": [], "others": []}
    assert news(client, "zoe")["mine"] == [("Enviar nota", "open", [("assigned", "Ana")])]
    as_(client, "zoe")
    patch(client, given, owner_id=str(people["leo"].id))
    assert news(client, "leo")["mine"] == [("Enviar nota", "open", [("assigned", "Zoe")])]


def test_taking_it_oneself_tells_nobody(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    patch(client, given, owner_id=str(people["ana"].id))

    assert news(client, "ana")["mine"] == [("Enviar nota", "open", [])]


def test_reopening_takes_back_that_it_was_done(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    as_(client, "leo")
    set_state(client, given, "done")
    as_(client, "ana")
    set_state(client, given, "open")

    assert news(client, "zoe")["others"] == [("Enviar nota", "open", [])]
    as_(client, "leo")
    set_state(client, given, "done")
    assert news(client, "zoe")["others"] == [("Enviar nota", "done", [("done", "Leo")])]


def test_one_dropped_leaves_every_list_and_nobody_is_left_with_news_of_it(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    set_state(client, given, "dropped")

    assert stored() == []
    for name in ("ana", "leo", "zoe"):
        assert news(client, name) == {"mine": [], "others": []}
    as_(client, "ana")
    set_state(client, given, "open")
    assert news(client, "leo")["mine"] == [("Enviar nota", "open", [])]


def test_correcting_the_day_it_was_done_is_not_news(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    as_(client, "leo")
    set_state(client, given, "done")
    news(client, "ana")
    read(client)
    as_(client, "leo")
    set_state(client, given, "done", completed_on="2026-03-01", note="Fue antes.")

    assert news(client, "ana") == {"mine": [], "others": []}


def test_someone_no_longer_attached_stops_seeing_it_and_its_news(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    as_(client, "leo")
    patch(client, given, follower_ids=[])
    set_state(client, given, "done")

    assert news(client, "zoe") == {"mine": [], "others": []}


def test_what_has_news_comes_first_and_the_rest_by_due_date(client, people):
    as_(client, "ana")
    give(client, people["leo"], date(2026, 3, 1), description="Vencido")
    give(client, people["leo"], date(2026, 5, 1), description="Lejano")
    give(client, people["leo"], date(2026, 4, 1), description="Cercano")
    done = give(client, people["leo"], date(2026, 6, 1), description="Hecho")
    as_(client, "leo")
    set_state(client, done, "done")

    assert [row[0] for row in news(client, "ana")["others"]] == [
        "Hecho",
        "Vencido",
        "Cercano",
        "Lejano",
    ]


def test_those_of_a_meeting_reach_people_without_the_cabinet(client):
    municipality, gabi = cabinet_member(client, email="gabi@noetinger.test")
    leo, zoe = make_user("leo@noetinger.test"), make_user("zoe@noetinger.test")
    for user in (leo, zoe):
        make_membership(user, municipality)
    taken = commit(client, prepare(client)["items"][0], leo, follower_ids=[str(zoe.id)])

    assert news(client, "leo")["mine"] == [("Certificar la obra", "open", [("assigned", "Gabi")])]
    assert news(client, "zoe")["others"] == [("Certificar la obra", "open", [])]
    as_(client, "leo")
    set_state(client, taken, "done")
    assert news(client, "zoe")["others"] == [("Certificar la obra", "done", [("done", "Leo")])]
    assert stored() == [("zoe", "done")]
    # Whoever wrote the meeting down follows it in the cabinet, not here.
    assert news(client, "gabi") == {"mine": [], "others": []}


def test_nothing_is_sent_by_email(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    as_(client, "leo")
    set_state(client, given, "done")

    with admin_session() as session:
        assert session.scalars(select(EmailOutbox)).all() == []


def test_finishing_it_twice_at_once_tells_everyone_once(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    start = threading.Barrier(4)

    def finish():
        with tenant_session(people["municipality"].id) as db:
            membership = db.scalar(select(Membership).where(Membership.user_id == people["leo"].id))
            ctx = RequestContext(people["leo"], people["municipality"].id, membership, db)
            commitments.load(ctx, given["id"])
            start.wait()
            commitment = commitments.load(ctx, given["id"], lock=True)
            commitments.set_state(ctx, commitment, date(2026, 3, 10), "done")

    threads = [threading.Thread(target=finish) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    with admin_session() as session:
        told = [
            notice.user_id
            for notice in session.scalars(select(CommitmentNotice))
            if notice.kind == "done"
        ]
    assert sorted(told) == sorted([people["ana"].id, people["zoe"].id])
