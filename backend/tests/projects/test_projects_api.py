from datetime import date

import pytest
from sqlalchemy import func, select

from gobernar360.core.db import tenant_session
from gobernar360.dashboards.projects.clock import get_today
from gobernar360.dashboards.projects.models import Project
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_municipality
from tests.projects.factories import (
    make_axis,
    make_department,
    make_objective,
    make_project,
    make_term,
    projects_member,
)

BASE = "/api/dashboards/projects"
TODAY = date(2025, 6, 15)


@pytest.fixture
def plan(client):
    """An editor signed in to a municipality that has a term, an axis and a department."""
    client.app.dependency_overrides[get_today] = lambda: TODAY
    municipality = projects_member("editor")
    term = make_term(municipality)
    axis = make_axis(municipality, term)
    department = make_department(municipality)
    login(client, "ana@noetinger.test")
    return {"municipality": municipality, "term": term, "axis": axis, "department": department}


def _payload(plan, **overrides):
    return {
        "term_id": str(plan["term"].id),
        "name": "Pavimentación de la calle San Martín",
        "axis_id": str(plan["axis"].id),
        "department_id": str(plan["department"].id),
        "priority": "A+",
        "year": 2024,
    } | overrides


def _project_count(municipality) -> int:
    with tenant_session(municipality.id) as db:
        return db.scalar(select(func.count()).select_from(Project))


def test_editor_creates_project_with_sdgs(client, plan):
    response = client.post(
        f"{BASE}/projects",
        json=_payload(plan, sdgs=[11, 9], planned_budget="1500000", executed_budget="250000.5"),
    )

    assert response.status_code == 201
    body = response.json()
    assert body["sdgs"] == [9, 11]
    assert body["planned_budget"] == "1500000.00"
    assert body["executed_budget"] == "250000.50"
    assert body["axis"] == {"id": str(plan["axis"].id), "name": "Ciudad inclusiva"}
    assert body["department"]["name"] == "Obras Públicas"
    assert (body["status"], body["effective_status"], body["progress"]) == (
        "not_started",
        "not_started",
        0,
    )
    assert client.get(f"{BASE}/projects/{body['id']}").json() == body


def test_viewer_cannot_create_project(client, plan):
    projects_member("viewer", email="vera@noetinger.test", municipality=plan["municipality"])
    client.post("/api/auth/logout")
    login(client, "vera@noetinger.test")

    assert client.post(f"{BASE}/projects", json=_payload(plan)).status_code == 403
    assert client.get(f"{BASE}/projects").status_code == 200


def test_project_cannot_reference_axis_of_another_municipality(client, plan):
    other = make_municipality("Saira")
    foreign_axis = make_axis(other, make_term(other))

    response = client.post(f"{BASE}/projects", json=_payload(plan, axis_id=str(foreign_axis.id)))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"
    assert _project_count(plan["municipality"]) == 0


def test_project_cannot_reference_department_of_another_municipality(client, plan):
    foreign_department = make_department(make_municipality("Saira"))

    response = client.post(
        f"{BASE}/projects", json=_payload(plan, department_id=str(foreign_department.id))
    )

    assert response.status_code == 422
    assert _project_count(plan["municipality"]) == 0


def test_project_update_cannot_point_to_another_municipality(client, plan):
    foreign_department = make_department(make_municipality("Saira"))
    project_id = client.post(f"{BASE}/projects", json=_payload(plan)).json()["id"]

    response = client.patch(
        f"{BASE}/projects/{project_id}", json={"department_id": str(foreign_department.id)}
    )

    assert response.status_code == 422


def test_axis_must_belong_to_the_project_term(client, plan):
    other_term = make_term(
        plan["municipality"], name="Gestión 2019-2023", start_year=2019, end_year=2023
    )
    other_axis = make_axis(plan["municipality"], other_term, "Eje anterior")

    response = client.post(f"{BASE}/projects", json=_payload(plan, axis_id=str(other_axis.id)))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"


def test_objective_must_belong_to_the_project_axis(client, plan):
    other_axis = make_axis(plan["municipality"], plan["term"], "Ciudad segura")
    objective = make_objective(plan["municipality"], other_axis)

    response = client.post(f"{BASE}/projects", json=_payload(plan, objective_id=str(objective.id)))

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"


def test_changing_the_axis_requires_a_matching_objective(client, plan):
    objective = make_objective(plan["municipality"], plan["axis"])
    other_axis = make_axis(plan["municipality"], plan["term"], "Ciudad segura")
    project_id = client.post(
        f"{BASE}/projects", json=_payload(plan, objective_id=str(objective.id))
    ).json()["id"]

    mismatch = client.patch(f"{BASE}/projects/{project_id}", json={"axis_id": str(other_axis.id)})
    cleared = client.patch(
        f"{BASE}/projects/{project_id}", json={"axis_id": str(other_axis.id), "objective_id": None}
    )

    assert mismatch.status_code == 422
    assert cleared.status_code == 200
    assert cleared.json()["objective"] is None


