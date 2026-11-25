from tests.contract import administrator, check_reference, check_trace, write
from tests.projects.factories import make_axis, make_department, make_objective, make_term

BASE = "/api/dashboards/projects"


def world(client):
    municipality = administrator(client, "projects")
    term = make_term(municipality)
    axis = make_axis(municipality, term)
    project = {
        "term_id": str(term.id),
        "axis_id": str(axis.id),
        "department_id": str(make_department(municipality).id),
        "name": "Bacheo",
        "priority": "A",
        "year": 2024,
    }
    return municipality, term, axis, project


def test_what_is_created_leaves_a_trace_of_what_it_was(client):
    municipality, term, axis, project = world(client)
    objective = make_objective(municipality, axis)
    created = write(client, "POST", f"{BASE}/projects", project | {"name": "Otro"}).json()

    for path, body in (
        ("terms", {"name": "Otra", "start_year": 2028, "end_year": 2031}),
        ("axes", {"term_id": str(term.id), "name": "Eje"}),
        ("objectives", {"axis_id": str(axis.id), "name": "Objetivo"}),
        ("departments", {"name": "Hacienda"}),
        ("programs", {"name": "Programa"}),
        ("owners", {"full_name": "Ana"}),
        ("projects", project),
        (f"projects/{created['id']}/milestones", {"name": "Hito", "due_date": "2026-01-01"}),
        ("indicators", {"objective_id": str(objective.id), "name": "Cuadras"}),
    ):
        check_trace(client, "POST", f"{BASE}/{path}", body, "create")


def test_budgets_leave_a_trace_when_set_and_when_changed(client):
    _, term, _, _ = world(client)
    url = f"{BASE}/terms/{term.id}/budgets"

    check_trace(client, "PUT", url, {"year": 2024, "total_amount": "1.00"}, "create")
    before = {"year": 2024, "total_amount": "2.00"}
    write(client, "PUT", url, before)
    assert [b["total_amount"] for b in client.get(url).json()] == ["2.00"]


def test_ids_that_are_not_the_municipality_s_are_refused_by_name(client):
    municipality, term, axis, project = world(client)
    objective = make_objective(municipality, axis)
    indicator = {"objective_id": str(objective.id), "name": "Cuadras"}
    made = write(client, "POST", f"{BASE}/indicators", indicator).json()

    for path, body, field in (
        ("axes", {"name": "Eje"}, "term_id"),
        ("objectives", {"name": "Objetivo"}, "axis_id"),
        ("indicators", {"name": "Cuadras"}, "objective_id"),
        *(
            ("projects", project, field)
            for field in (
                "term_id",
                "axis_id",
                "objective_id",
                "department_id",
                "owner_id",
                "program_id",
            )
        ),
    ):
        check_reference(client, "POST", f"{BASE}/{path}", body, field)
    check_reference(client, "PATCH", f"{BASE}/indicators/{made['id']}", {}, "objective_id")
