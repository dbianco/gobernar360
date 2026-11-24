"""What the projects dashboard adds to a month's report: milestones reached and overdue."""

from datetime import date

from sqlalchemy import select

from gobernar360.dashboards.projects.models import Milestone, Project
from gobernar360.dashboards.projects.rules import FINISHED
from gobernar360.dashboards.registry import ReportColumn, ReportTable
from gobernar360.platform.access import RequestContext


def report_tables(ctx: RequestContext, first: date, last: date) -> list[ReportTable]:
    """Milestones completed within the month, and those due within it still open at its end.

    Only project and milestone names and dates: owners are people and stay out.
    """
    rows = ctx.db.execute(
        select(
            Project.name,
            Project.status,
            Milestone.name,
            Milestone.due_date,
            Milestone.completed_on,
        ).join(Project, Milestone.project_id == Project.id)
    ).all()
    reached = sorted(
        (row for row in rows if row.completed_on and first <= row.completed_on <= last),
        key=lambda row: (row.completed_on, row[0], row[2]),
    )
    overdue = sorted(
        (
            row
            for row in rows
            if first <= row.due_date <= last
            and (row.completed_on is None or row.completed_on > last)
            # A finished project no longer raises alerts for milestones left open.
            and row.status != FINISHED
        ),
        key=lambda row: (row.due_date, row[0], row[2]),
    )
    return [
        ReportTable(
            key="projects.milestones_reached",
            title="Hitos alcanzados en el mes",
            columns=(
                ReportColumn("Proyecto"),
                ReportColumn("Hito"),
                ReportColumn("Fecha comprometida", "date"),
                ReportColumn("Alcanzado el", "date"),
            ),
            rows=[
                (project, name, due.isoformat(), done.isoformat())
                for project, _, name, due, done in reached
            ],
        ),
        ReportTable(
            key="projects.milestones_overdue",
            title="Hitos vencidos en el mes",
            columns=(
                ReportColumn("Proyecto"),
                ReportColumn("Hito"),
                ReportColumn("Fecha comprometida", "date"),
                ReportColumn("Días de atraso al cierre", "number"),
            ),
            rows=[
                (project, name, due.isoformat(), (last - due).days)
                for project, _, name, due, _ in overdue
            ],
        ),
    ]
