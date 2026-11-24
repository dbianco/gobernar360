"""CSV downloads: the cases of a period and the per-area report.

Both take the same period as the summary (by date received), so a spreadsheet over the
cases file reproduces the summary's figures: the median of `resolution_business_days`
per type is the summary's median for that type.
"""

from fastapi import APIRouter, Response
from sqlalchemy import select

from gobernar360.dashboards.complaints.access import Viewer
from gobernar360.dashboards.complaints.clock import AT_RISK, ON_TIME, OVERDUE
from gobernar360.dashboards.complaints.models import Area
from gobernar360.dashboards.complaints.summary import (
    PeriodParams,
    load_cases,
    received_in,
    resolution_of,
)
from gobernar360.platform.clock import Today
from gobernar360.platform.csv_export import csv_response, safe_text

router = APIRouter()

CASE_COLUMNS = (
    "number",
    "received_on",
    "type",
    "area",
    "zone",
    "address",
    "state",
    "complainant",
    "target_business_days",
    "business_days_used",
    "business_days_left",
    "deadline",
    "clock_status",
    "resolved_on",
    "resolution_business_days",
    "resolved_on_time",
)
AREA_COLUMNS = (
    "area",
    "received",
    "resolved",
    "resolved_on_time",
    "on_time_percent",
    "median_resolution_business_days",
    "p90_resolution_business_days",
    "open_today",
    "at_risk_today",
    "overdue_today",
)


def _blank(value: object) -> object:
    return "" if value is None else value


def _days(value: float | None) -> str:
    """4.0 -> "4", 8.8 -> "8.8"."""
    return "" if value is None else f"{value:.1f}".removesuffix(".0")


def _percent(value: float | None) -> str:
    return "" if value is None else f"{value * 100:.1f}"


@router.get("/export/complaints.csv")
def export_complaints(ctx: Viewer, today: Today, window: PeriodParams) -> Response:
    """One row per complaint received in the period, oldest first."""
    rows = []
    for case in received_in(load_cases(ctx, today), window):
        complaint, reading = case.complaint, case.reading
        person = complaint.person
        rows.append(
            (
                complaint.number,
                case.received_on.isoformat(),
                safe_text(complaint.type.name),
                safe_text(complaint.area.name),
                safe_text(complaint.zone.name),
                safe_text(complaint.address),
                complaint.state,
                safe_text(person.full_name if person else ""),
                reading.target_days,
                reading.used_days,
                reading.left_days if case.open else "",
                reading.deadline.isoformat() if case.open or case.solved else "",
                _blank(reading.status),
                reading.resolved_on.isoformat() if reading.resolved_on else "",
                reading.used_days if case.solved else "",
                ("yes" if reading.status == ON_TIME else "no") if case.solved else "",
            )
        )
    return csv_response("complaints.csv", CASE_COLUMNS, rows)


@router.get("/export/areas.csv")
def export_areas(ctx: Viewer, today: Today, window: PeriodParams) -> Response:
    """Per area: how the period's complaints were solved and what it holds open today."""
    cases = load_cases(ctx, today)
    period = received_in(cases, window)
    rows = []
    for area in ctx.db.scalars(select(Area).order_by(Area.name, Area.id)):
        solved = resolution_of([case for case in period if case.complaint.area_id == area.id])
        backlog = [case for case in cases if case.open and case.complaint.area_id == area.id]
        rows.append(
            (
                safe_text(area.name),
                solved.received,
                solved.resolved,
                solved.on_time,
                _percent(solved.on_time_ratio),
                _days(solved.median_days),
                _days(solved.p90_days),
                len(backlog),
                sum(case.reading.status == AT_RISK for case in backlog),
                sum(case.reading.status == OVERDUE for case in backlog),
            )
        )
    return csv_response("complaints-areas.csv", AREA_COLUMNS, rows)
