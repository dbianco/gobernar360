"""The linkable-subject contract, exercised with a dashboard that exists only here.

The demo dashboard declares a kind of record and nothing else. That commitments can be
taken about it, and are shown next to it, without touching the cabinet module is the point
of the contract.
"""

import uuid
from datetime import date

import pytest
from fastapi import APIRouter

from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import (
    DashboardModule,
    LinkableRecord,
    SubjectRecord,
)
from tests.cabinet.factories import (
    URL,
    as_member,
    cabinet_member,
    close,
    commit,
    error,
    make_light,
    month_subject,
    pin_today,
    prepare,
)

ENABLED = ("demo", "cabinet", "environment")
THINGS = {
    uuid.UUID(int=1): "Cosa uno",
    uuid.UUID(int=2): "Cosa dos",
}
FIRST, SECOND = THINGS


def _record(thing_id: uuid.UUID) -> SubjectRecord:
    return SubjectRecord(id=thing_id, label=THINGS[thing_id], path=f"/d/demo/things/{thing_id}")


def _search(ctx, words, limit):
    return [_record(i) for i, name in sorted(THINGS.items()) if words in name][:limit]


def _describe(ctx, ids):
    return [_record(i) for i in THINGS if i in ids]


def thing(ref=FIRST) -> dict:
    return {"dashboard_key": "demo", "kind": "thing", "ref": str(ref)}


@pytest.fixture(autouse=True)
def demo(client):
    """A dashboard with a kind anyone with access may know and one only for its editors."""
    pin_today(client)
    registry.register(
        DashboardModule(
            key="demo",
            router=APIRouter(),
            get_summary=lambda ctx, today: [],
            linkable=(
                LinkableRecord("thing", _search, _describe),
                LinkableRecord("secret", _search, _describe, min_level="editor"),
            ),
        )
    )
    yield
    registry.unregister("demo")


def about(client, ref=FIRST, kind="thing", key="demo"):
    return client.get(f"/api/subjects/{key}/{kind}/{ref}/commitments")


def search(client, key="demo", kind="thing", **params):
    return client.get("/api/subjects/search", params={"dashboard_key": key, "kind": kind} | params)


# A dashboard the cabinet knows nothing about


def test_a_dashboard_that_only_declares_its_records_can_receive_commitments(client):
    municipality, ana = cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)
    item = prepare(client)["items"][0]

    taken = commit(client, item, ana, subject=thing())
    commit(client, item, ana, description="Otra", subject=thing(SECOND))

    assert taken["subject"] == {
        "access": "visible",
        "kind": "thing",
        "dashboard_key": "demo",
        "ref": str(FIRST),
        "label": "Cosa uno",
        "path": f"/d/demo/things/{FIRST}",
        "color": None,
    }
    assert about(client).json() == [
        {
            "id": taken["id"],
            "ref": str(FIRST),
            "description": "Certificar la obra",
            "owner": "Ana",
            "due_date": "2026-03-20",
            "overdue": False,
            "times_postponed": 0,
            "path": f"/commitments/{taken['id']}",
        }
    ]


def test_its_records_are_restricted_to_those_without_access(client):
    municipality, ana = cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)
    meeting = prepare(client)
    taken = commit(client, meeting["items"][0], ana, subject=thing())
    close(client, meeting)
    cabinet_member(client, "viewer", "leo@noetinger.test", municipality, enable=ENABLED)

    seen = client.get(f"/api/commitments/{taken['id']}").json()["subject"]

    assert (seen["access"], seen["kind"], seen["dashboard_key"]) == ("restricted", "thing", "demo")
    assert (seen["label"], seen["ref"], seen["path"]) == (None, None, None)
    # Documents have a text for kinds they know nothing about.
    minutes = client.get(f"{URL}/meetings/{meeting['id']}/minutes.html").text
    assert "Sobre: Un registro de un tablero al que no tenés acceso" in minutes


