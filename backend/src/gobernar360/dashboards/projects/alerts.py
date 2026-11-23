"""Email alerts of the projects dashboard: milestones past their due date."""

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.config import get_settings
from gobernar360.dashboards.projects.models import Milestone, Project
from gobernar360.dashboards.projects.rules import FINISHED, MilestoneState, milestone_in_alert
from gobernar360.dashboards.registry import Alert
from gobernar360.platform.texts import format_date

MILESTONE_OVERDUE = "milestone_overdue"


def get_alerts(db: Session, today: date) -> list[Alert]:
    """One alert per milestone in alert, the same ones the project page flags."""
    rows = db.execute(
        select(Milestone, Project)
        .join(Project, Milestone.project_id == Project.id)
        .where(Milestone.completed_on.is_(None), Project.status != FINISHED)
        .order_by(Milestone.due_date, Project.name, Milestone.name)
    ).all()
    settings = get_settings()
    return [
        Alert(
            kind=MILESTONE_OVERDUE,
            # A new due date that passes again is a new event.
            event_key=f"{milestone.id}:{milestone.due_date.isoformat()}",
            params={
                "project": project.name,
                "milestone": milestone.name,
                "due_date": format_date(milestone.due_date),
                "link": settings.app_link(f"/d/projects/projects/{project.id}"),
            },
        )
        for milestone, project in rows
        if milestone_in_alert(MilestoneState(milestone.due_date, milestone.completed_on), today)
    ]