def test_project_year_outside_term_is_rejected(client, plan):
    assert client.post(f"{BASE}/projects", json=_payload(plan, year=2030)).status_code == 422


def test_end_date_before_start_date_is_rejected(client, plan):
    response = client.post(
        f"{BASE}/projects", json=_payload(plan, start_date="2024-05-01", end_date="2024-04-30")
    )

    assert response.status_code == 422


def test_sdg_number_out_of_range_is_rejected(client, plan):
    assert client.post(f"{BASE}/projects", json=_payload(plan, sdgs=[18])).status_code == 422


def test_unknown_priority_or_status_is_rejected(client, plan):
    assert client.post(f"{BASE}/projects", json=_payload(plan, priority="D")).status_code == 422
    assert client.post(f"{BASE}/projects", json=_payload(plan, status="delayed")).status_code == 422


def test_negative_budget_is_rejected(client, plan):
    assert (
        client.post(f"{BASE}/projects", json=_payload(plan, planned_budget="-1")).status_code == 422
    )


def test_project_list_filters_by_year_axis_department_owner_and_priority(client, plan):
    municipality, term = plan["municipality"], plan["term"]
    other_axis = make_axis(municipality, term, "Ciudad segura")
    other_department = make_department(municipality, "Salud")
    owner_id = _as_admin_create_owner(client, plan)
    client.post(f"{BASE}/projects", json=_payload(plan, name="Uno", owner_id=owner_id))
    make_project(
        municipality, term, other_axis, other_department, name="Dos", year=2025, priority="C"
    )

    def names(**params):
        return [p["name"] for p in client.get(f"{BASE}/projects", params=params).json()]

    assert names() == ["Dos", "Uno"]
    assert names(term_id=str(term.id)) == ["Dos", "Uno"]
    assert names(year=2025) == ["Dos"]
    assert names(axis_id=str(other_axis.id)) == ["Dos"]
    assert names(department_id=str(other_department.id)) == ["Dos"]
    assert names(owner_id=owner_id) == ["Uno"]
    assert names(priority="A+") == ["Uno"]


def _as_admin_create_owner(client, plan) -> str:
    projects_member("admin", email="admin@noetinger.test", municipality=plan["municipality"])
    client.post("/api/auth/logout")
    login(client, "admin@noetinger.test")
    owner_id = client.post(f"{BASE}/owners", json={"full_name": "María Pérez"}).json()["id"]
    client.post("/api/auth/logout")
    login(client, "ana@noetinger.test")
    return owner_id


def test_project_list_filters_by_delayed_status(client, plan):
    client.post(f"{BASE}/projects", json=_payload(plan, name="A tiempo", end_date="2025-12-31"))
    client.post(
        f"{BASE}/projects",
        json=_payload(plan, name="Vencido", end_date="2025-06-14", status="in_progress"),
    )

    delayed = client.get(f"{BASE}/projects", params={"status": "delayed"}).json()
    in_progress = client.get(f"{BASE}/projects", params={"status": "in_progress"}).json()

    assert [p["name"] for p in delayed] == ["Vencido"]
    assert delayed[0]["status"] == "in_progress"
    assert delayed[0]["effective_status"] == "delayed"
    assert in_progress == []


