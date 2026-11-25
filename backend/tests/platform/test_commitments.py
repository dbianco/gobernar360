"""Commitments any member gives to any other, outside meetings; and those of meetings for
whoever owes them or is attached without having the cabinet dashboard."""

import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import select

from gobernar360.dashboards import registry
from gobernar360.platform.commitment_models import CommitmentNotice
from gobernar360.platform.models import AuditLog
from tests.cabinet.factories import (
    TODAY,
    cabinet_member,
    close,
    commit,
    error,
    make_simple_project,
    pin_today,
    prepare,
    project_subject,
)
from tests.cabinet.factories import URL as CABINET
from tests.factories import (
    admin_session,
    enable_dashboards,
    login,
    make_membership,
    make_municipality,
    make_user,
)

URL = "/api/commitments"
DUE = date(2026, 3, 20)
FORBIDDEN = (403, "forbidden")
NOT_FOUND = (404, "not_found")


@pytest.fixture(autouse=True)
def pinned_today(client):
    pin_today(client)


@pytest.fixture
def people():
    """Members of Noetinger with no dashboard: Ana, Leo, Zoe and Max; and its administrator."""
    municipality = make_municipality()
    enable_dashboards(municipality, ["projects", "cabinet"])
    found = {}
    for name in ("ana", "leo", "zoe", "max"):
        found[name] = make_user(f"{name}@noetinger.test")
        make_membership(found[name], municipality)
    found["admin"] = make_user("admin@noetinger.test")
    make_membership(found["admin"], municipality, admin=True, enable=[])
    found["municipality"] = municipality
    return found


def as_(client, name: str) -> None:
    client.cookies.clear()
    login(client, f"{name}@noetinger.test")


def give(client, owner, due: date = DUE, **fields) -> dict:
    body = {"description": "Enviar nota", "owner_id": str(owner.id), "due_date": due.isoformat()}
    response = client.post(URL, json=body | fields)
    assert response.status_code == 201, response.text
    return response.json()


def get(client, commitment):
    return client.get(f"{URL}/{commitment['id']}")


def patch(client, commitment, **fields):
    return client.patch(f"{URL}/{commitment['id']}", json=fields)


def set_state(client, commitment, state, **fields):
    return client.post(f"{URL}/{commitment['id']}/state", json={"state": state} | fields)


def add_note(client, commitment, note="Avanza."):
    return client.post(f"{URL}/{commitment['id']}/notes", json={"note": note})


def listed(client, relation: str = "mine", **params) -> list[str]:
    response = client.get(URL, params={"relation": relation} | params)
    assert response.status_code == 200, response.text
    page = response.json()
    assert page["total"] == len(page["items"])
    return [c["description"] for c in page["items"]]


# Giving


def test_a_member_gives_another_one_a_commitment(client, people):
    as_(client, "ana")

    given = give(
        client,
        people["leo"],
        description=" Enviar nota ",
        follower_ids=[str(people["zoe"].id), str(people["max"].id), str(people["zoe"].id)],
    )

    assert given == {
        "id": given["id"],
        "description": "Enviar nota",
        "owner": {"id": str(people["leo"].id), "full_name": "Leo"},
        "creator": {"id": str(people["ana"].id), "full_name": "Ana"},
        "due_date": "2026-03-20",
        "state": "open",
        "completed_on": None,
        "times_postponed": 0,
        "subject": None,
        "source": None,
        "origin": None,
        "followers": [
            {"id": str(people["max"].id), "full_name": "Max"},
            {"id": str(people["zoe"].id), "full_name": "Zoe"},
        ],
        "rights": {
            "see": True,
            "finish": False,
            "reschedule": True,
            "manage": True,
            "edit": True,
            "note": True,
        },
        "history": [],
    }


def test_a_member_gives_themselves_one(client, people):
    as_(client, "ana")

    given = give(client, people["ana"])

    assert all(given["rights"].values())
    assert set_state(client, given, "done").json()["state"] == "done"


