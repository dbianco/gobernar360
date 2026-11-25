import csv
import io
from datetime import date
from decimal import Decimal

import pytest

from gobernar360.dashboards.projects.models import Indicator
from gobernar360.platform.clock import get_today
from tests.factories import admin_session, login
from tests.projects.factories import (
    make_axis,
    make_department,
    make_indicator,
    make_objective,
    make_owner,
    make_program,
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
        "zones",
        "latitude",
        "longitude",
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


def _in_full(plan, name, **fields):
    """A project with every optional part, in the catalogs of its own."""
    municipality = plan["municipality"]
    axis = make_axis(municipality, plan["term"], f"Eje {name}")
    return make_project(
        municipality,
        plan["term"],
        axis,
        make_department(municipality, f"Área {name}"),
        name=name,
        objective_id=make_objective(municipality, axis, f"Objetivo {name}").id,
        owner_id=make_owner(municipality, f"Responsable {name}").id,
        program_id=make_program(municipality, f"Programa {name}").id,
        **fields,
    )


def test_projects_csv_has_every_value_in_its_column(client, plan):
    _in_full(
        plan,
        "Plaza",
        sdgs=[11, 6],
        year=2024,
        priority="B",
        status="in_progress",
        manual_progress=30,
        start_date=date(2024, 2, 3),
        end_date=date(2099, 4, 5),
        planned_budget=Decimal("10"),
        executed_budget=Decimal("2.5"),
    )
    _project(plan, name="Sin nada", year=2023)

    full, bare = _rows(client.get(f"{BASE}/export/projects.csv"))

    assert full == {
        "name": "Plaza",
        "term": "Gestión 2023-2027",
        "year": "2024",
        "axis": "Eje Plaza",
        "objective": "Objetivo Plaza",
        "department": "Área Plaza",
        "owner": "Responsable Plaza",
        "program": "Programa Plaza",
        "priority": "B",
        "status": "in_progress",
        "progress": "30",
        "planned_budget": "10.00",
        "executed_budget": "2.50",
        "start_date": "2024-02-03",
        "end_date": "2099-04-05",
        "sdgs": "6;11",
        "zones": "",
        "latitude": "",
        "longitude": "",
    }
    empty = ("objective", "owner", "program", "start_date", "end_date", "sdgs")
    assert [bare[column] for column in empty] == [""] * len(empty)


def test_projects_csv_takes_every_filter_of_the_list(client, plan):
    one = _in_full(plan, "Uno", year=2023, priority="A", status="in_progress")
    _in_full(plan, "Dos", year=2024, priority="C", status="finished")
    old = make_term(plan["municipality"], "Vieja", 2015, 2019)
    make_project(
        plan["municipality"],
        old,
        make_axis(plan["municipality"], old, "Viejo"),
        plan["department"],
        name="Viejo",
        priority="B",
        year=2015,
        status="in_progress",
        end_date=date(2016, 1, 1),
    )

    def names(**params):
        rows = _rows(client.get(f"{BASE}/export/projects.csv", params=params))
        return [row["name"] for row in rows]

    assert names() == ["Dos", "Uno", "Viejo"]
    assert names(term_id=str(plan["term"].id)) == ["Dos", "Uno"]
    assert names(year=2023) == ["Uno"]
    assert names(axis_id=str(one.axis_id)) == ["Uno"]
    assert names(department_id=str(one.department_id)) == ["Uno"]
    assert names(owner_id=str(one.owner_id)) == ["Uno"]
    assert names(priority="A") == ["Uno"]
    assert names(status="finished") == ["Dos"]
    # Worked out from its dates, so it depends on the day.
    assert names(status="delayed") == ["Viejo"]


def test_indicators_csv_has_every_value_and_takes_the_filters(client, plan):
    municipality = plan["municipality"]
    old = make_term(municipality, "Vieja", 2015, 2019)
    objectives = {
        name: make_objective(municipality, axis, name)
        for name, axis in (
            ("Uno", plan["axis"]),
            ("Dos", plan["axis"]),
            ("Tres", make_axis(municipality, old, "Viejo")),
        )
    }
    with admin_session() as session, session.begin():
        for name, objective in objectives.items():
            session.add(
                Indicator(
                    municipality_id=municipality.id,
                    objective_id=objective.id,
                    name=f"Indicador {name}",
                    unit="u",
                    baseline=Decimal("1.50"),
                    target=Decimal("20"),
                    current_value=Decimal("7.25"),
                )
            )

    def names(**params):
        rows = _rows(client.get(f"{BASE}/export/indicators.csv", params=params))
        return sorted(row["objective"] for row in rows)

    response = client.get(
        f"{BASE}/export/indicators.csv", params={"objective_id": str(objectives["Uno"].id)}
    )
    assert 'filename="indicators.csv"' in response.headers["content-disposition"]
    assert _rows(response) == [
        {
            "name": "Indicador Uno",
            "axis": plan["axis"].name,
            "objective": "Uno",
            "unit": "u",
            "baseline": "1.5",
            "target": "20",
            "current_value": "7.25",
        }
    ]
    assert names() == ["Dos", "Tres", "Uno"]
    assert names(term_id=str(plan["term"].id)) == ["Dos", "Uno"]
    assert names(term_id=str(old.id)) == ["Tres"]