def test_a_kind_may_ask_for_more_than_viewing_the_dashboard(client):
    municipality, ana = cabinet_member(client, others={"demo": "editor"}, enable=ENABLED)
    subject = thing() | {"kind": "secret"}
    taken = commit(client, prepare(client)["items"][0], ana, subject=subject)
    assert taken["subject"]["label"] == "Cosa uno"
    assert [c["id"] for c in about(client, kind="secret").json()] == [taken["id"]]
    # The same record as another kind is another subject.
    assert about(client, kind="thing").json() == []

    cabinet_member(
        client, "editor", "leo@noetinger.test", municipality, {"demo": "viewer"}, ENABLED
    )
    seen = client.get(f"/api/commitments/{taken['id']}").json()["subject"]
    assert seen["access"] == "restricted"
    assert error(about(client, kind="secret")) == (403, "forbidden")
    assert error(search(client, kind="secret")) == (403, "forbidden")
    refused = client.patch(f"{URL}/commitments/{taken['id']}", json={"subject": subject})
    assert error(refused) == (422, "invalid_reference")


def test_a_record_that_is_gone_reads_as_deleted(client, monkeypatch):
    municipality, ana = cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)
    meeting = prepare(client)
    taken = commit(client, meeting["items"][0], ana, subject=thing())
    monkeypatch.delitem(THINGS, FIRST)

    seen = client.get(f"/api/commitments/{taken['id']}").json()["subject"]

    assert seen == {
        "access": "deleted",
        "kind": "thing",
        "dashboard_key": "demo",
        "ref": str(FIRST),
        "label": None,
        "path": None,
        "color": None,
    }
    close(client, meeting)
    minutes = client.get(f"{URL}/meetings/{meeting['id']}/minutes.html").text
    assert "Sobre: Un registro que ya no existe" in minutes


def test_a_dashboard_that_is_uninstalled_leaves_its_links_restricted(client):
    municipality, ana = cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)
    taken = commit(client, prepare(client)["items"][0], ana, subject=thing())
    registry.unregister("demo")

    seen = client.get(f"/api/commitments/{taken['id']}").json()["subject"]

    assert (seen["access"], seen["label"]) == ("restricted", None)


def test_a_declaration_cannot_take_the_place_of_months():
    with pytest.raises(ValueError, match="'month' is every dashboard's own month"):
        LinkableRecord("month", _search, _describe)


# Choosing what to link


def test_the_kinds_offered_are_those_the_member_may_see(client):
    cabinet_member(client, others={"demo": "editor"}, enable=ENABLED)

    assert client.get("/api/subjects/kinds").json() == [
        {"dashboard_key": "cabinet", "kind": "month"},
        {"dashboard_key": "demo", "kind": "month"},
        {"dashboard_key": "demo", "kind": "thing"},
        {"dashboard_key": "demo", "kind": "secret"},
    ]


def test_a_viewer_is_not_offered_what_needs_an_editor(client):
    cabinet_member(client, None, others={"demo": "viewer"}, enable=ENABLED)

    assert [k["kind"] for k in client.get("/api/subjects/kinds").json()] == ["month", "thing"]


def test_records_are_searched_by_their_dashboard(client):
    cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)

    assert [s["label"] for s in search(client).json()] == ["Cosa uno", "Cosa dos"]
    assert [s["label"] for s in search(client, limit=1).json()] == ["Cosa uno"]
    assert search(client, q="dos").json() == [
        {
            "access": "visible",
            "kind": "thing",
            "dashboard_key": "demo",
            "ref": str(SECOND),
            "label": "Cosa dos",
            "path": f"/d/demo/things/{SECOND}",
            "color": None,
        }
    ]


def test_months_are_offered_newest_first_with_their_light(client):
    municipality, _ = cabinet_member(client, others={"environment": "viewer"}, enable=ENABLED)
    make_light(municipality, "environment", 2026, 2, "red")
    make_light(municipality, "demo", 2026, 1, "yellow")

    months = search(client, "environment", "month", limit=50).json()

    assert len(months) == 24
    assert [(m["ref"], m["color"]) for m in months[:4]] == [
        ("2026-03", None),
        ("2026-02", "red"),
        ("2026-01", None),
        ("2025-12", None),
    ]
    assert months[-1]["ref"] == "2024-04"
    found = search(client, "environment", "month", q="Febrero 2026").json()
    assert [m["label"] for m in found] == ["Ambiental, febrero de 2026"]
    assert len(search(client, "environment", "month").json()) == 20


def test_months_of_a_dashboard_without_a_name_of_its_own_go_by_its_key(client):
    cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)

    [newest] = search(client, "demo", "month", limit=1).json()

    assert newest["label"] == "demo, marzo de 2026"


