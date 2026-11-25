"""Projects on the map: works at a point or along a street."""

import uuid
from datetime import date

from pydantic import BaseModel
from sqlalchemy import ColumnElement, func, select

from gobernar360.dashboards.projects.models import Project, Term
from gobernar360.dashboards.projects.projects_router import query_projects
from gobernar360.dashboards.projects.rules import FINISHED
from gobernar360.dashboards.projects.schemas import EffectiveStatus, Priority
from gobernar360.platform.access import RequestContext
from gobernar360.platform.geo.aggregates import MONEY
from gobernar360.platform.geo.contract import LocatedRecord, ZoneMetric
from gobernar360.platform.listing import SearchText, every_word


class ProjectFilters(BaseModel):
    """The filters of the project list."""

    term_id: uuid.UUID | None = None
    year: int | None = None
    axis_id: uuid.UUID | None = None
    department_id: uuid.UUID | None = None
    owner_id: uuid.UUID | None = None
    priority: Priority | None = None
    status: EffectiveStatus | None = None
    q: SearchText = None


def _conditions(
    ctx: RequestContext, today: date, filters: ProjectFilters
) -> list[ColumnElement[bool]]:
    chosen = filters.model_dump(exclude={"q"}, exclude_none=True)
    conditions = every_word(filters.q, Project.name)
    if chosen:
        # The effective status is worked out from dates and milestones, not stored.
        projects = query_projects(ctx, today, **chosen)
        conditions.append(Project.id.in_([project.id for project in projects]))
    return conditions


def _latest_term(ctx: RequestContext, today: date) -> ProjectFilters:
    """The overview shows the most recent term, as the dashboard's indicators do."""
    return ProjectFilters(
        term_id=ctx.db.scalar(select(Term.id).order_by(Term.start_year.desc(), Term.name).limit(1))
    )


projects = LocatedRecord(
    key="projects",
    model=Project,
    title=Project.name,
    filters=ProjectFilters,
    conditions=_conditions,
    overview_filters=_latest_term,
    metrics=(
        ZoneMetric(
            "active",
            lambda today, filters: func.count(Project.id).filter(Project.status != FINISHED),
        ),
        ZoneMetric(
            "planned_budget",
            lambda today, filters: func.sum(Project.planned_budget).filter(
                Project.status != FINISHED
            ),
            unit=MONEY,
        ),
        ZoneMetric(
            "executed_budget",
            lambda today, filters: func.sum(Project.executed_budget).filter(
                Project.status != FINISHED
            ),
            unit=MONEY,
        ),
        ZoneMetric("projects", lambda today, filters: func.count(Project.id)),
    ),
)
