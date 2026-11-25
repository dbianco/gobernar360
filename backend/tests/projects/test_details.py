"""What the API answers about indicators and milestones, and what is told by email."""

import uuid
from datetime import date

import pytest

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.projects.alerts import get_alerts
from gobernar360.platform.clock import get_today
from tests.factories import login
from tests.projects.factories import (
    make_axis,
    make_department,
    make_objective,
    make_project,
    make_term,
    projects_member,
)

BASE = "/api/dashboards/projects"
TODAY = date(2026, 3, 10)


@pytest.fixture
def plan(client):
    client.app.dependency_overrides[get_today] = lambda: TODAY
    municipality = projects_member("editor")
    term = make_term(municipality)
    login(client, "ana@noetinger.test")
    return {
        "municipality": municipality,
        "term": term,
        "axis": make_axis(municipality, term, "B"),
        "department": make_department(municipality),
    }


def _project(plan, name, milestones=(), **fields):
    return make_project(
        plan["municipality"],
        plan["term"],
        plan["axis"],
        plan["department"],
        name=name,
        milestones=milestones,
        **fields,
    )


def test_an_indicator_answers_with_every_measure(client, plan):
    objective = make_objective(plan["municipality"], plan["axis"], "O")
    body = {"objective_id": str(objective.id), "name": "Cuadras", "unit": "cuadras"}

    full = client.post(
        f"{BASE}/indicators",
        json=body | {"baseline": 1.5, "target": 20, "current_value": 7.25},
    ).json()
    bare = client.post(f"{BASE}/indicators", json=body).json()

    assert full == {
        "id": full["id"],
        "name": "Cuadras",
        "unit": "cuadras",
        "baseline": 1.5,
        "target": 20,
        "current_value": 7.25,
        "objective": {"id": str(objective.id), "name": "O"},
        "axis": {"id": str(plan["axis"].id), "name": "B"},
    }
    assert (bare["baseline"], bare["target"], bare["current_value"]) == (None, None, None)


def test_indicators_come_by_axis_objective_and_name(client, plan):
    municipality = plan["municipality"]
    first = make_axis(municipality, plan["term"], "A")
    for axis, objective, names in (
        (plan["axis"], "P", ("A",)),
        (first, "R", ("A",)),
        (first, "Q", ("Z", "Y")),
    ):
        parent = make_objective(municipality, axis, objective)
        for name in names:
            client.post(f"{BASE}/indicators", json={"objective_id": str(parent.id), "name": name})

    listed = client.get(f"{BASE}/indicators").json()

    assert [(i["axis"]["name"], i["objective"]["name"], i["name"]) for i in listed] == [
        ("A", "Q", "Y"),
        ("A", "Q", "Z"),
        ("A", "R", "A"),
        ("B", "P", "A"),
    ]


def test_a_milestone_answers_when_it_was_completed(client, plan):
    project = _project(plan, "Plaza")
    path = f"{BASE}/projects/{project.id}/milestones"

    done = client.post(
        path, json={"name": "Hecho", "due_date": "2026-01-01", "completed_on": "2026-01-02"}
    ).json()
    late = client.post(path, json={"name": "Tarde", "due_date": "2026-03-09"}).json()
    today = client.post(path, json={"name": "Hoy", "due_date": "2026-03-10"}).json()

    assert (done["completed_on"], done["in_alert"]) == ("2026-01-02", False)
    assert (late["completed_on"], late["in_alert"]) == (None, True)
    assert today["in_alert"] is False


def test_alerts_are_the_milestones_past_due_of_projects_under_way(client, plan):
    past, before, today = date(2026, 3, 9), date(2026, 1, 5), TODAY
    _project(plan, "B", [(past, None), (past, date(2026, 3, 9)), (today, None)])
    _project(plan, "A", [(past, None), (before, None)])
    _project(plan, "Lista", [(before, None)], status="finished")

    with tenant_session(plan["municipality"].id) as db:
        alerts = get_alerts(db, TODAY)

    assert [(a.params["project"], a.params["due_date"]) for a in alerts] == [
        ("A", "05/01/2026"),
        ("A", "09/03/2026"),
        ("B", "09/03/2026"),
    ]
    assert {a.kind for a in alerts} == {"milestone_overdue"}
    assert all(a.event_key.endswith((":2026-03-09", ":2026-01-05")) for a in alerts)
    assert len({a.event_key for a in alerts}) == 3


def test_several_milestones_of_a_project_are_told_by_name(client, plan):
    project = _project(plan, "A")
    for name in ("Zanja", "Asfalto"):
        client.post(
            f"{BASE}/projects/{project.id}/milestones",
            json={"name": name, "due_date": "2026-01-01"},
        )

    with tenant_session(plan["municipality"].id) as db:
        assert [a.params["milestone"] for a in get_alerts(db, TODAY)] == ["Asfalto", "Zanja"]


@pytest.mark.parametrize("field", ["actor_type_id", "sector_id"])
def test_an_actor_names_the_reference_that_does_not_exist(client, field):
    from tests.economic.factories import economic_member

    economic_member("editor", email="eco@noetinger.test", municipality_name="Saira")
    login(client, "eco@noetinger.test")

    response = client.post(
        "/api/dashboards/economic/actors", json={"name": "x", field: str(uuid.uuid4())}
    )

    assert response.status_code == 422
    assert response.json()["error"] == {
        "code": "invalid_reference",
        "message": f"{field} does not reference an existing record.",
    }