def test_nothing_is_searched_in_a_dashboard_the_member_cannot_open(client):
    cabinet_member(client, enable=ENABLED)

    for key, kind in (
        ("demo", "thing"),
        ("demo", "month"),
        ("environment", "month"),
        ("lottery", "month"),
        ("cabinet", "thing"),
    ):
        assert error(search(client, key, kind)) == (403, "forbidden"), (key, kind)


def test_subjects_need_a_session(client):
    assert client.get("/api/subjects/kinds").status_code == 401
    assert search(client).status_code == 401
    assert about(client).status_code == 401


# The reverse view


def test_commitments_about_a_subject_are_the_open_ones_soonest_first(client):
    municipality, ana = cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)
    meeting = prepare(client)
    item = meeting["items"][0]
    subject = thing()
    later = commit(client, item, ana, date(2026, 4, 1), description="Después", subject=subject)
    late = commit(client, item, ana, date(2026, 3, 9), description="Antes", subject=subject)
    tie = commit(client, item, ana, date(2026, 4, 1), description="Al mismo", subject=subject)
    done = commit(client, item, ana, date(2026, 3, 1), subject=subject)
    dropped = commit(client, item, ana, date(2026, 3, 1), subject=subject)
    commit(client, item, ana, date(2026, 3, 1))
    client.post(f"/api/commitments/{done['id']}/state", json={"state": "done"})
    client.post(f"/api/commitments/{dropped['id']}/state", json={"state": "dropped"})
    close(client, meeting)
    prepare(client)

    found = about(client, str(FIRST).upper()).json()

    assert [(c["id"], c["overdue"], c["times_postponed"]) for c in found] == [
        (late["id"], True, 1),
        (tie["id"], False, 1),
        (later["id"], False, 1),
    ]
    assert about(client, SECOND).json() == []
    assert about(client, "not-an-id").json() == []


def test_a_year_s_months_come_with_the_commitments_of_each(client):
    municipality, ana = cabinet_member(client, others={"environment": "viewer"}, enable=ENABLED)
    item = prepare(client)["items"][0]
    refs = ("2026-02", "2026-01", "2025-12")
    for day, ref in enumerate(refs, start=1):
        commit(client, item, ana, date(2026, 4, day), subject=month_subject("environment", ref))
    commit(client, item, ana, subject=month_subject("cabinet", "2026-02"))

    def months(key, year):
        response = client.get(f"/api/subjects/{key}/commitments", params={"year": year})
        assert response.status_code == 200
        return [c["ref"] for c in response.json()]

    assert months("environment", 2026) == ["2026-02", "2026-01"]
    assert months("environment", 2025) == ["2025-12"]
    assert months("cabinet", 2026) == ["2026-02"]
    assert about(client, "2025-12", "month", "environment").json()[0]["ref"] == "2025-12"
    assert about(client, "2025-13", "month", "environment").json() == []


def test_only_those_who_see_the_subject_and_the_commitments_get_them(client):
    municipality, ana = cabinet_member(
        client, others={"demo": "viewer", "environment": "viewer"}, enable=ENABLED
    )
    item = prepare(client)["items"][0]
    commit(client, item, ana, subject=thing())
    commit(client, item, ana, subject=month_subject("environment", "2026-02"))
    year = "/api/subjects/environment/commitments?year=2026"
    assert len(client.get(year).json()) == 1

    # Without the cabinet dashboard: the page works and shows none.
    both = {"demo": "admin", "environment": "admin"}
    cabinet_member(client, None, "leo@noetinger.test", municipality, both, ENABLED)
    assert (about(client).status_code, about(client).json()) == (200, [])
    assert client.get(year).json() == []
    # Without the subject's dashboard: refused.
    cabinet_member(client, "admin", "zoe@noetinger.test", municipality, enable=ENABLED)
    assert error(about(client)) == (403, "forbidden")
    assert error(client.get(year)) == (403, "forbidden")
    as_member(client)
    assert error(about(client, key="lottery")) == (403, "forbidden")
    assert error(about(client, kind="nothing")) == (403, "forbidden")


def test_another_municipality_s_commitments_are_not_shown(client):
    _, ana = cabinet_member(client, others={"demo": "viewer"}, enable=ENABLED)
    commit(client, prepare(client)["items"][0], ana, subject=thing())
    cabinet_member(
        client,
        email="beto@saira.test",
        municipality_name="Saira",
        others={"demo": "viewer"},
        enable=ENABLED,
    )

    # The same reference means nothing in another municipality.
    assert about(client).json() == []
