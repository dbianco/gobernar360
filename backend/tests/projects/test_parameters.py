import pytest
from sqlalchemy import select

from gobernar360.core.db import tenant_session
from gobernar360.platform.models import AuditLog
from tests.factories import login, make_municipality
from tests.projects.factories import (
    make_axis,
    make_budget,
    make_department,
    make_objective,
    make_owner,
    make_program,
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


def test_term_cannot_be_shortened_past_its_projects_or_budgets(client):
    municipality = _admin(client)
    term = make_term(municipality)  # 2023-2027
    make_project(
        municipality, term, make_axis(municipality, term), make_department(municipality), year=2027
    )
    client.put(f"{BASE}/terms/{term.id}/budgets", json={"year": 2023, "total_amount": "10"})

    cut_end = client.patch(f"{BASE}/terms/{term.id}", json={"end_year": 2026})
    cut_start = client.patch(f"{BASE}/terms/{term.id}", json={"start_year": 2024})
    extend = client.patch(f"{BASE}/terms/{term.id}", json={"end_year": 2028})

    assert (cut_end.status_code, cut_start.status_code) == (409, 409)
    assert cut_end.json()["error"]["code"] == "in_use"
    assert extend.status_code == 200


PARAMETERS = [
    ("departments", {"name": "Obras"}, {"name": "Obras Públicas"}),
    ("programs", {"name": "Bacheo"}, {"name": "Plan de bacheo"}),
    ("owners", {"full_name": "María"}, {"full_name": "María Pérez"}),
]


@pytest.mark.parametrize(("path", "body", "changed"), PARAMETERS)
def test_each_parameter_is_created_renamed_listed_by_name_and_removed(client, path, body, changed):
    _admin(client)
    [field] = body
    created = client.post(f"{BASE}/{path}", json=body)
    client.post(f"{BASE}/{path}", json={field: "Archivo"})
    url = f"{BASE}/{path}/{created.json()['id']}"

    renamed = client.patch(url, json=changed)

    assert (created.status_code, renamed.status_code) == (201, 200)
    assert renamed.json() == {"id": created.json()["id"]} | changed
    names = [item[field] for item in client.get(f"{BASE}/{path}").json()]
    assert names == ["Archivo", changed[field]]
    assert client.delete(url).status_code == 204
    assert [item[field] for item in client.get(f"{BASE}/{path}").json()] == ["Archivo"]
    assert client.delete(url).status_code == 404
    assert client.patch(url, json=changed).status_code == 404


def test_axes_and_objectives_are_renamed_and_removed(client):
    municipality = _admin(client)
    term = make_term(municipality)
    axis = make_axis(municipality, term, "Ciudad")
    objective = make_objective(municipality, axis, "Luz")

    renamed = client.patch(f"{BASE}/axes/{axis.id}", json={"name": "Ciudad segura"})
    changed = client.patch(f"{BASE}/objectives/{objective.id}", json={"name": "Más luz"})

    assert renamed.json() == {
        "id": str(axis.id),
        "term_id": str(term.id),
        "name": "Ciudad segura",
    }
    assert (changed.status_code, changed.json()["name"]) == (200, "Más luz")
    # An axis is not removed from under its objectives.
    assert client.delete(f"{BASE}/axes/{axis.id}").status_code == 409
    assert client.delete(f"{BASE}/objectives/{objective.id}").status_code == 204
    assert client.delete(f"{BASE}/axes/{axis.id}").status_code == 204
    assert client.get(f"{BASE}/axes").json() == client.get(f"{BASE}/objectives").json() == []


def test_axes_and_objectives_are_listed_by_name_for_a_term_an_axis_or_all(client):
    municipality = _admin(client)
    old, new = make_term(municipality, "Vieja", 2019, 2022), make_term(municipality)
    axes = {name: make_axis(municipality, term, name) for name, term in (("B", old), ("A", new))}
    for name, axis in (("Tres", "A"), ("Dos", "B"), ("Uno", "A")):
        make_objective(municipality, axes[axis], name)

    def names(path, **params):
        return [item["name"] for item in client.get(f"{BASE}/{path}", params=params).json()]

    assert names("axes") == ["A", "B"]
    assert names("axes", term_id=str(old.id)) == ["B"]
    assert names("objectives") == ["Dos", "Tres", "Uno"]
    assert names("objectives", axis_id=str(axes["A"].id)) == ["Tres", "Uno"]
    assert names("objectives", term_id=str(old.id)) == ["Dos"]


def test_only_dashboard_admins_rename_or_remove_parameters(client):
    municipality = projects_member("editor")
    term = make_term(municipality)
    axis = make_axis(municipality, term)
    paths = [
        f"axes/{axis.id}",
        f"objectives/{make_objective(municipality, axis).id}",
        f"departments/{make_department(municipality).id}",
        f"programs/{make_program(municipality).id}",
        f"owners/{make_owner(municipality).id}",
    ]
    login(client, "ana@noetinger.test")

    for path in paths:
        body = {"full_name": "x"} if path.startswith("owners") else {"name": "x"}
        assert client.patch(f"{BASE}/{path}", json=body).status_code == 403, path
        assert client.delete(f"{BASE}/{path}").status_code == 403, path


def test_a_term_of_one_year_is_fine_and_one_that_ends_before_it_starts_is_not(client):
    municipality = _admin(client)
    term = make_term(municipality, start_year=2024, end_year=2026)
    url = f"{BASE}/terms/{term.id}"

    assert client.patch(url, json={"end_year": 2024}).json()["end_year"] == 2024
    refused = client.patch(url, json={"end_year": 2023})
    assert refused.status_code == 422
    assert refused.json()["error"] == {
        "code": "validation_error",
        "message": "end_year must not be before start_year.",
    }
    assert _term(client, start_year=2030, end_year=2030).status_code == 201
    created = _term(client, start_year=2030, end_year=2029)
    assert created.status_code == 422
    [detail] = created.json()["error"]["details"]
    assert detail["message"].endswith("end_year must not be before start_year")


def test_a_term_keeps_the_years_its_own_projects_and_budgets_are_in(client):
    municipality = _admin(client)
    term = make_term(municipality, start_year=2023, end_year=2027)
    other = make_term(municipality, "Otra", 2019, 2030)
    for owner, year in ((term, 2025), (other, 2019), (other, 2030)):
        make_project(
            municipality,
            owner,
            make_axis(municipality, owner),
            make_department(municipality),
            year=year,
        )
        make_budget(municipality, owner, year, 100)
        make_budget(municipality, owner, year + 1 if year < 2030 else 2029, 100)
    url = f"{BASE}/terms/{term.id}"

    # 2025 has a project and 2026 a budget; those of the other term are not its concern.
    for years in ({"end_year": 2025}, {"start_year": 2026}):
        refused = client.patch(url, json=years)
        assert refused.status_code == 409
        assert refused.json()["error"] == {
            "code": "in_use",
            "message": "The term has projects or budgets in the years being removed.",
        }
    assert client.patch(url, json={"start_year": 2025, "end_year": 2026}).status_code == 200


def test_a_budget_is_for_a_year_of_its_term_ends_included(client):
    municipality = _admin(client)
    term = make_term(municipality, start_year=2023, end_year=2027)
    other = make_term(municipality, "Otra", 2023, 2027)
    make_budget(municipality, other, 2027, 50)
    url = f"{BASE}/terms/{term.id}/budgets"

    for year in (2027, 2023, 2025):
        body = {"year": year, "total_amount": "100.00"}
        assert client.put(url, json=body).status_code == 200
    for year in (2022, 2028):
        refused = client.put(url, json={"year": year, "total_amount": "1"})
        assert refused.status_code == 422
        assert refused.json()["error"] == {
            "code": "validation_error",
            "message": "year must be within the term.",
        }
    listed = [(b["year"], b["total_amount"]) for b in client.get(url).json()]
    assert listed == [(2023, "100.00"), (2025, "100.00"), (2027, "100.00")]
    # Another term's budget of the same year is another budget.
    theirs = client.get(f"{BASE}/terms/{other.id}/budgets").json()
    assert [(b["year"], b["total_amount"]) for b in theirs] == [(2027, "50.00")]
