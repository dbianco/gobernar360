"""Catalogs the municipality maintains itself: terms, axes, objectives, departments,
programs and owners. Reading needs viewer access; changing them needs dashboard admin."""

import uuid

from fastapi import APIRouter
from sqlalchemy import select

from gobernar360.core.errors import validation_error
from gobernar360.dashboards.projects.access import Admin, Viewer
from gobernar360.dashboards.projects.models import (
    AnnualBudget,
    Axis,
    Department,
    Objective,
    Owner,
    Program,
    Term,
)
from gobernar360.dashboards.projects.schemas import (
    AnnualBudgetIn,
    AnnualBudgetOut,
    AxisIn,
    AxisOut,
    NamedRef,
    NameIn,
    NamePatch,
    ObjectiveIn,
    ObjectiveOut,
    OwnerIn,
    OwnerOut,
    TermIn,
    TermOut,
    TermPatch,
)
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    resolve,
    update_entity,
)

router = APIRouter()


# Terms and their annual budgets


@router.get("/terms")
def list_terms(ctx: Viewer) -> list[TermOut]:
    return ctx.db.scalars(select(Term).order_by(Term.start_year.desc(), Term.name)).all()


@router.post("/terms", status_code=201)
def create_term(payload: TermIn, ctx: Admin) -> TermOut:
    return create_entity(ctx, Term(**payload.model_dump()), payload.model_dump())


@router.patch("/terms/{term_id}")
def update_term(term_id: uuid.UUID, payload: TermPatch, ctx: Admin) -> TermOut:
    term = get_or_404(ctx, Term, term_id)
    changes = payload.model_dump(exclude_none=True)
    start_year = changes.get("start_year", term.start_year)
    end_year = changes.get("end_year", term.end_year)
    if end_year < start_year:
        raise validation_error("end_year must not be before start_year.")
    return update_entity(ctx, term, changes)


@router.delete("/terms/{term_id}", status_code=204)
def delete_term(term_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Term, term_id))


@router.get("/terms/{term_id}/budgets")
def list_annual_budgets(term_id: uuid.UUID, ctx: Viewer) -> list[AnnualBudgetOut]:
    get_or_404(ctx, Term, term_id)
    return ctx.db.scalars(
        select(AnnualBudget).where(AnnualBudget.term_id == term_id).order_by(AnnualBudget.year)
    ).all()


@router.put("/terms/{term_id}/budgets")
def set_annual_budget(term_id: uuid.UUID, payload: AnnualBudgetIn, ctx: Admin) -> AnnualBudgetOut:
    term = get_or_404(ctx, Term, term_id)
    if not term.start_year <= payload.year <= term.end_year:
        raise validation_error("year must be within the term.")
    budget = ctx.db.scalar(
        select(AnnualBudget).where(
            AnnualBudget.term_id == term_id, AnnualBudget.year == payload.year
        )
    )
    changes = {"total_amount": payload.total_amount}
    if budget is None:
        return create_entity(
            ctx, AnnualBudget(term_id=term_id, year=payload.year, **changes), payload.model_dump()
        )
    return update_entity(ctx, budget, changes)


# Axes and objectives


@router.get("/axes")
def list_axes(ctx: Viewer, term_id: uuid.UUID | None = None) -> list[AxisOut]:
    query = select(Axis).order_by(Axis.name)
    if term_id is not None:
        query = query.where(Axis.term_id == term_id)
    return ctx.db.scalars(query).all()


@router.post("/axes", status_code=201)
def create_axis(payload: AxisIn, ctx: Admin) -> AxisOut:
    resolve(ctx, Term, payload.term_id, "term_id")
    return create_entity(ctx, Axis(**payload.model_dump()), payload.model_dump())


@router.patch("/axes/{axis_id}")
def update_axis(axis_id: uuid.UUID, payload: NamePatch, ctx: Admin) -> AxisOut:
    return update_entity(ctx, get_or_404(ctx, Axis, axis_id), payload.model_dump())


@router.delete("/axes/{axis_id}", status_code=204)
def delete_axis(axis_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Axis, axis_id))


@router.get("/objectives")
def list_objectives(
    ctx: Viewer, axis_id: uuid.UUID | None = None, term_id: uuid.UUID | None = None
) -> list[ObjectiveOut]:
    query = select(Objective).order_by(Objective.name)
    if axis_id is not None:
        query = query.where(Objective.axis_id == axis_id)
    if term_id is not None:
        query = query.join(Axis, Objective.axis_id == Axis.id).where(Axis.term_id == term_id)
    return ctx.db.scalars(query).all()


@router.post("/objectives", status_code=201)
def create_objective(payload: ObjectiveIn, ctx: Admin) -> ObjectiveOut:
    resolve(ctx, Axis, payload.axis_id, "axis_id")
    return create_entity(ctx, Objective(**payload.model_dump()), payload.model_dump())


@router.patch("/objectives/{objective_id}")
def update_objective(objective_id: uuid.UUID, payload: NamePatch, ctx: Admin) -> ObjectiveOut:
    return update_entity(ctx, get_or_404(ctx, Objective, objective_id), payload.model_dump())


@router.delete("/objectives/{objective_id}", status_code=204)
def delete_objective(objective_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Objective, objective_id))


# Departments, programs and owners


@router.get("/departments")
def list_departments(ctx: Viewer) -> list[NamedRef]:
    return ctx.db.scalars(select(Department).order_by(Department.name)).all()


@router.post("/departments", status_code=201)
def create_department(payload: NameIn, ctx: Admin) -> NamedRef:
    return create_entity(ctx, Department(**payload.model_dump()), payload.model_dump())


@router.patch("/departments/{department_id}")
def update_department(department_id: uuid.UUID, payload: NamePatch, ctx: Admin) -> NamedRef:
    return update_entity(ctx, get_or_404(ctx, Department, department_id), payload.model_dump())


@router.delete("/departments/{department_id}", status_code=204)
def delete_department(department_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Department, department_id))


@router.get("/programs")
def list_programs(ctx: Viewer) -> list[NamedRef]:
    return ctx.db.scalars(select(Program).order_by(Program.name)).all()


@router.post("/programs", status_code=201)
def create_program(payload: NameIn, ctx: Admin) -> NamedRef:
    return create_entity(ctx, Program(**payload.model_dump()), payload.model_dump())


@router.patch("/programs/{program_id}")
def update_program(program_id: uuid.UUID, payload: NamePatch, ctx: Admin) -> NamedRef:
    return update_entity(ctx, get_or_404(ctx, Program, program_id), payload.model_dump())


@router.delete("/programs/{program_id}", status_code=204)
def delete_program(program_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Program, program_id))


@router.get("/owners")
def list_owners(ctx: Viewer) -> list[OwnerOut]:
    return ctx.db.scalars(select(Owner).order_by(Owner.full_name)).all()


@router.post("/owners", status_code=201)
def create_owner(payload: OwnerIn, ctx: Admin) -> OwnerOut:
    return create_entity(ctx, Owner(**payload.model_dump()), payload.model_dump())


@router.patch("/owners/{owner_id}")
def update_owner(owner_id: uuid.UUID, payload: OwnerIn, ctx: Admin) -> OwnerOut:
    return update_entity(ctx, get_or_404(ctx, Owner, owner_id), payload.model_dump())


@router.delete("/owners/{owner_id}", status_code=204)
def delete_owner(owner_id: uuid.UUID, ctx: Admin) -> None:
    delete_entity(ctx, get_or_404(ctx, Owner, owner_id))