def test_it_may_be_linked_only_to_what_its_creator_sees(client, people):
    project = make_simple_project(people["municipality"])
    as_(client, "ana")
    body = {"description": "x", "owner_id": str(people["leo"].id), "due_date": "2026-03-20"}

    refused = client.post(URL, json=body | {"subject": project_subject(project)})

    assert error(refused) == (422, "invalid_reference")
    as_(client, "admin")
    given = give(client, people["leo"], subject=project_subject(project))
    assert given["subject"]["label"] == "Pavimentación"
    # Whoever owes it learns that it is about a project, and not which.
    as_(client, "leo")
    assert get(client, given).json()["subject"]["access"] == "restricted"
    assert "Pavimentación" not in get(client, given).text


def test_it_is_given_only_to_active_members_and_the_same_for_those_attached(client, people):
    stranger = make_user("beto@saira.test")
    make_membership(stranger, make_municipality("Saira"))
    inactive = make_user("ida@noetinger.test", active=False)
    make_membership(inactive, people["municipality"])
    as_(client, "ana")

    for user in (stranger, inactive):
        body = {"description": "x", "owner_id": str(user.id), "due_date": "2026-03-20"}
        refused = client.post(URL, json=body)
        assert refused.status_code == 422
        assert refused.json()["error"] == {
            "code": "invalid_reference",
            "message": "owner_id does not reference a member of the municipality.",
        }
        body |= {"owner_id": str(people["leo"].id), "follower_ids": [str(user.id)]}
        refused = client.post(URL, json=body)
        assert refused.json()["error"] == {
            "code": "invalid_reference",
            "message": "follower_ids does not reference a member of the municipality.",
        }
    assert listed(client, "given") == []


@pytest.mark.parametrize(
    "change", [{"description": " "}, {"due_date": None}, {"owner_id": None}, {"source": "cabinet"}]
)
def test_it_needs_what_who_and_when_and_nothing_else(client, people, change):
    as_(client, "ana")
    body = {
        "description": "x",
        "owner_id": str(people["leo"].id),
        "due_date": "2026-03-20",
    }

    assert error(client.post(URL, json=body | change)) == (422, "validation_error")


# Who sees it


def test_an_informal_one_is_seen_by_its_creator_its_owner_and_those_attached(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])

    for name in ("ana", "leo", "zoe"):
        as_(client, name)
        assert get(client, given).status_code == 200, name
    # Nobody else, administrators included: to them it does not exist.
    for name in ("max", "admin"):
        as_(client, name)
        for response in (
            get(client, given),
            patch(client, given, due_date="2026-04-01"),
            set_state(client, given, "done"),
            add_note(client, given),
        ):
            assert error(response) == NOT_FOUND, name
        assert [listed(client, relation) for relation in ("mine", "given", "following")] == [
            [],
            [],
            [],
        ]


def test_members_of_the_cabinet_do_not_see_informal_ones(client, people):
    make_membership(
        make_user("gabi@noetinger.test"),
        people["municipality"],
        grants={"cabinet": "admin"},
        enable=[],
    )
    as_(client, "ana")
    given = give(client, people["leo"])
    as_(client, "gabi")

    assert error(get(client, given)) == NOT_FOUND
    assert client.get(f"{CABINET}/commitments").json()["total"] == 0


def test_another_municipality_s_are_not_found_even_for_a_shared_account(client, people):
    saira = make_municipality("Saira")
    make_membership(people["leo"], saira)
    as_(client, "ana")
    given = give(client, people["leo"])
    client.cookies.clear()
    login(client, "leo@noetinger.test")
    switched = client.post("/api/auth/active-municipality", json={"municipality_id": str(saira.id)})
    assert switched.status_code == 200, switched.text

    assert error(get(client, given)) == NOT_FOUND
    assert listed(client) == []
    assert client.get("/api/notifications").json() == {"mine": [], "others": []}


