"""Tables of the economic dashboard. All are tenant data protected by row-level security."""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk
from gobernar360.platform.models import Person

# Who a tool can be assigned to.
AUDIENCES = ("actors", "people", "both")
EMPLOYMENT_STATUSES = (
    "unknown",
    "employed",
    "self_employed",
    "unemployed",
    "student",
    "retired",
    "other",
)
# What a person is to an actor they are linked to.
ROLES = ("owner", "contact", "employee")


def _fk(target: str, ondelete: str = "RESTRICT") -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=False, index=True)


def _optional_fk(target: str) -> Mapped[uuid.UUID | None]:
    return mapped_column(Uuid, ForeignKey(target, ondelete="RESTRICT"), nullable=True, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _name() -> Mapped[str]:
    return mapped_column(String(200), nullable=False)


def _text(length: int) -> Mapped[str]:
    return mapped_column(String(length), nullable=False, default="", server_default="")


def _long_text() -> Mapped[str]:
    return mapped_column(Text, nullable=False, default="", server_default="")


class ActorType(TenantMixin, AuditMixin, Base):
    """Kind of economic actor, e.g. shop, industry, entrepreneur."""

    __tablename__ = "economic_actor_types"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class Sector(TenantMixin, AuditMixin, Base):
    __tablename__ = "economic_sectors"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class ToolCategory(TenantMixin, AuditMixin, Base):
    __tablename__ = "economic_tool_categories"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class ToolSubcategory(TenantMixin, AuditMixin, Base):
    __tablename__ = "economic_tool_subcategories"

    id: Mapped[uuid.UUID] = uuid_pk()
    category_id: Mapped[uuid.UUID] = _fk("economic_tool_categories.id")
    name: Mapped[str] = _name()


class Tool(TenantMixin, AuditMixin, Base):
    """A support instrument the municipality offers: a credit line, a course, a programme."""

    __tablename__ = "economic_tools"
    __table_args__ = (CheckConstraint(_in("audience", AUDIENCES), name="audience_valid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    category_id: Mapped[uuid.UUID] = _fk("economic_tool_categories.id")
    subcategory_id: Mapped[uuid.UUID | None] = _optional_fk("economic_tool_subcategories.id")
    name: Mapped[str] = _name()
    description: Mapped[str] = _long_text()
    audience: Mapped[str] = mapped_column(String(20), nullable=False)

    category: Mapped[ToolCategory] = relationship(lazy="joined")
    subcategory: Mapped[ToolSubcategory | None] = relationship(lazy="joined")


class Actor(TenantMixin, AuditMixin, Base):
    """A company, shop, entrepreneur or organisation of the local economy."""

    __tablename__ = "economic_actors"
    __table_args__ = (CheckConstraint("employee_count >= 0", name="employee_count_not_negative"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()
    actor_type_id: Mapped[uuid.UUID | None] = _optional_fk("economic_actor_types.id")
    sector_id: Mapped[uuid.UUID | None] = _optional_fk("economic_sectors.id")
    # Digits only, or empty when unknown.
    cuit: Mapped[str] = _text(11)
    address: Mapped[str] = _text(200)
    phone: Mapped[str] = _text(50)
    email: Mapped[str] = _text(200)
    employee_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = _long_text()

    actor_type: Mapped[ActorType | None] = relationship(lazy="joined")
    sector: Mapped[Sector | None] = relationship(lazy="joined")


class EconomicPerson(TenantMixin, AuditMixin, Base):
    """A person of the municipality's registry incorporated into this dashboard.

    Everything else in the dashboard points at this row rather than at the
    registry, so the dashboard only ever reaches people it incorporated.
    """

    __tablename__ = "economic_people"
    __table_args__ = (
        UniqueConstraint("person_id"),
        CheckConstraint(
            _in("employment_status", EMPLOYMENT_STATUSES), name="employment_status_valid"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = _fk("people.id")
    employment_status: Mapped[str] = mapped_column(String(20), nullable=False)
    occupation: Mapped[str] = _text(200)

    person: Mapped[Person] = relationship(lazy="joined")

    @property
    def full_name(self) -> str:
        return self.person.full_name


class ActorPerson(TenantMixin, AuditMixin, Base):
    __tablename__ = "economic_actor_people"
    __table_args__ = (
        UniqueConstraint("actor_id", "person_id"),
        CheckConstraint(_in("role", ROLES), name="role_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    actor_id: Mapped[uuid.UUID] = _fk("economic_actors.id", ondelete="CASCADE")
    person_id: Mapped[uuid.UUID] = _fk("economic_people.id", ondelete="CASCADE")
    role: Mapped[str] = mapped_column(String(20), nullable=False)

    actor: Mapped[Actor] = relationship(lazy="joined")
    person: Mapped[EconomicPerson] = relationship(lazy="joined")


class Assignment(TenantMixin, AuditMixin, Base):
    """A tool given to one actor or to one person on a date."""

    __tablename__ = "economic_assignments"
    __table_args__ = (
        CheckConstraint("(actor_id IS NULL) <> (person_id IS NULL)", name="exactly_one_target"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    tool_id: Mapped[uuid.UUID] = _fk("economic_tools.id")
    actor_id: Mapped[uuid.UUID | None] = _optional_fk("economic_actors.id")
    person_id: Mapped[uuid.UUID | None] = _optional_fk("economic_people.id")
    date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str] = _long_text()

    tool: Mapped[Tool] = relationship(lazy="joined")
    actor: Mapped[Actor | None] = relationship(lazy="joined")
    person: Mapped[EconomicPerson | None] = relationship(lazy="joined")
