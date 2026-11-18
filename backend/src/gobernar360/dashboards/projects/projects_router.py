"""Projects, their milestones, and strategic indicators.

Reading needs viewer access; loading data needs editor access.
"""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter
from sqlalchemy import select

from gobernar360.core.errors import invalid_reference, validation_error
from gobernar360.dashboards.projects.access import Editor, Viewer
from gobernar360.dashboards.projects.models import (
    Axis,
    Department,
    Indicator,
    Milestone,
    Objective,
    Owner,
    Program,
    Project,
    ProjectSdg,
    Term,
)
from gobernar360.dashboards.projects.rules import (
    FINISHED,
    MilestoneState,
    effective_status,
    milestone_in_alert,
    progress_percent,
)
from gobernar360.dashboards.projects.schemas import (
    EffectiveStatus,
    IndicatorIn,
    IndicatorOut,
    IndicatorPatch,
    MilestoneIn,
    MilestoneOut,
    MilestonePatch,
    NamedRef,
    OwnerRef,
    Priority,
    ProjectIn,
    ProjectOut,
    ProjectPatch,
)
from gobernar360.dashboards.projects.sdgs import SDG_NUMBERS
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import Today
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


def milestone_states(project: Project) -> list[MilestoneState]:
    return [MilestoneState(m.due_date, m.completed_on) for m in project.milestones]


def project_effective_status(project: Project, today: date) -> str:
    return effective_status(project.status, project.end_date, milestone_states(project), today)


def project_progress(project: Project) -> int:
    return progress_percent(project.status, milestone_states(project), project.manual_progress)


def _milestone_out(milestone: Milestone, project: Project, today: date) -> MilestoneOut:
    state = MilestoneState(milestone.due_date, milestone.completed_on)
    return MilestoneOut(
        id=milestone.id,
        name=milestone.name,
        due_date=milestone.due_date,
        completed_on=milestone.completed_on,
        # A finished project no longer raises alerts for milestones left open.
        in_alert=project.status != FINISHED and milestone_in_alert(state, today),
    )


def _ref(entity: Any) -> NamedRef | None:
    return NamedRef.model_validate(entity) if entity is not None else None


def project_out(project: Project, today: date) -> ProjectOut:
    return ProjectOut(
        id=project.id,
        term_id=project.term_id,
        name=project.name,
        description=project.description,
        axis=_ref(project.axis),
        objective=_ref(project.objective),
        department=_ref(project.department),
        owner=OwnerRef.model_validate(project.owner) if project.owner else None,
        program=_ref(project.program),
        priority=project.priority,
        year=project.year,
        start_date=project.start_date,
        end_date=project.end_date,
        planned_budget=project.planned_budget,
        executed_budget=project.executed_budget,
        status=project.status,
        effective_status=project_effective_status(project, today),
        progress=project_progress(project),
        manual_progress=project.manual_progress,
        sdgs=sorted(sdg.sdg_number for sdg in project.sdgs),
        milestones=[_milestone_out(m, project, today) for m in project.milestones],
    )


def _validate_project(ctx: RequestContext, fields: dict[str, Any]) -> None:
    """Check a project's complete set of fields, whether new or after applying a patch."""
    term = resolve(ctx, Term, fields["term_id"], "term_id")
    axis = resolve(ctx, Axis, fields["axis_id"], "axis_id")
    if axis.term_id != term.id:
        raise invalid_reference("axis_id does not belong to the project's term.")
    if fields.get("objective_id") is not None:
        objective = resolve(ctx, Objective, fields["objective_id"], "objective_id")
        if objective.axis_id != axis.id:
            raise invalid_reference("objective_id does not belong to the project's axis.")
    resolve(ctx, Department, fields["department_id"], "department_id")
    if fields.get("owner_id") is not None:
        resolve(ctx, Owner, fields["owner_id"], "owner_id")
    if fields.get("program_id") is not None:
        resolve(ctx, Program, fields["program_id"], "program_id")
    if not term.start_year <= fields["year"] <= term.end_year:
        raise validation_error("year must be within the term.")
    start_date, end_date = fields.get("start_date"), fields.get("end_date")
    if start_date and end_date and end_date < start_date:
        raise validation_error("end_date must not be before start_date.")


def _set_sdgs(ctx: RequestContext, project: Project, numbers: list[int]) -> None:
    wanted = set(numbers)
    project.sdgs = [sdg for sdg in project.sdgs if sdg.sdg_number in wanted] + [
        ProjectSdg(municipality_id=ctx.municipality_id, sdg_number=number)
        for number in sorted(wanted - {sdg.sdg_number for sdg in project.sdgs})
    ]


PROJECT_COLUMNS = (
    "term_id",
    "axis_id",
    "objective_id",
    "department_id",
    "owner_id",
    "program_id",
    "year",
    "start_date",
    "end_date",
)


def query_projects(
    ctx: RequestContext,
    today: date,
    term_id: uuid.UUID | None = None,
    year: int | None = None,
    axis_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    priority: str | None = None,
    status: str | None = None,
) -> list[Project]:
    """Projects matching the filters, ordered by name. `status` is the effective status."""
    query = select(Project).order_by(Project.name)
    filters = {
        Project.term_id: term_id,
        Project.year: year,
        Project.axis_id: axis_id,
        Project.department_id: department_id,
        Project.owner_id: owner_id,
        Project.priority: priority,
    }
    for column, value in filters.items():
        if value is not None:
            query = query.where(column == value)
    projects = ctx.db.scalars(query).unique().all()
    if status is not None:
        projects = [p for p in projects if project_effective_status(p, today) == status]
    return list(projects)


