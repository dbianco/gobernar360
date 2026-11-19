"""Tables of the environment dashboard. All are tenant data protected by row-level security."""

import uuid
from decimal import Decimal

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Numeric, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk

# The environmental agenda is split into these fixed categories; municipalities
# define their own subcategories and variables inside them.
CATEGORIES = ("energy", "waste", "water", "air", "mobility", "biodiversity", "governance")
FREQUENCIES = ("monthly", "annual")
DIRECTIONS = ("higher_is_better", "lower_is_better")
SOURCES = ("municipal", "external")
AGGREGATIONS = ("sum", "average", "last")

# Period of a value loaded for the whole year; months are 1 to 12.
WHOLE_YEAR = 0


def _fk(target: str) -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey(target, ondelete="RESTRICT"), nullable=False, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _choice(length: int = 20) -> Mapped[str]:
    return mapped_column(String(length), nullable=False)


class Subcategory(TenantMixin, AuditMixin, Base):
    __tablename__ = "environment_subcategories"
    __table_args__ = (CheckConstraint(_in("category", CATEGORIES), name="category_valid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    category: Mapped[str] = _choice()
    name: Mapped[str] = mapped_column(String(200), nullable=False)


class Variable(TenantMixin, AuditMixin, Base):
    """Something the municipality measures every month or every year."""

    __tablename__ = "environment_variables"
    __table_args__ = (
        CheckConstraint(_in("frequency", FREQUENCIES), name="frequency_valid"),
        CheckConstraint(_in("direction", DIRECTIONS), name="direction_valid"),
        CheckConstraint(_in("source", SOURCES), name="source_valid"),
        CheckConstraint(_in("annual_aggregation", AGGREGATIONS), name="annual_aggregation_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    subcategory_id: Mapped[uuid.UUID] = _fk("environment_subcategories.id")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="", server_default="")
    frequency: Mapped[str] = _choice()
    # Goal for the year's figure, in the variable's unit.
    target: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    direction: Mapped[str] = _choice()
    source: Mapped[str] = _choice()
    # How the months of a monthly variable are turned into the year's figure.
    annual_aggregation: Mapped[str] = _choice()

    subcategory: Mapped[Subcategory] = relationship(lazy="joined")


class Value(TenantMixin, AuditMixin, Base):
    __tablename__ = "environment_values"
    __table_args__ = (
        UniqueConstraint("variable_id", "year", "period"),
        CheckConstraint("period BETWEEN 0 AND 12", name="period_range"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    variable_id: Mapped[uuid.UUID] = _fk("environment_variables.id")
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    period: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