def test_a_meeting_s_one_is_seen_without_its_meeting_by_whoever_owes_it_or_is_attached(client):
    municipality, _ = cabinet_member(client, email="gabi@noetinger.test")
    leo, zoe, max_ = (make_user(f"{name}@noetinger.test") for name in ("leo", "zoe", "max"))
    for user in (leo, zoe, max_):
        make_membership(user, municipality)
    meeting = prepare(client, agenda=["Tema reservado"])
    taken = commit(client, meeting["items"][0], leo, follower_ids=[str(zoe.id)])
    close(client, meeting)
    prepare(client)

    for name in ("leo", "zoe"):
        as_(client, name)
        seen = get(client, taken)
        assert seen.status_code == 200
        assert (seen.json()["source"], seen.json()["origin"]) == ("cabinet", None)
        assert seen.json()["times_postponed"] == 1
        assert "reservado" not in seen.text and meeting["id"] not in seen.text
        assert client.get(f"{CABINET}/meetings/{meeting['id']}").status_code == 403
    as_(client, "max")
    assert error(get(client, taken)) == NOT_FOUND


def test_losing_the_dashboard_loses_its_commitments_also_for_whoever_recorded_them(client):
    municipality, gabi = cabinet_member(client, email="gabi@noetinger.test")
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    taken = commit(client, prepare(client)["items"][0], leo)
    as_(client, "gabi")
    assert get(client, taken).status_code == 200
    with admin_session() as session, session.begin():
        from gobernar360.platform.models import DashboardGrant

        for grant in session.scalars(select(DashboardGrant)):
            session.delete(grant)

    assert error(get(client, taken)) == NOT_FOUND
    assert listed(client, "given") == []


# Lists


def test_each_list_has_what_the_member_owes_gave_or_is_attached_to(client, people):
    ana, leo = people["ana"], people["leo"]
    as_(client, "ana")
    give(client, leo, description="De Ana a Leo")
    give(client, ana, description="De Ana a Ana")
    as_(client, "leo")
    give(client, people["zoe"], description="De Leo a Zoe", follower_ids=[str(ana.id)])
    give(client, ana, description="De Leo a Ana", follower_ids=[str(ana.id)])

    as_(client, "ana")
    assert sorted(listed(client)) == ["De Ana a Ana", "De Leo a Ana"]
    # What is one's own is not given to, nor followed of, somebody else.
    assert listed(client, "given") == ["De Ana a Leo"]
    assert listed(client, "following") == ["De Leo a Zoe"]
    as_(client, "leo")
    assert listed(client) == ["De Ana a Leo"]
    assert sorted(listed(client, "given")) == ["De Leo a Ana", "De Leo a Zoe"]
    assert listed(client, "following") == []
    assert client.get(URL, params={"relation": "all"}).status_code == 422


def test_lists_put_open_ones_first_by_due_date_and_are_searched_and_filtered(client, people):
    leo = people["leo"]
    as_(client, "ana")
    done = give(client, leo, date(2026, 1, 1), description="Hecho")
    give(client, leo, date(2026, 3, 11), description="Después")
    give(client, leo, date(2026, 3, 9), description="Señalización")
    give(client, leo, date(2026, 3, 10), description="Hoy")
    dropped = give(client, leo, date(2026, 1, 2), description="Descartado")
    set_state(client, dropped, "dropped")
    as_(client, "leo")
    set_state(client, done, "done")

    assert listed(client) == ["Señalización", "Hoy", "Después", "Hecho", "Descartado"]
    assert listed(client, state="pending") == ["Señalización", "Hoy", "Después"]
    assert listed(client, state="overdue") == ["Señalización"]
    assert listed(client, state="open") == ["Hoy", "Después"]
    assert listed(client, state="done") == ["Hecho"]
    assert listed(client, state="dropped") == ["Descartado"]
    assert listed(client, q="senalizacion leo") == ["Señalización"]
    assert listed(client, q="nada") == []
    page = client.get(URL, params={"limit": 2, "offset": 1}).json()
    assert (page["total"], [c["description"] for c in page["items"]]) == (5, ["Hoy", "Después"])


# Who changes it


