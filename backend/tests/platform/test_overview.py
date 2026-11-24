from datetime import date

from gobernar360.platform.clock import get_today
from gobernar360.platform.models import DashboardStatus
from tests.factories import (
    admin_session,
    current_overview,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.projects.factories import (
    make_axis,
    make_department,
    make_project,
    make_term,
    projects_member,
)


def test_overview_includes_projects_indicators_for_a_viewer(client):
    client.app.dependency_overrides[get_today] = lambda: date(2025, 6, 15)
    municipality = projects_member("viewer")
    old_term = make_term(municipality, name="Gestión 2019-2023", start_year=2019, end_year=2023)
    term = make_term(municipality)
    axis, department = make_axis(municipality, term), make_department(municipality)
    make_project(municipality, term, axis, department, name="Uno", status="finished")
    make_project(
        municipality,
        term,
        axis,
        department,
        name="Dos",
        status="in_progress",
        end_date=date(2025, 6, 1),
        planned_budget=200,
        executed_budget=50,
        milestones=[(date(2025, 5, 1), None)],
    )
    make_project(
        municipality, old_term, make_axis(municipality, old_term), department, name="Viejo"
    )
    login(client, "ana@noetinger.test")

    response = client.get("/api/overview")

    assert response.status_code == 200
    assert current_overview(response.json()) == [
        {
            "dashboard_key": "projects",
            "indicators": [
                {"key": "projects.active", "value": 1, "unit": None},
                {"key": "projects.finished", "value": 1, "unit": None},
                {"key": "projects.delayed", "value": 1, "unit": None},
                {"key": "projects.average_progress", "value": 50, "unit": "percent"},
                {"key": "projects.milestones_in_alert", "value": 1, "unit": None},
                {"key": "projects.budget_executed_ratio", "value": 0.25, "unit": "ratio"},
            ],
            "status": [],
        }
    ]


def test_overview_omits_dashboards_the_user_cannot_see(client):
    projects_member(None)
    login(client, "ana@noetinger.test")

    assert client.get("/api/overview").json() == []


def test_overview_for_municipality_without_terms_has_empty_indicators(client):
    projects_member("viewer")
    login(client, "ana@noetinger.test")

    assert client.get("/api/overview").json() == [
        {"dashboard_key": "projects", "indicators": [], "status": []}
    ]


def test_overview_requires_an_active_municipality(client):
    user = make_user("ana@noetinger.test")
    make_membership(user, make_municipality("Noetinger"))
    make_membership(user, make_municipality("Saira"))
    login(client, "ana@noetinger.test")

    assert client.get("/api/overview").status_code == 403


def test_overview_includes_recent_lights_newest_first(client):
    client.app.dependency_overrides[get_today] = lambda: date(2025, 2, 10)
    municipality = projects_member("viewer")
    lights = [(2024, 6, "red"), (2024, 11, "yellow"), (2025, 1, "green"), (2025, 3, "red")]
    with admin_session() as session, session.begin():
        for year, month, color in lights:
            session.add(
                DashboardStatus(
                    municipality_id=municipality.id,
                    dashboard_key="projects",
                    year=year,
                    month=month,
                    color=color,
                )
            )
        session.add(
            DashboardStatus(
                municipality_id=municipality.id,
                dashboard_key="environment",
                year=2025,
                month=2,
                color="red",
            )
        )
    login(client, "ana@noetinger.test")

    assert client.get("/api/overview").json()[0]["status"] == [
        {"year": 2025, "month": 1, "color": "green"},
        {"year": 2024, "month": 11, "color": "yellow"},
    ]


def test_overview_takes_the_latest_term_and_of_two_alike_the_first_by_name(client):
    client.app.dependency_overrides[get_today] = lambda: date(2025, 6, 15)
    municipality = projects_member("viewer")
    department = make_department(municipality)
    for name, start, projects in (
        ("Gestión B", 2023, 3),
        ("Gestión A", 2023, 2),
        ("Gestión vieja", 2019, 5),
    ):
        term = make_term(municipality, name=name, start_year=start, end_year=start + 4)
        axis = make_axis(municipality, term)
        for number in range(projects):
            make_project(municipality, term, axis, department, name=f"{name} {number}")
    login(client, "ana@noetinger.test")

    [section] = current_overview(client.get("/api/overview").json())

    assert section["indicators"][0] == {"key": "projects.active", "value": 2, "unit": None}