def test_project_of_another_municipality_returns_not_found(client, plan):
    other = make_municipality("Saira")
    term = make_term(other)
    foreign = make_project(other, term, make_axis(other, term), make_department(other))

    assert client.get(f"{BASE}/projects/{foreign.id}").status_code == 404
    assert client.patch(f"{BASE}/projects/{foreign.id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"{BASE}/projects/{foreign.id}").status_code == 404
    assert (
        client.post(
            f"{BASE}/projects/{foreign.id}/milestones", json={"name": "x", "due_date": "2025-01-01"}
        ).status_code
        == 404
    )
    assert client.get(f"{BASE}/projects").json() == []


def test_editor_updates_and_deletes_a_project(client, plan):
    project_id = client.post(f"{BASE}/projects", json=_payload(plan, sdgs=[1, 2])).json()["id"]

    updated = client.patch(
        f"{BASE}/projects/{project_id}",
        json={"name": "Nuevo nombre", "status": "in_progress", "manual_progress": 35, "sdgs": [3]},
    )

    assert updated.status_code == 200
    assert (updated.json()["name"], updated.json()["progress"], updated.json()["sdgs"]) == (
        "Nuevo nombre",
        35,
        [3],
    )
    assert client.delete(f"{BASE}/projects/{project_id}").status_code == 204
    assert client.get(f"{BASE}/projects/{project_id}").status_code == 404


def test_completing_milestones_updates_progress_and_alert(client, plan):
    project_id = client.post(
        f"{BASE}/projects", json=_payload(plan, status="in_progress", end_date="2025-12-31")
    ).json()["id"]
    url = f"{BASE}/projects/{project_id}/milestones"
    overdue = client.post(url, json={"name": "Licitación", "due_date": "2025-06-01"})
    client.post(url, json={"name": "Inicio de obra", "due_date": "2025-09-01"})

    before = client.get(f"{BASE}/projects/{project_id}").json()
    client.patch(f"{BASE}/milestones/{overdue.json()['id']}", json={"completed_on": "2025-06-10"})
    after = client.get(f"{BASE}/projects/{project_id}").json()

    assert overdue.status_code == 201
    assert [m["in_alert"] for m in before["milestones"]] == [True, False]
    assert (before["effective_status"], before["progress"]) == ("delayed", 0)
    assert [m["in_alert"] for m in after["milestones"]] == [False, False]
    assert (after["effective_status"], after["progress"]) == ("in_progress", 50)


def test_editor_deletes_a_milestone(client, plan):
    project_id = client.post(f"{BASE}/projects", json=_payload(plan)).json()["id"]
    milestone_id = client.post(
        f"{BASE}/projects/{project_id}/milestones", json={"name": "Hito", "due_date": "2025-09-01"}
    ).json()["id"]

    assert client.delete(f"{BASE}/milestones/{milestone_id}").status_code == 204
    assert client.get(f"{BASE}/projects/{project_id}").json()["milestones"] == []


def test_editor_manages_indicators(client, plan):
    objective = make_objective(plan["municipality"], plan["axis"])

    created = client.post(
        f"{BASE}/indicators",
        json={
            "objective_id": str(objective.id),
            "name": "Cuadras pavimentadas",
            "unit": "cuadras",
            "baseline": "120",
            "target": "200",
            "current_value": "150",
        },
    )
    indicator_id = created.json()["id"]
    updated = client.patch(f"{BASE}/indicators/{indicator_id}", json={"current_value": "175.5"})
    listed = client.get(f"{BASE}/indicators", params={"term_id": str(plan["term"].id)}).json()

    assert created.status_code == 201
    assert updated.json()["current_value"] == 175.5
    assert [i["name"] for i in listed] == ["Cuadras pavimentadas"]
    assert listed[0]["objective"]["name"] == objective.name
    assert listed[0]["axis"]["name"] == "Ciudad inclusiva"
    assert client.delete(f"{BASE}/indicators/{indicator_id}").status_code == 204
    assert client.get(f"{BASE}/indicators").json() == []


def test_indicator_cannot_reference_objective_of_another_municipality(client, plan):
    other = make_municipality("Saira")
    foreign = make_objective(other, make_axis(other, make_term(other)))

    response = client.post(
        f"{BASE}/indicators", json={"objective_id": str(foreign.id), "name": "Indicador"}
    )

    assert response.status_code == 422


def test_sdg_catalog_lists_the_17_goals(client, plan):
    assert client.get(f"{BASE}/sdgs").json() == list(range(1, 18))


def test_project_changes_are_audited(client, plan):
    project_id = client.post(f"{BASE}/projects", json=_payload(plan)).json()["id"]
    client.patch(f"{BASE}/projects/{project_id}", json={"status": "finished"})

    with tenant_session(plan["municipality"].id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
        project = db.get(Project, project_id)

    assert [(e.action, e.entity_type, e.entity_id) for e in entries] == [
        ("create", "projects_projects", project_id),
        ("update", "projects_projects", project_id),
    ]
    assert entries[1].changes == {"status": "finished"}
    assert project.created_by == entries[0].user_id


def test_patch_cannot_clear_required_fields(client, plan):
    objective = make_objective(plan["municipality"], plan["axis"])
    project_id = client.post(f"{BASE}/projects", json=_payload(plan)).json()["id"]
    milestone_id = client.post(
        f"{BASE}/projects/{project_id}/milestones", json={"name": "Hito", "due_date": "2025-09-01"}
    ).json()["id"]
    indicator_id = client.post(
        f"{BASE}/indicators", json={"objective_id": str(objective.id), "name": "Indicador"}
    ).json()["id"]

    responses = [
        client.patch(f"{BASE}/projects/{project_id}", json={"name": None}),
        client.patch(f"{BASE}/projects/{project_id}", json={"department_id": None}),
        client.patch(f"{BASE}/projects/{project_id}", json={"year": None}),
        client.patch(f"{BASE}/milestones/{milestone_id}", json={"due_date": None}),
        client.patch(f"{BASE}/indicators/{indicator_id}", json={"objective_id": None}),
    ]

    assert [r.status_code for r in responses] == [422] * 5


def test_patch_can_clear_optional_fields(client, plan):
    project_id = client.post(
        f"{BASE}/projects", json=_payload(plan, end_date="2025-12-31", manual_progress=20)
    ).json()["id"]

    response = client.patch(
        f"{BASE}/projects/{project_id}", json={"end_date": None, "manual_progress": None}
    )

    assert response.status_code == 200
    assert (response.json()["end_date"], response.json()["manual_progress"]) == (None, None)
