from datetime import date

from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
from tests.economic.factories import (
    BASE,
    EMAIL,
    economic_member,
    make_actor,
    make_assignment,
    make_economic_person,
    make_person,
    make_tool,
)
from tests.factories import login, make_municipality


def _editor(client):
    municipality = economic_member("editor")
    login(client, EMAIL)
    return municipality


def _post(client, **body):
    return client.post(f"{BASE}/assignments", json={"date": "2026-03-10"} | body)


def test_editor_assigns_a_tool_to_an_actor_and_to_a_person(client):
    municipality = _editor(client)
    tool = make_tool(municipality)
    actor = make_actor(municipality)
    person = make_economic_person(municipality)

    to_actor = _post(client, tool_id=str(tool.id), actor_id=str(actor.id), note=" Primera cuota ")
    to_person = _post(client, tool_id=str(tool.id), person_id=str(person.id))

    assert (to_actor.status_code, to_person.status_code) == (201, 201)
    assert to_actor.json() == {
        "id": to_actor.json()["id"],
        "date": "2026-03-10",
        "note": "Primera cuota",
        "tool": {"id": str(tool.id), "name": "Microcrédito productivo"},
        "actor": {"id": str(actor.id), "name": "Panadería La Espiga"},
        "person": None,
    }
    assert to_person.json()["actor"] is None
    assert to_person.json()["person"] == {"id": str(person.id), "full_name": "Pérez, Juana"}


def test_assignment_needs_exactly_one_recipient(client):
    municipality = _editor(client)
    tool = make_tool(municipality)
    actor = make_actor(municipality)
    person = make_economic_person(municipality)

    both = _post(client, tool_id=str(tool.id), actor_id=str(actor.id), person_id=str(person.id))
    neither = _post(client, tool_id=str(tool.id))

    assert (both.status_code, neither.status_code) == (422, 422)
    assert client.get(f"{BASE}/assignments").json()["total"] == 0


def test_tool_audience_limits_who_can_receive_it(client):
    municipality = _editor(client)
    for_actors = make_tool(municipality, name="Para actores", audience="actors")
    for_people = make_tool(municipality, name="Para personas", audience="people")
    actor = make_actor(municipality)
    person = make_economic_person(municipality)

    wrong_person = _post(client, tool_id=str(for_actors.id), person_id=str(person.id))
    wrong_actor = _post(client, tool_id=str(for_people.id), actor_id=str(actor.id))
    right_actor = _post(client, tool_id=str(for_actors.id), actor_id=str(actor.id))
    right_person = _post(client, tool_id=str(for_people.id), person_id=str(person.id))

    assert (wrong_person.status_code, wrong_actor.status_code) == (422, 422)
    assert wrong_person.json()["error"]["code"] == "validation_error"
    assert (right_actor.status_code, right_person.status_code) == (201, 201)


def test_assignment_cannot_reference_records_outside_the_dashboard(client):
    other = make_municipality("Saira")
    foreign_tool, foreign_actor = make_tool(other), make_actor(other)
    foreign_person = make_economic_person(other)
    municipality = _editor(client)
    tool, actor = make_tool(municipality), make_actor(municipality)
    registry_only = make_person(municipality, "Solo", "Padrón")

    responses = [
        _post(client, tool_id=str(foreign_tool.id), actor_id=str(actor.id)),
        _post(client, tool_id=str(tool.id), actor_id=str(foreign_actor.id)),
        _post(client, tool_id=str(tool.id), person_id=str(foreign_person.id)),
        _post(client, tool_id=str(tool.id), person_id=str(registry_only.id)),
    ]

    assert [r.status_code for r in responses] == [422] * 4
    assert {r.json()["error"]["code"] for r in responses} == {"invalid_reference"}
    assert client.get(f"{BASE}/assignments").json()["total"] == 0


def test_assignments_are_listed_newest_first_and_filtered(client):
    municipality = _editor(client)
    credit, course = make_tool(municipality), make_tool(municipality, name="Curso de costos")
    actor, person = make_actor(municipality), make_economic_person(municipality)
    make_assignment(municipality, credit, actor=actor, on=date(2026, 1, 5))
    make_assignment(municipality, course, person=person, on=date(2026, 12, 31))
    make_assignment(municipality, course, actor=actor, on=date(2025, 12, 31))
    other = make_municipality("Saira")
    make_assignment(other, make_tool(other), actor=make_actor(other))

    def dates(**params):
        response = client.get(f"{BASE}/assignments", params=params)
        assert response.status_code == 200, response.text
        return [item["date"] for item in response.json()["items"]]

    assert dates() == ["2026-12-31", "2026-01-05", "2025-12-31"]
    assert dates(year=2026) == ["2026-12-31", "2026-01-05"]
    assert dates(year=2025) == ["2025-12-31"]
    assert dates(tool_id=str(course.id)) == ["2026-12-31", "2025-12-31"]
    assert dates(actor_id=str(actor.id)) == ["2026-01-05", "2025-12-31"]
    assert dates(person_id=str(person.id)) == ["2026-12-31"]
    assert dates(limit=1, offset=1) == ["2026-01-05"]
    assert client.get(f"{BASE}/assignments", params={"limit": 1}).json()["total"] == 3