@router.get("/sdgs")
def list_sdgs(ctx: Viewer) -> list[int]:
    return list(SDG_NUMBERS)


@router.get("/projects")
def list_projects(
    ctx: Viewer,
    today: Today,
    term_id: uuid.UUID | None = None,
    year: int | None = None,
    axis_id: uuid.UUID | None = None,
    department_id: uuid.UUID | None = None,
    owner_id: uuid.UUID | None = None,
    priority: Priority | None = None,
    status: EffectiveStatus | None = None,
) -> list[ProjectOut]:
    projects = query_projects(
        ctx, today, term_id, year, axis_id, department_id, owner_id, priority, status
    )
    return [project_out(project, today) for project in projects]


@router.post("/projects", status_code=201)
def create_project(payload: ProjectIn, ctx: Editor, today: Today) -> ProjectOut:
    fields = payload.model_dump(exclude={"sdgs"})
    _validate_project(ctx, fields)
    project = Project(**fields)
    _set_sdgs(ctx, project, payload.sdgs)
    create_entity(ctx, project, payload.model_dump())
    ctx.db.refresh(project)
    return project_out(project, today)


@router.get("/projects/{project_id}")
def get_project(project_id: uuid.UUID, ctx: Viewer, today: Today) -> ProjectOut:
    return project_out(get_or_404(ctx, Project, project_id), today)


@router.patch("/projects/{project_id}")
def update_project(
    project_id: uuid.UUID, payload: ProjectPatch, ctx: Editor, today: Today
) -> ProjectOut:
    project = get_or_404(ctx, Project, project_id)
    changes = payload.model_dump(exclude_unset=True)
    sdgs = changes.pop("sdgs", None)
    merged = {column: getattr(project, column) for column in PROJECT_COLUMNS} | changes
    _validate_project(ctx, merged)
    if sdgs is not None:
        _set_sdgs(ctx, project, sdgs)
    update_entity(ctx, project, changes)
    ctx.db.refresh(project)
    return project_out(project, today)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, get_or_404(ctx, Project, project_id))


@router.post("/projects/{project_id}/milestones", status_code=201)
def create_milestone(
    project_id: uuid.UUID, payload: MilestoneIn, ctx: Editor, today: Today
) -> MilestoneOut:
    project = get_or_404(ctx, Project, project_id)
    milestone = Milestone(project_id=project_id, **payload.model_dump())
    return _milestone_out(create_entity(ctx, milestone, payload.model_dump()), project, today)


@router.patch("/milestones/{milestone_id}")
def update_milestone(
    milestone_id: uuid.UUID, payload: MilestonePatch, ctx: Editor, today: Today
) -> MilestoneOut:
    milestone = get_or_404(ctx, Milestone, milestone_id)
    changes = payload.model_dump(exclude_unset=True)
    project = get_or_404(ctx, Project, milestone.project_id)
    return _milestone_out(update_entity(ctx, milestone, changes), project, today)


@router.delete("/milestones/{milestone_id}", status_code=204)
def delete_milestone(milestone_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, get_or_404(ctx, Milestone, milestone_id))


def query_indicators(
    ctx: RequestContext, term_id: uuid.UUID | None = None, objective_id: uuid.UUID | None = None
) -> list[Indicator]:
    query = (
        select(Indicator)
        .join(Objective, Indicator.objective_id == Objective.id)
        .join(Axis, Objective.axis_id == Axis.id)
        .order_by(Axis.name, Objective.name, Indicator.name)
    )
    if term_id is not None:
        query = query.where(Axis.term_id == term_id)
    if objective_id is not None:
        query = query.where(Indicator.objective_id == objective_id)
    return list(ctx.db.scalars(query).unique())


def _indicator_out(indicator: Indicator) -> IndicatorOut:
    return IndicatorOut(
        id=indicator.id,
        name=indicator.name,
        unit=indicator.unit,
        baseline=indicator.baseline,
        target=indicator.target,
        current_value=indicator.current_value,
        objective=_ref(indicator.objective),
        axis=_ref(indicator.objective.axis),
    )


@router.get("/indicators")
def list_indicators(
    ctx: Viewer, term_id: uuid.UUID | None = None, objective_id: uuid.UUID | None = None
) -> list[IndicatorOut]:
    return [_indicator_out(indicator) for indicator in query_indicators(ctx, term_id, objective_id)]


@router.post("/indicators", status_code=201)
def create_indicator(payload: IndicatorIn, ctx: Editor) -> IndicatorOut:
    resolve(ctx, Objective, payload.objective_id, "objective_id")
    indicator = create_entity(ctx, Indicator(**payload.model_dump()), payload.model_dump())
    ctx.db.refresh(indicator)
    return _indicator_out(indicator)


@router.patch("/indicators/{indicator_id}")
def update_indicator(indicator_id: uuid.UUID, payload: IndicatorPatch, ctx: Editor) -> IndicatorOut:
    indicator = get_or_404(ctx, Indicator, indicator_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("objective_id") is not None:
        resolve(ctx, Objective, changes["objective_id"], "objective_id")
    update_entity(ctx, indicator, changes)
    ctx.db.refresh(indicator)
    return _indicator_out(indicator)


@router.delete("/indicators/{indicator_id}", status_code=204)
def delete_indicator(indicator_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, get_or_404(ctx, Indicator, indicator_id))
