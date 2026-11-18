"""CSV downloads of projects and indicators."""

import csv
import io
import uuid
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

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

router = APIRouter()

# Spreadsheets run cells starting with these characters as formulas.
FORMULA_PREFIXES = ("=", "+", "-", "@")

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


def _text(value: Any) -> str:
    """Free text typed by users: neutralise anything a spreadsheet would run as a formula."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def _plain_number(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.normalize(), "f")


def _csv_response(filename: str, header: Iterable[str], rows: Iterable[Iterable[Any]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    # The byte-order mark makes Excel read the file as UTF-8, keeping accents intact.
    return Response(
        content=("﻿" + buffer.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
            _text(p.name),
            _text(p.term.name),
            p.year,
            _text(p.axis.name),
            _text(p.objective.name if p.objective else ""),
            _text(p.department.name),
            _text(p.owner.full_name if p.owner else ""),
            _text(p.program.name if p.program else ""),
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
    return _csv_response("projects.csv", PROJECT_COLUMNS, rows)


@router.get("/export/indicators.csv")
def export_indicators(
    ctx: Viewer, term_id: uuid.UUID | None = None, objective_id: uuid.UUID | None = None
) -> Response:
    rows = (
        (
            _text(i.name),
            _text(i.objective.axis.name),
            _text(i.objective.name),
            _text(i.unit),
            _plain_number(i.baseline),
            _plain_number(i.target),
            _plain_number(i.current_value),
        )
        for i in query_indicators(ctx, term_id, objective_id)
    )
    return _csv_response("indicators.csv", INDICATOR_COLUMNS, rows)