def test_whoever_owes_it_says_it_is_done_and_changes_the_date_the_owner_and_those_attached(
    client, people
):
    as_(client, "ana")
    given = give(client, people["leo"])
    as_(client, "leo")
    assert get(client, given).json()["rights"] == {
        "see": True,
        "finish": True,
        "reschedule": True,
        "manage": False,
        "edit": False,
        "note": True,
    }

    assert add_note(client, given).status_code == 201
    moved = patch(client, given, due_date="2026-04-01", follower_ids=[str(people["max"].id)]).json()
    assert (moved["due_date"], [f["full_name"] for f in moved["followers"]]) == (
        "2026-04-01",
        ["Max"],
    )
    for refused in (
        patch(client, given, description="Otra cosa"),
        patch(client, given, subject=None),
        set_state(client, given, "dropped"),
    ):
        assert error(refused) == FORBIDDEN
    done = set_state(client, given, "done", completed_on="2026-03-09", note="Listo.").json()
    assert (done["state"], done["completed_on"]) == ("done", "2026-03-09")
    assert error(set_state(client, given, "open")) == FORBIDDEN


def test_the_creator_corrects_drops_and_reopens_but_does_not_say_it_is_done(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])

    changed = patch(
        client,
        given,
        description="Enviar la nota",
        due_date="2026-04-01",
        owner_id=str(people["zoe"].id),
    ).json()
    assert (changed["description"], changed["owner"]["full_name"]) == ("Enviar la nota", "Zoe")
    assert error(set_state(client, given, "done")) == FORBIDDEN
    assert set_state(client, given, "dropped").json()["state"] == "dropped"
    assert set_state(client, given, "open").json()["state"] == "open"


