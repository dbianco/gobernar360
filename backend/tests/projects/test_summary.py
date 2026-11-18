from datetime import date
from decimal import Decimal

import pytest

from gobernar360.dashboards.projects.summary import compute_summary
from gobernar360.platform.clock import get_today
from tests.factories import login, make_municipality
from tests.projects.factories import (
    make_axis,
    make_budget,
    make_department,
    make_owner,
    make_program,
    make_project,
    make_term,
    projects_member,
)

BASE = "/api/dashboards/projects"
TODAY = date(2025, 6, 15)
PAST, FUTURE = date(2025, 6, 1), date(2025, 12, 1)


@pytest.fixture
def plan(client):
    client.app.dependency_overrides[get_today] = lambda: TODAY
    municipality = projects_member("viewer")
    term = make_term(municipality)
    login(client, "ana@noetinger.test")
    return {
        "municipality": municipality,
        "term": term,
        "axis": make_axis(municipality, term),
        "department": make_department(municipality),
    }


def _project(plan, **fields):
    return make_project(
        plan["municipality"], plan["term"], plan["axis"], plan["department"], **fields
    )


def _summary(client, plan, **params):
    response = client.get(f"{BASE}/summary", params={"term_id": str(plan["term"].id)} | params)
    assert response.status_code == 200, response.text
    return response.json()


def test_summary_of_term_without_projects_is_all_zero_and_null_ratios(client, plan):
    assert _summary(client, plan) == {
        "status_counts": {"not_started": 0, "in_progress": 0, "delayed": 0, "finished": 0},
        "active_count": 0,
        "finished_count": 0,
        "average_progress": 0,
        "budget": {
            "total": None,
            "planned": "0.00",
            "executed": "0.00",
            "planned_ratio": None,
            "executed_ratio": None,
        },
        "milestones": {"total": 0, "completed": 0, "in_alert": 0},
        "by_department": [],
        "by_owner": [],
        "by_program": [],
        "by_sdg": [],
    }


def test_pure_summary_of_no_projects_has_no_division_errors():
    summary = compute_summary([], total_budget=Decimal("0"), today=TODAY)

    assert summary.average_progress == 0
    assert summary.budget.planned_ratio is None
    assert summary.budget.executed_ratio is None


def test_summary_requires_a_term(client, plan):
    assert client.get(f"{BASE}/summary").status_code == 422


def test_summary_of_unknown_term_returns_not_found(client, plan):
    response = client.get(
        f"{BASE}/summary", params={"term_id": "00000000-0000-0000-0000-000000000000"}
    )

    assert response.status_code == 404


def test_summary_counts_projects_by_effective_status(client, plan):
    _project(plan, name="Sin iniciar")
    _project(plan, name="En curso", status="in_progress", end_date=FUTURE, manual_progress=40)
    _project(plan, name="Vencido", status="in_progress", end_date=PAST, manual_progress=20)
    _project(plan, name="Terminado", status="finished", end_date=PAST)

    summary = _summary(client, plan)

    assert summary["status_counts"] == {
        "not_started": 1,
        "in_progress": 1,
        "delayed": 1,
        "finished": 1,
    }
    assert (summary["active_count"], summary["finished_count"]) == (3, 1)
    assert summary["average_progress"] == 40  # (0 + 40 + 20 + 100) / 4


def test_summary_budget_ratios(client, plan):
    make_budget(plan["municipality"], plan["term"], 2023, Decimal("1000"))
    _project(plan, name="Uno", planned_budget=Decimal("300"), executed_budget=Decimal("100"))
    _project(plan, name="Dos", planned_budget=Decimal("100"))

    assert _summary(client, plan)["budget"] == {
        "total": "1000.00",
        "planned": "400.00",
        "executed": "100.00",
        "planned_ratio": 0.4,
        "executed_ratio": 0.25,
    }


def test_summary_budget_total_follows_the_year_filter(client, plan):
    make_budget(plan["municipality"], plan["term"], 2023, Decimal("1000"))
    make_budget(plan["municipality"], plan["term"], 2024, Decimal("3000"))

    assert _summary(client, plan)["budget"]["total"] == "4000.00"
    assert _summary(client, plan, year=2024)["budget"]["total"] == "3000.00"
    assert _summary(client, plan, year=2025)["budget"]["total"] is None


def test_summary_with_zero_planned_budget_has_null_executed_ratio(client, plan):
    make_budget(plan["municipality"], plan["term"], 2023, Decimal("0"))
    _project(plan, executed_budget=Decimal("50"))

    budget = _summary(client, plan)["budget"]

    assert (budget["planned_ratio"], budget["executed_ratio"]) == (None, None)
    assert budget["total"] == "0.00"


def test_summary_counts_milestones_and_alerts(client, plan):
    _project(plan, name="Uno", milestones=[(PAST, PAST), (PAST, None), (FUTURE, None)])
    _project(plan, name="Terminado", status="finished", milestones=[(PAST, None)])

    # An unfinished milestone of a finished project still counts as pending, but not as an alert.
    assert _summary(client, plan)["milestones"] == {"total": 4, "completed": 1, "in_alert": 1}


def test_summary_groups_by_department_owner_program_and_sdg(client, plan):
    municipality, term, axis = plan["municipality"], plan["term"], plan["axis"]
    health = make_department(municipality, "Salud")
    owner = make_owner(municipality)
    program = make_program(municipality)
    _project(plan, name="Uno", owner_id=owner.id, program_id=program.id, sdgs=[11, 3])
    _project(plan, name="Dos", sdgs=[11])
    make_project(municipality, term, axis, health, name="Tres")

    summary = _summary(client, plan)

    assert [(row["name"], row["count"]) for row in summary["by_department"]] == [
        ("Obras Públicas", 2),
        ("Salud", 1),
    ]
    assert summary["by_owner"] == [{"id": str(owner.id), "name": "María Pérez", "count": 1}]
    assert summary["by_program"] == [{"id": str(program.id), "name": "Plan de bacheo", "count": 1}]
    assert summary["by_sdg"] == [{"sdg": 3, "count": 1}, {"sdg": 11, "count": 2}]


def test_summary_respects_filters(client, plan):
    municipality, term = plan["municipality"], plan["term"]
    other_axis = make_axis(municipality, term, "Ciudad segura")
    _project(plan, name="Uno", year=2023, priority="A+")
    make_project(
        municipality, term, other_axis, plan["department"], name="Dos", year=2024, priority="C"
    )

    def active(**params):
        return _summary(client, plan, **params)["active_count"]

    assert active() == 2
    assert active(year=2024) == 1
    assert active(axis_id=str(other_axis.id)) == 1
    assert active(priority="A+") == 1
    assert active(department_id=str(plan["department"].id)) == 2
    assert active(year=2026) == 0


def test_summary_excludes_other_municipalities(client, plan):
    other = make_municipality("Saira")
    other_term = make_term(other)
    make_project(other, other_term, make_axis(other, other_term), make_department(other))
    _project(plan)

    assert _summary(client, plan)["active_count"] == 1
    assert client.get(f"{BASE}/summary", params={"term_id": str(other_term.id)}).status_code == 404
