"""Headline numbers of the projects dashboard."""

import uuid
from collections import Counter
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import func, select

from gobernar360.dashboards.projects.access import Viewer
from gobernar360.dashboards.projects.models import AnnualBudget, Project, Term
from gobernar360.dashboards.projects.projects_router import (
    milestone_states,
    project_effective_status,
    project_progress,
    query_projects,
)
from gobernar360.dashboards.projects.rules import (
    DELAYED,
    EFFECTIVE_STATUSES,
    FINISHED,
    milestone_in_alert,
)
from gobernar360.dashboards.projects.schemas import Money, Priority
from gobernar360.dashboards.registry import IndicatorDefinition, SummaryIndicator
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import Today
from gobernar360.platform.tenant_crud import get_or_404

router = APIRouter()

# None can be rebuilt for a past month: a project's status, milestones and amounts are
# stored as they are today, with no record of when they changed.
INDICATORS = (
    IndicatorDefinition("projects.active", name="Proyectos activos", aggregate=True),
    IndicatorDefinition("projects.finished", name="Proyectos finalizados", aggregate=True),
    IndicatorDefinition(
        "projects.delayed", higher_is_better=False, name="Proyectos retrasados", aggregate=True
    ),
    IndicatorDefinition(
        "projects.average_progress", "percent", name="Avance promedio", aggregate=True
    ),
    IndicatorDefinition(
        "projects.milestones_in_alert",
        higher_is_better=False,
        name="Hitos en alerta",
        aggregate=True,
    ),
    IndicatorDefinition(
        "projects.budget_executed_ratio", "ratio", name="Presupuesto ejecutado", aggregate=True
    ),
)


class BudgetSummary(BaseModel):
    total: Money | None
    planned: Money
    executed: Money
    # Share of the total budget that is planned in projects.
    planned_ratio: float | None
    # Share of the planned budget that has been executed.
    executed_ratio: float | None


class MilestoneSummary(BaseModel):
    total: int
    completed: int
    in_alert: int


class GroupCount(BaseModel):
    id: uuid.UUID
    name: str
    count: int


class SdgCount(BaseModel):
    sdg: int
    count: int


class SummaryOut(BaseModel):
    status_counts: dict[str, int]
    active_count: int
    finished_count: int
    average_progress: int
    budget: BudgetSummary
    milestones: MilestoneSummary
    by_department: list[GroupCount]
    by_owner: list[GroupCount]
    by_program: list[GroupCount]
    by_sdg: list[SdgCount]


def _ratio(numerator: Decimal, denominator: Decimal | None) -> float | None:
    if not denominator:
        return None
    return round(float(numerator / denominator), 4)


def _group(entities: list[Any], name_attribute: str = "name") -> list[GroupCount]:
    counts = Counter(entity.id for entity in entities)
    names = {entity.id: getattr(entity, name_attribute) for entity in entities}
    groups = [GroupCount(id=key, name=names[key], count=count) for key, count in counts.items()]
    return sorted(groups, key=lambda group: (-group.count, group.name))


def compute_summary(
    projects: Sequence[Project], total_budget: Decimal | None, today: date
) -> SummaryOut:
    """Aggregate already-loaded projects. Touches no database."""
    status_counts = dict.fromkeys(EFFECTIVE_STATUSES, 0)
    for project in projects:
        status_counts[project_effective_status(project, today)] += 1

    planned = sum((p.planned_budget for p in projects), Decimal("0"))
    executed = sum((p.executed_budget for p in projects), Decimal("0"))

    milestones_total = milestones_completed = milestones_in_alert = 0
    for project in projects:
        for state in milestone_states(project):
            milestones_total += 1
            milestones_completed += state.completed_on is not None
            # A finished project no longer raises alerts for milestones left open.
            milestones_in_alert += project.status != FINISHED and milestone_in_alert(state, today)

    finished_count = status_counts[FINISHED]
    progress_values = [project_progress(project) for project in projects]
    sdg_counts = Counter(sdg.sdg_number for project in projects for sdg in project.sdgs)

    return SummaryOut(
        status_counts=status_counts,
        active_count=len(projects) - finished_count,
        finished_count=finished_count,
        average_progress=round(sum(progress_values) / len(projects)) if projects else 0,
        budget=BudgetSummary(
            total=total_budget,
            planned=planned,
            executed=executed,
            planned_ratio=_ratio(planned, total_budget),
            executed_ratio=_ratio(executed, planned),
        ),
        milestones=MilestoneSummary(
            total=milestones_total, completed=milestones_completed, in_alert=milestones_in_alert
        ),
        by_department=_group([p.department for p in projects]),
        by_owner=_group([p.owner for p in projects if p.owner], "full_name"),
        by_program=_group([p.program for p in projects if p.program]),
        by_sdg=[SdgCount(sdg=number, count=count) for number, count in sorted(sdg_counts.items())],
    )


def _total_budget(ctx: RequestContext, term_id: uuid.UUID, year: int | None) -> Decimal | None:
    """Sum of the annual budgets loaded for the term; None when none has been loaded."""
    query = select(func.sum(AnnualBudget.total_amount)).where(AnnualBudget.term_id == term_id)
    if year is not None:
        query = query.where(AnnualBudget.year == year)
    return ctx.db.scalar(query)


@router.get("/summary")
def get_term_summary(
    ctx: Viewer,
    today: Today,
    term_id: uuid.UUID,
    year: int | None = None,
    axis_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    priority: Priority | None = None,
) -> SummaryOut:
    get_or_404(ctx, Term, term_id)
    projects = query_projects(ctx, today, term_id, year, axis_id, department_id, owner_id, priority)
    return compute_summary(projects, _total_budget(ctx, term_id, year), today)


def get_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    """Indicators for the general overview, taken from the most recent term."""
    term = ctx.db.scalars(select(Term).order_by(Term.start_year.desc(), Term.name).limit(1)).first()
    if term is None:
        return []
    projects = query_projects(ctx, today, term_id=term.id)
    summary = compute_summary(projects, _total_budget(ctx, term.id, None), today)
    return [
        SummaryIndicator("projects.active", summary.active_count),
        SummaryIndicator("projects.finished", summary.finished_count),
        SummaryIndicator("projects.delayed", summary.status_counts[DELAYED]),
        SummaryIndicator("projects.average_progress", summary.average_progress, "percent"),
        SummaryIndicator("projects.milestones_in_alert", summary.milestones.in_alert),
        SummaryIndicator("projects.budget_executed_ratio", summary.budget.executed_ratio, "ratio"),
    ]
