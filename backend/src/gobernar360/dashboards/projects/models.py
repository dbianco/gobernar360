"""Tables of the projects dashboard. All are tenant data protected by row-level security."""

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk

PRIORITIES = ("A+", "A", "B", "C")
STORED_STATUSES = ("not_started", "in_progress", "finished")

TABLE_NAMES = (
    "projects_terms",
    "projects_annual_budgets",
    "projects_axes",
    "projects_objectives",
    "projects_departments",
    "projects_programs",
    "projects_owners",
    "projects_projects",
    "projects_project_sdgs",
    "projects_milestones",
    "projects_indicators",
)


# The column helpers below run once, while the models are imported, where mutation testing
# cannot reach them (hence the pragmas); tests/test_models_match_migrations.py checks the
# schema they build against the migrations.
def _fk(
    target: str, ondelete: str = "RESTRICT", nullable: bool = False
) -> Mapped:  # pragma: no mutate block
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=nullable, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:  # pragma: no mutate block
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _name() -> Mapped[str]:  # pragma: no mutate block
    return mapped_column(String(200), nullable=False)


def _money() -> Mapped[Decimal]:  # pragma: no mutate block
    return mapped_column(Numeric(16, 2), nullable=False, default=Decimal("0"), server_default="0")


class Term(TenantMixin, AuditMixin, Base):
    """A government term ("gestión"): the period a plan of axes and projects belongs to."""

    __tablename__ = "projects_terms"
    __table_args__ = (CheckConstraint("end_year >= start_year", name="years_ordered"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()
    start_year: Mapped[int] = mapped_column(Integer, nullable=False)
    end_year: Mapped[int] = mapped_column(Integer, nullable=False)


class AnnualBudget(TenantMixin, AuditMixin, Base):
    """Total municipal budget of one year; the base for the planned-budget percentage."""

    __tablename__ = "projects_annual_budgets"
    __table_args__ = (
        UniqueConstraint("term_id", "year"),
        CheckConstraint("total_amount >= 0", name="total_amount_not_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    term_id: Mapped[uuid.UUID] = _fk("projects_terms.id", ondelete="CASCADE")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    total_amount: Mapped[Decimal] = _money()


class Axis(TenantMixin, AuditMixin, Base):
    __tablename__ = "projects_axes"

    id: Mapped[uuid.UUID] = uuid_pk()
    term_id: Mapped[uuid.UUID] = _fk("projects_terms.id")
    name: Mapped[str] = _name()


class Objective(TenantMixin, AuditMixin, Base):
    __tablename__ = "projects_objectives"

    id: Mapped[uuid.UUID] = uuid_pk()
    axis_id: Mapped[uuid.UUID] = _fk("projects_axes.id")
    name: Mapped[str] = _name()

    axis: Mapped[Axis] = relationship(lazy="joined")


class Department(TenantMixin, AuditMixin, Base):
    __tablename__ = "projects_departments"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class Program(TenantMixin, AuditMixin, Base):
    __tablename__ = "projects_programs"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class Owner(TenantMixin, AuditMixin, Base):
    """The person responsible for a project."""

    __tablename__ = "projects_owners"

    id: Mapped[uuid.UUID] = uuid_pk()
    full_name: Mapped[str] = _name()


class Project(TenantMixin, AuditMixin, Base):
    __tablename__ = "projects_projects"
    __table_args__ = (
        CheckConstraint(_in("priority", PRIORITIES), name="priority_valid"),
        CheckConstraint(_in("status", STORED_STATUSES), name="status_valid"),
        CheckConstraint("manual_progress BETWEEN 0 AND 100", name="manual_progress_range"),
        CheckConstraint("planned_budget >= 0", name="planned_budget_not_negative"),
        CheckConstraint("executed_budget >= 0", name="executed_budget_not_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    term_id: Mapped[uuid.UUID] = _fk("projects_terms.id")
    name: Mapped[str] = _name()
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    axis_id: Mapped[uuid.UUID] = _fk("projects_axes.id")
    objective_id: Mapped[uuid.UUID | None] = _fk("projects_objectives.id", nullable=True)
    department_id: Mapped[uuid.UUID] = _fk("projects_departments.id")
    owner_id: Mapped[uuid.UUID | None] = _fk("projects_owners.id", nullable=True)
    program_id: Mapped[uuid.UUID | None] = _fk("projects_programs.id", nullable=True)
    priority: Mapped[str] = mapped_column(String(2), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_budget: Mapped[Decimal] = _money()
    executed_budget: Mapped[Decimal] = _money()
    # "delayed" is never stored: it is derived from dates and milestones.
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    # Used only while the project has no milestones.
    manual_progress: Mapped[int | None] = mapped_column(Integer, nullable=True)

    term: Mapped[Term] = relationship(lazy="joined")
    axis: Mapped[Axis] = relationship(lazy="joined")
    objective: Mapped[Objective | None] = relationship(lazy="joined")
    department: Mapped[Department] = relationship(lazy="joined")
    owner: Mapped[Owner | None] = relationship(lazy="joined")
    program: Mapped[Program | None] = relationship(lazy="joined")
    sdgs: Mapped[list["ProjectSdg"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True, lazy="selectin"
    )
    milestones: Mapped[list["Milestone"]] = relationship(
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="Milestone.due_date",
    )


class ProjectSdg(TenantMixin, Base):
    __tablename__ = "projects_project_sdgs"
    __table_args__ = (CheckConstraint("sdg_number BETWEEN 1 AND 17", name="sdg_number_range"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects_projects.id", ondelete="CASCADE"), primary_key=True
    )
    sdg_number: Mapped[int] = mapped_column(Integer, primary_key=True)


class Milestone(TenantMixin, AuditMixin, Base):
    __tablename__ = "projects_milestones"

    id: Mapped[uuid.UUID] = uuid_pk()
    project_id: Mapped[uuid.UUID] = _fk("projects_projects.id", ondelete="CASCADE")
    name: Mapped[str] = _name()
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)


class Indicator(TenantMixin, AuditMixin, Base):
    """A strategic indicator that measures progress towards an objective."""

    __tablename__ = "projects_indicators"

    id: Mapped[uuid.UUID] = uuid_pk()
    objective_id: Mapped[uuid.UUID] = _fk("projects_objectives.id")
    name: Mapped[str] = _name()
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="", server_default="")
    baseline: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    objective: Mapped[Objective] = relationship(lazy="joined")
