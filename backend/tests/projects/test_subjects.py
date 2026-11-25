"""Projects as linkable records."""

from tests.factories import login
from tests.projects.factories import (
    make_axis,
    make_department,
    make_project,
    make_term,
    projects_member,
)


def search(client, **params):
    response = client.get(
        "/api/subjects/search",
        params={"dashboard_key": "projects", "kind": "project"} | params,
    )
    assert response.status_code == 200, response.text
    return [(s["label"], s["path"]) for s in response.json()]


def make_projects(municipality, *named_years):
    term = make_term(municipality)
    axis, department = make_axis(municipality, term), make_department(municipality)
    return {
        name: f"/d/projects/projects/{project.id}"
        for name, year in named_years
        for project in [make_project(municipality, term, axis, department, name=name, year=year)]
    }


def test_projects_are_offered_by_name_the_latest_years_first(client):
    municipality = projects_member("viewer")
    paths = make_projects(
        municipality, ("Zanjeo", 2024), ("Árboles", 2024), ("Bacheo", 2024), ("Plaza", 2025)
    )
    login(client, "ana@noetinger.test")

    assert search(client) == [
        (name, paths[name]) for name in ("Plaza", "Árboles", "Bacheo", "Zanjeo")
    ]
    assert [label for label, _ in search(client, limit=2)] == ["Plaza", "Árboles"]


def test_projects_are_searched_ignoring_case_and_accents(client):
    municipality = projects_member("viewer")
    make_projects(municipality, ("Pavimentación San Martín", 2024), ("Plaza San Martín", 2024))
    login(client, "ana@noetinger.test")

    assert [label for label, _ in search(client, q="martin PAVIMENTACION")] == [
        "Pavimentación San Martín"
    ]
    assert search(client, q="100%") == []


def test_another_municipality_s_projects_are_not_offered(client):
    other = projects_member("admin", "beto@saira.test", municipality_name="Saira")
    make_projects(other, ("Ajeno", 2024))
    projects_member("viewer")
    login(client, "ana@noetinger.test")

    assert search(client) == []


def test_projects_are_not_offered_to_members_without_the_dashboard(client):
    municipality = projects_member(None)
    make_projects(municipality, ("Plaza", 2024))
    login(client, "ana@noetinger.test")

    response = client.get(
        "/api/subjects/search", params={"dashboard_key": "projects", "kind": "project"}
    )

    assert response.status_code == 403


def test_projects_of_a_year_come_by_name_whatever_order_they_were_loaded_in(client):
    municipality = projects_member("viewer")
    make_projects(municipality, *((name, 2024) for name in ("zanja", "Árbol", "bache", "Cordón")))
    login(client, "ana@noetinger.test")

    assert [label for label, _ in search(client)] == ["Árbol", "bache", "Cordón", "zanja"]