def test_whoever_owes_a_dropped_one_cannot_bring_it_back_by_saying_it_is_done(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    set_state(client, given, "dropped")

    as_(client, "leo")
    assert error(set_state(client, given, "done")) == FORBIDDEN

    as_(client, "ana")
    assert get(client, given).json()["state"] == "dropped"
    assert set_state(client, given, "open").json()["state"] == "open"
    as_(client, "leo")
    assert set_state(client, given, "done").json()["state"] == "done"


def test_those_attached_only_read_it(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    as_(client, "zoe")

    rights = get(client, given).json()["rights"]
    assert [name for name, allowed in rights.items() if allowed] == ["see"]
    for refused in (
        patch(client, given, due_date="2026-04-01"),
        patch(client, given, owner_id=str(people["zoe"].id)),
        patch(client, given, follower_ids=[]),
        patch(client, given, description="x"),
        set_state(client, given, "done"),
        set_state(client, given, "dropped"),
        add_note(client, given),
    ):
        assert error(refused) == FORBIDDEN


def test_cabinet_viewers_read_and_editors_change_those_of_meetings(client):
    municipality, _ = cabinet_member(client, email="gabi@noetinger.test")
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality)
    taken = commit(client, prepare(client)["items"][0], leo)
    cabinet_member(client, "viewer", "vera@noetinger.test", municipality)

    rights = get(client, taken).json()["rights"]
    assert [name for name, allowed in rights.items() if allowed] == ["see"]
    assert get(client, taken).json()["origin"]["label"] == "Reunión del 10/03/2026"
    assert error(set_state(client, taken, "done")) == FORBIDDEN
    as_(client, "gabi")
    assert set_state(client, taken, "done").status_code == 200
    assert set_state(client, taken, "open").status_code == 200
    assert patch(client, taken, due_date="2026-05-01").json()["due_date"] == "2026-05-01"


def test_whoever_gives_theirs_to_another_no_longer_has_to_do_with_it(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    as_(client, "leo")

    answer = patch(client, given, owner_id=str(people["zoe"].id))

    assert answer.status_code == 200
    assert (answer.json()["owner"]["full_name"], answer.json()["rights"]["see"]) == ("Zoe", False)
    assert error(get(client, given)) == NOT_FOUND
    as_(client, "zoe")
    assert listed(client) == ["Enviar nota"]


def test_whoever_created_it_keeps_it_in_sight_after_giving_it_to_another(client, people):
    as_(client, "ana")
    own = give(client, people["ana"])

    answer = patch(client, own, owner_id=str(people["zoe"].id)).json()

    assert answer["rights"]["see"] is True
    # Saying it is done goes with owing it.
    assert answer["rights"]["finish"] is False
    assert error(set_state(client, own, "done")) == FORBIDDEN
    assert get(client, own).status_code == 200
    assert (listed(client), listed(client, "given")) == ([], ["Enviar nota"])


def test_whoever_has_the_cabinet_keeps_a_meeting_s_one_in_sight_after_giving_it_to_another(client):
    municipality, _ = cabinet_member(client, email="gabi@noetinger.test")
    vera, leo, zoe = (make_user(f"{name}@noetinger.test") for name in ("vera", "leo", "zoe"))
    make_membership(vera, municipality, grants={"cabinet": "viewer"}, enable=[])
    for user in (leo, zoe):
        make_membership(user, municipality)
    item = prepare(client)["items"][0]
    by_viewer, by_other = commit(client, item, vera), commit(client, item, leo)

    for name, taken, status in (("vera", by_viewer, 200), ("leo", by_other, 404)):
        as_(client, name)
        answer = patch(client, taken, owner_id=str(zoe.id))
        assert answer.json()["rights"]["see"] is (status == 200), name
        assert get(client, taken).status_code == status, name


def test_giving_it_to_another_while_staying_attached_keeps_it_in_sight(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    as_(client, "leo")

    answer = patch(
        client, given, owner_id=str(people["zoe"].id), follower_ids=[str(people["leo"].id)]
    )

    assert answer.json()["rights"]["see"] is True
    assert listed(client, "following") == ["Enviar nota"]


def test_someone_attached_who_left_the_municipality_stays_attached(client, people):
    as_(client, "ana")
    given = give(client, people["leo"], follower_ids=[str(people["zoe"].id)])
    with admin_session() as session, session.begin():
        from gobernar360.platform.models import Membership

        session.delete(
            session.scalar(select(Membership).where(Membership.user_id == people["zoe"].id))
        )

    both = [str(people["zoe"].id), str(people["max"].id)]
    answer = patch(client, given, follower_ids=both)

    assert [f["full_name"] for f in answer.json()["followers"]] == ["Max", "Zoe"]


def test_its_history_keeps_who_changed_what_newest_first(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    patch(client, given, description="Enviar la nota")
    patch(client, given, description="Enviar la nota", due_date="2026-03-20")
    as_(client, "leo")
    patch(client, given, due_date="2026-04-01")
    add_note(client, given, " Falta la firma. ")
    set_state(client, given, "done")
    set_state(client, given, "done")
    set_state(client, given, "done", completed_on="2026-03-08")

    history = get(client, given).json()["history"]

    assert [(e["author"], e["note"], e["changes"]) for e in history] == [
        ("Leo", "", {"completed_on": ["2026-03-10", "2026-03-08"]}),
        ("Leo", "", {"state": ["open", "done"], "completed_on": [None, "2026-03-10"]}),
        ("Leo", "Falta la firma.", {}),
        ("Leo", "", {"due_date": ["2026-03-20", "2026-04-01"]}),
        ("Ana", "", {"description": ["Enviar nota", "Enviar la nota"]}),
    ]


def test_a_finished_one_is_not_changed_until_it_is_reopened(client, people):
    as_(client, "ana")
    given = give(client, people["ana"])
    set_state(client, given, "done")

    for fields in ({"due_date": "2026-04-01"}, {"description": "x"}, {"follower_ids": []}):
        assert error(patch(client, given, **fields)) == (409, "commitment_finished")
    set_state(client, given, "open")
    assert patch(client, given, due_date="2026-04-01").status_code == 200


def test_it_is_not_delivered_in_the_future(client, people):
    as_(client, "ana")
    given = give(client, people["ana"])
    tomorrow = (TODAY + timedelta(days=1)).isoformat()

    assert error(set_state(client, given, "done", completed_on=tomorrow)) == (
        422,
        "validation_error",
    )


def test_the_link_is_changed_by_its_creator(client, people):
    project = make_simple_project(people["municipality"])
    as_(client, "admin")
    given = give(client, people["leo"])

    linked = patch(client, given, subject=project_subject(project)).json()
    assert linked["subject"]["label"] == "Pavimentación"
    assert patch(client, given, subject=None).json()["subject"] is None


def test_one_that_does_not_exist_is_not_found(client, people):
    as_(client, "ana")

    assert error(get(client, {"id": uuid.uuid4()})) == NOT_FOUND


def test_what_is_done_is_audited(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    patch(client, given, due_date="2026-04-01")

    with admin_session() as session:
        entries = session.execute(
            select(AuditLog.action, AuditLog.changes, AuditLog.user_id)
            .where(AuditLog.entity_type == "commitments", AuditLog.entity_id == given["id"])
            .order_by(AuditLog.created_at)
        ).all()
    assert [(action, user_id) for action, _, user_id in entries] == [
        ("create", people["ana"].id),
        ("update", people["ana"].id),
    ]
    assert entries[0].changes == {
        "description": "Enviar nota",
        "owner_id": str(people["leo"].id),
        "due_date": "2026-03-20",
        "source": None,
    }
    assert entries[1].changes == {"due_date": "2026-04-01"}


# The reverse view


def test_an_informal_one_is_shown_beside_its_subject_only_to_those_who_see_it(client):
    both = {"projects": "viewer"}
    municipality, ana = cabinet_member(client, None, "ana@noetinger.test", others=both)
    project = make_simple_project(municipality)
    leo = make_user("leo@noetinger.test")
    make_membership(leo, municipality, grants=both, enable=[])
    make_membership(make_user("zoe@noetinger.test"), municipality, grants=both, enable=[])
    given = give(client, leo, subject=project_subject(project))
    url = f"/api/subjects/projects/project/{project.id}/commitments"

    assert [(c["id"], c["path"]) for c in client.get(url).json()] == [
        (given["id"], f"/commitments/{given['id']}")
    ]
    as_(client, "leo")
    assert len(client.get(url).json()) == 1
    as_(client, "zoe")
    assert client.get(url).json() == []


def test_every_route_needs_a_session(client):
    some = uuid.uuid4()
    for response in (
        client.get(URL),
        client.post(URL, json={}),
        client.get(f"{URL}/{some}"),
        client.get("/api/notifications"),
        client.post("/api/notifications/read", json={}),
    ):
        assert response.status_code == 401


def test_notices_of_another_member_are_not_touched(client, people):
    as_(client, "ana")
    give(client, people["leo"])
    client.post("/api/notifications/read", json={})

    with admin_session() as session:
        [notice] = session.scalars(select(CommitmentNotice))
    assert (notice.user_id, notice.read_at) == (people["leo"].id, None)


def test_one_recorded_by_a_dashboard_no_longer_installed_has_no_origin(client):
    municipality, ana = cabinet_member(client)
    taken = commit(client, prepare(client)["items"][0], ana)
    module = registry.get_module("cabinet")
    registry.unregister("cabinet")
    try:
        seen = get(client, taken).json()
    finally:
        registry.register(module)

    # Theirs to deliver all the same.
    assert (seen["origin"], seen["times_postponed"], seen["rights"]["finish"]) == (None, 0, True)


def test_an_owner_changed_to_a_stranger_is_refused_by_name(client, people):
    as_(client, "ana")
    given = give(client, people["leo"])
    stranger = make_user("beto@saira.test")

    refused = patch(client, given, owner_id=str(stranger.id))

    assert refused.status_code == 422
    assert refused.json()["error"] == {
        "code": "invalid_reference",
        "message": "owner_id does not reference a member of the municipality.",
    }


def test_an_informal_one_is_linked_to_months_up_to_the_current_one(client):
    _, ana = cabinet_member(client, None, "ana@noetinger.test", others={"projects": "viewer"})

    def link(month):
        return {"dashboard_key": "projects", "kind": "month", "ref": month}

    given = give(client, ana, subject=link("2026-03"))
    assert given["subject"]["ref"] == "2026-03"
    assert patch(client, given, subject=link("2026-02")).json()["subject"]["ref"] == "2026-02"
    assert error(patch(client, given, subject=link("2026-04"))) == (422, "invalid_reference")
    body = {
        "description": "x",
        "owner_id": str(ana.id),
        "due_date": "2026-03-20",
        "subject": link("2026-04"),
    }
    assert error(client.post(URL, json=body)) == (422, "invalid_reference")
