"""CSV downloads of projects and indicators."""

import uuid

from fastapi import APIRouter, Response

from gobernar360.dashboards.projects.access import Viewer
from gobernar360.dashboards.projects.projects_router import (
    project_effective_status,
    project_progress,
    query_indicators,
    query_projects,
)
from gobernar360.dashboards.projects.schemas import EffectiveStatus, Priority
from gobernar360.platform.clock import Today
from gobernar360.platform.csv_export import csv_response, plain_number, safe_text

router = APIRouter()

PROJECT_COLUMNS = (
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
)
INDICATOR_COLUMNS = ("name", "axis", "objective", "unit", "baseline", "target", "current_value")


@router.get("/export/projects.csv")
def export_projects(
    ctx: Viewer,
    today: Today,
    term_id: uuid.UUID | None = None,
    year: int | None = None,
    axis_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    priority: Priority | None = None,
    status: EffectiveStatus | None = None,
) -> Response:
    projects = query_projects(
        ctx, today, term_id, year, axis_id, department_id, owner_id, priority, status
    )
    rows = (
        (
            safe_text(p.name),
            safe_text(p.term.name),
            p.year,
            safe_text(p.axis.name),
            safe_text(p.objective.name if p.objective else ""),
            safe_text(p.department.name),
            safe_text(p.owner.full_name if p.owner else ""),
            safe_text(p.program.name if p.program else ""),
            p.priority,
            project_effective_status(p, today),
            project_progress(p),
            f"{p.planned_budget:.2f}",
            f"{p.executed_budget:.2f}",
            p.start_date or "",
            p.end_date or "",
            ";".join(str(number) for number in sorted(sdg.sdg_number for sdg in p.sdgs)),
        )
        for p in projects
    )
    return csv_response("projects.csv", PROJECT_COLUMNS, rows)


@router.get("/export/indicators.csv")
def export_indicators(
    ctx: Viewer, term_id: uuid.UUID | None = None, objective_id: uuid.UUID | None = None
) -> Response:
    rows = (
        (
            safe_text(i.name),
            safe_text(i.objective.axis.name),
            safe_text(i.objective.name),
            safe_text(i.unit),
            plain_number(i.baseline),
            plain_number(i.target),
            plain_number(i.current_value),
        )
        for i in query_indicators(ctx, term_id, objective_id)
    )
    return csv_response("indicators.csv", INDICATOR_COLUMNS, rows)
