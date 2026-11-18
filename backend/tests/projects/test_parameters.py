from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_municipality
from tests.projects.factories import (
    make_axis,
    make_department,
    make_project,
    make_term,
    projects_member,
)

BASE = "/api/dashboards/projects"


def _admin(client):
    municipality = projects_member("admin")
    login(client, "ana@noetinger.test")
    return municipality


def _term(client, **overrides):
    payload = {"name": "Gestión 2023-2027", "start_year": 2023, "end_year": 2027} | overrides
    return client.post(f"{BASE}/terms", json=payload)


def test_dashboard_admin_creates_term_axis_and_objective(client):
    _admin(client)

    term = _term(client)
    axis = client.post(f"{BASE}/axes", json={"term_id": term.json()["id"], "name": "Ciudad segura"})
    objective = client.post(
        f"{BASE}/objectives", json={"axis_id": axis.json()["id"], "name": "Más iluminación"}
    )

    assert (term.status_code, axis.status_code, objective.status_code) == (201, 201, 201)
    assert client.get(f"{BASE}/axes", params={"term_id": term.json()["id"]}).json() == [axis.json()]
    assert client.get(f"{BASE}/objectives", params={"axis_id": axis.json()["id"]}).json() == [
        objective.json()
    ]


def test_dashboard_admin_manages_departments_programs_and_owners(client):
    _admin(client)

    department = client.post(f"{BASE}/departments", json={"name": "  Obras Públicas  "})
    program = client.post(f"{BASE}/programs", json={"name": "Plan de bacheo"})
    owner = client.post(f"{BASE}/owners", json={"full_name": "María Pérez"})

    assert department.json()["name"] == "Obras Públicas"
    renamed = client.patch(
        f"{BASE}/programs/{program.json()['id']}", json={"name": "Plan de pavimento"}
    )
    assert renamed.json()["name"] == "Plan de pavimento"
    assert client.delete(f"{BASE}/owners/{owner.json()['id']}").status_code == 204
    assert client.get(f"{BASE}/owners").json() == []


def test_blank_parameter_name_is_rejected(client):
    _admin(client)

    assert client.post(f"{BASE}/departments", json={"name": "   "}).status_code == 422


def test_editor_cannot_change_parameters(client):
    municipality = projects_member("editor")
    term = make_term(municipality)
    login(client, "ana@noetinger.test")

    assert _term(client).status_code == 403
    assert client.post(f"{BASE}/departments", json={"name": "Salud"}).status_code == 403
    assert client.delete(f"{BASE}/terms/{term.id}").status_code == 403


def test_viewer_lists_parameters(client):
    municipality = projects_member("viewer")
    make_term(municipality)
    make_department(municipality, "Salud")
    login(client, "ana@noetinger.test")

    assert [t["name"] for t in client.get(f"{BASE}/terms").json()] == ["Gestión 2023-2027"]
    assert [d["name"] for d in client.get(f"{BASE}/departments").json()] == ["Salud"]


def test_member_without_grant_cannot_list_parameters(client):
    projects_member(None)
    login(client, "ana@noetinger.test")

    assert client.get(f"{BASE}/terms").status_code == 403


def test_parameters_of_another_municipality_are_not_listed(client):
    other = make_municipality("Saira")
    make_department(other, "Hacienda de Saira")
    other_term = make_term(other)
    _admin(client)

    assert client.get(f"{BASE}/departments").json() == []
    assert client.get(f"{BASE}/terms").json() == []
    assert client.patch(f"{BASE}/terms/{other_term.id}", json={"name": "x"}).status_code == 404
    assert client.delete(f"{BASE}/terms/{other_term.id}").status_code == 404


def test_objective_cannot_reference_axis_of_another_municipality(client):
    other = make_municipality("Saira")
    foreign_axis = make_axis(other, make_term(other))
    _admin(client)

    response = client.post(
        f"{BASE}/objectives", json={"axis_id": str(foreign_axis.id), "name": "Objetivo"}
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"


def test_deleting_axis_used_by_a_project_returns_in_use(client):
    municipality = _admin(client)
    term = make_term(municipality)
    axis = make_axis(municipality, term)
    department = make_department(municipality)
    make_project(municipality, term, axis, department)

    for path in (f"axes/{axis.id}", f"departments/{department.id}", f"terms/{term.id}"):
        response = client.delete(f"{BASE}/{path}")
        assert response.status_code == 409, path
        assert response.json()["error"]["code"] == "in_use"
    assert len(client.get(f"{BASE}/axes").json()) == 1


def test_term_end_year_before_start_year_is_rejected(client):
    _admin(client)

    assert _term(client, start_year=2027, end_year=2023).status_code == 422


def test_term_cannot_be_shortened_to_end_before_it_starts(client):
    _admin(client)
    term_id = _term(client).json()["id"]

    assert client.patch(f"{BASE}/terms/{term_id}", json={"end_year": 2020}).status_code == 422


def test_annual_budget_upsert_replaces_existing_year(client):
    _admin(client)
    term_id = _term(client).json()["id"]
    url = f"{BASE}/terms/{term_id}/budgets"

    client.put(url, json={"year": 2024, "total_amount": "1000.00"})
    response = client.put(url, json={"year": 2024, "total_amount": "2500.50"})

    assert response.status_code == 200
    assert client.get(url).json() == [{"year": 2024, "total_amount": "2500.50"}]


def test_annual_budget_outside_the_term_years_is_rejected(client):
    _admin(client)
    term_id = _term(client).json()["id"]

    response = client.put(
        f"{BASE}/terms/{term_id}/budgets", json={"year": 2030, "total_amount": "10.00"}
    )

    assert response.status_code == 422


def test_negative_annual_budget_is_rejected(client):
    _admin(client)
    term_id = _term(client).json()["id"]

    response = client.put(
        f"{BASE}/terms/{term_id}/budgets", json={"year": 2024, "total_amount": "-1"}
    )

    assert response.status_code == 422


def test_parameter_change_is_audited(client):
    municipality = _admin(client)

    department_id = client.post(f"{BASE}/departments", json={"name": "Salud"}).json()["id"]
    client.patch(f"{BASE}/departments/{department_id}", json={"name": "Salud y Ambiente"})
    client.delete(f"{BASE}/departments/{department_id}")

    with tenant_session(municipality.id) as db:
        entries = db.scalars(select(AuditLog).order_by(AuditLog.created_at)).all()
    assert [(e.action, e.entity_type) for e in entries] == [
        ("create", "projects_departments"),
        ("update", "projects_departments"),
        ("delete", "projects_departments"),
    ]
    assert entries[1].changes == {"name": "Salud y Ambiente"}