def test_only_date_and_note_of_an_assignment_can_change(client):
    municipality = _editor(client)
    tool, other_tool = make_tool(municipality), make_tool(municipality, name="Otra")
    assignment = make_assignment(municipality, tool, actor=make_actor(municipality))

    changed = client.patch(
        f"{BASE}/assignments/{assignment.id}", json={"date": "2026-04-01", "note": "Renovado"}
    )
    retargeted = client.patch(
        f"{BASE}/assignments/{assignment.id}", json={"tool_id": str(other_tool.id)}
    )

    assert changed.status_code == 200
    assert (changed.json()["date"], changed.json()["note"]) == ("2026-04-01", "Renovado")
    assert retargeted.status_code == 422
    assert (
        client.patch(f"{BASE}/assignments/{assignment.id}", json={"date": None}).status_code == 422
    )


def test_assignment_is_deleted_and_audited(client):
    municipality = _editor(client)
    tool, actor = make_tool(municipality), make_actor(municipality)

    assignment_id = _post(client, tool_id=str(tool.id), actor_id=str(actor.id)).json()["id"]
    assert client.delete(f"{BASE}/assignments/{assignment_id}").status_code == 204

    assert client.get(f"{BASE}/assignments").json()["total"] == 0
    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.action, e.entity_type) for e in entries] == [
        ("create", "economic_assignments"),
        ("delete", "economic_assignments"),
    ]


def test_records_with_assignments_cannot_be_deleted(client):
    municipality = economic_member("admin")
    login(client, EMAIL)
    tool = make_tool(municipality)
    actor, person = make_actor(municipality), make_economic_person(municipality)
    make_assignment(municipality, tool, actor=actor)
    make_assignment(municipality, tool, person=person)

    for path in (f"tools/{tool.id}", f"actors/{actor.id}", f"people/{person.id}"):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"
    assert client.get(f"{BASE}/people/{person.id}").status_code == 200


def test_viewer_reads_assignments_but_cannot_change_them(client):
    municipality = economic_member("viewer")
    tool, actor = make_tool(municipality), make_actor(municipality)
    assignment = make_assignment(municipality, tool, actor=actor)
    login(client, EMAIL)

    assert client.get(f"{BASE}/assignments").json()["total"] == 1
    assert _post(client, tool_id=str(tool.id), actor_id=str(actor.id)).status_code == 403
    assert (
        client.patch(f"{BASE}/assignments/{assignment.id}", json={"note": "x"}).status_code == 403
    )
    assert client.delete(f"{BASE}/assignments/{assignment.id}").status_code == 403


def test_assignments_of_another_municipality_are_not_reachable(client):
    other = make_municipality("Saira")
    foreign = make_assignment(other, make_tool(other), actor=make_actor(other))
    _editor(client)

    assert client.get(f"{BASE}/assignments").json() == {"items": [], "total": 0}
    assert client.patch(f"{BASE}/assignments/{foreign.id}", json={"note": "x"}).status_code == 404
    assert client.delete(f"{BASE}/assignments/{foreign.id}").status_code == 404


def test_assignments_are_searched_by_tool_or_recipient(client):
    municipality = _editor(client)
    credit = make_tool(municipality, name="Microcrédito productivo")
    course = make_tool(municipality, name="Curso de marketing")
    bakery = make_actor(municipality, name="Panadería La Espiga")
    juana = make_economic_person(municipality, "Juana", "Pérez", dni="20123456")
    make_assignment(municipality, credit, actor=bakery, on=date(2026, 3, 1))
    make_assignment(municipality, course, person=juana, on=date(2026, 3, 2))

    def tools(q):
        items = client.get(f"{BASE}/assignments", params={"q": q}).json()["items"]
        return [item["tool"]["name"] for item in items]

    assert tools("credito") == ["Microcrédito productivo"]
    assert tools("panaderia") == ["Microcrédito productivo"]
    assert tools("perez juana") == ["Curso de marketing"]
    assert tools("20.123.456") == ["Curso de marketing"]
    assert tools("nadie") == []
    assert len(tools("")) == 2


def test_a_year_runs_from_the_first_of_january_to_the_thirty_first_of_december(client):
    municipality = _editor(client)
    tool = make_tool(municipality)
    actor = make_actor(municipality)
    for day in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 12, 31), date(2027, 1, 1)):
        make_assignment(municipality, tool, actor=actor, on=day)

    items = client.get(f"{BASE}/assignments", params={"year": 2026}).json()["items"]

    assert sorted(item["date"] for item in items) == ["2026-01-01", "2026-12-31"]
