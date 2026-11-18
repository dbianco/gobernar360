import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from gobernar360.platform.clock import get_today
from tests.factories import login
from tests.projects.factories import (
    make_axis,
    make_department,
    make_indicator,
    make_objective,
    make_project,
    make_term,
    projects_member,
)

BASE = "/api/dashboards/projects"
BOM = "﻿"


@pytest.fixture
def plan(client):
    client.app.dependency_overrides[get_today] = lambda: date(2025, 6, 15)
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


def _rows(response) -> list[dict[str, str]]:
    text = response.content.decode("utf-8")
    assert text.startswith(BOM)
    return list(csv.DictReader(io.StringIO(text.removeprefix(BOM))))


def test_projects_csv_has_header_bom_and_one_row_per_project(client, plan):
    _project(
        plan,
        name="Cloacas",
        status="in_progress",
        end_date=date(2025, 6, 1),
        planned_budget=Decimal("1500.5"),
        sdgs=[6, 11],
        year=2024,
        priority="A+",
    )
    _project(plan, name="Alumbrado")

    response = client.get(f"{BASE}/export/projects.csv")
    rows = _rows(response)

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert 'attachment; filename="projects.csv"' in response.headers["content-disposition"]
    assert list(rows[0]) == [
        "name",
        "term",
        "year",
        "axis",
        "objective",
        "department",
        "owner",
        "program",
        "priority",
        "status",
        "progress",
        "planned_budget",
        "executed_budget",
        "start_date",
        "end_date",
        "sdgs",
    ]
    assert [row["name"] for row in rows] == ["Alumbrado", "Cloacas"]
    assert (rows[1]["status"], rows[1]["planned_budget"], rows[1]["sdgs"], rows[1]["end_date"]) == (
        "delayed",
        "1500.50",
        "6;11",
        "2025-06-01",
    )
    assert (rows[1]["term"], rows[1]["axis"], rows[1]["owner"]) == (
        "Gestión 2023-2027",
        "Ciudad inclusiva",
        "",
    )


def test_projects_csv_respects_filters(client, plan):
    _project(plan, name="Uno", year=2023)
    _project(plan, name="Dos", year=2024)

    rows = _rows(client.get(f"{BASE}/export/projects.csv", params={"year": 2024}))

    assert [row["name"] for row in rows] == ["Dos"]


def test_csv_preserves_accented_characters(client, plan):
    _project(plan, name="Pavimentación Año 1")

    rows = _rows(client.get(f"{BASE}/export/projects.csv"))

    assert rows[0]["name"] == "Pavimentación Año 1"
    assert rows[0]["department"] == "Obras Públicas"


def test_csv_neutralises_formula_cells(client, plan):
    _project(plan, name="=SUM(A1)")
    _project(plan, name="@cmd")

    rows = _rows(client.get(f"{BASE}/export/projects.csv"))

    assert sorted(row["name"] for row in rows) == ["'=SUM(A1)", "'@cmd"]


def test_indicators_csv_lists_indicators(client, plan):
    objective = make_objective(plan["municipality"], plan["axis"])
    make_indicator(
        plan["municipality"],
        objective,
        unit="cuadras",
        baseline=Decimal("120"),
        target=Decimal("200"),
    )

    rows = _rows(client.get(f"{BASE}/export/indicators.csv"))

    assert rows == [
        {
            "name": "Cuadras pavimentadas",
            "axis": "Ciudad inclusiva",
            "objective": "Reducir el déficit habitacional",
            "unit": "cuadras",
            "baseline": "120",
            "target": "200",
            "current_value": "",
        }
    ]


def test_export_requires_dashboard_access(client):
    projects_member(None)
    login(client, "ana@noetinger.test")

    assert client.get(f"{BASE}/export/projects.csv").status_code == 403
