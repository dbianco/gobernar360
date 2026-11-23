"""Tables of the social dashboard. All are tenant data protected by row-level security."""

import uuid
from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

# A column of SocialPerson is itself called "relationship".
from sqlalchemy.orm import relationship as related

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk
from gobernar360.platform.models import Person

# What a person is within their household. "head" is the household's reference person.
RELATIONSHIPS = (
    "head",
    "partner",
    "child",
    "parent",
    "sibling",
    "grandparent",
    "grandchild",
    "other_relative",
    "non_relative",
)


# The column helpers below run once, while the models are imported, where mutation testing
# cannot reach them (hence the pragmas); tests/test_models_match_migrations.py checks the
# schema they build against the migrations.
def _fk(target: str) -> Mapped[uuid.UUID]:  # pragma: no mutate block
    return mapped_column(Uuid, ForeignKey(target, ondelete="RESTRICT"), nullable=False, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:  # pragma: no mutate block
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _name() -> Mapped[str]:  # pragma: no mutate block
    return mapped_column(String(200), nullable=False)


def _text(length: int) -> Mapped[str]:  # pragma: no mutate block
    return mapped_column(String(length), nullable=False, default="", server_default="")


def _long_text() -> Mapped[str]:  # pragma: no mutate block
    return mapped_column(Text, nullable=False, default="", server_default="")


class BenefitCategory(TenantMixin, AuditMixin, Base):
    __tablename__ = "social_benefit_categories"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class Benefit(TenantMixin, AuditMixin, Base):
    """Something the municipality hands out: a food box, building materials, a subsidy."""

    __tablename__ = "social_benefits"

    id: Mapped[uuid.UUID] = uuid_pk()
    category_id: Mapped[uuid.UUID] = _fk("social_benefit_categories.id")
    name: Mapped[str] = _name()
    description: Mapped[str] = _long_text()

    category: Mapped[BenefitCategory] = related(lazy="joined")


class InterventionType(TenantMixin, AuditMixin, Base):
    """Kind of work the team does with a person, e.g. interview, home visit."""

    __tablename__ = "social_intervention_types"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class Household(TenantMixin, AuditMixin, Base):
    """A family group: the people who live together and are assisted as a unit."""

    __tablename__ = "social_households"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()
    address: Mapped[str] = _text(200)
    neighborhood: Mapped[str] = _text(100)


class SocialPerson(TenantMixin, AuditMixin, Base):
    """A person of the municipality's registry incorporated into this dashboard.

    Everything else in the dashboard points at this row rather than at the
    registry, so the dashboard only ever reaches people it incorporated. A person
    belongs to at most one household, so the membership lives here.
    """

    __tablename__ = "social_people"
    __table_args__ = (
        UniqueConstraint("person_id"),
        CheckConstraint(
            "(household_id IS NULL) = (relationship IS NULL)",
            name="relationship_only_inside_a_household",
        ),
        CheckConstraint(_in("relationship", RELATIONSHIPS), name="relationship_valid"),
        Index(
            "uq_social_people_one_head_per_household",
            "household_id",
            unique=True,
            postgresql_where=text("relationship = 'head'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = _fk("people.id")
    household_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("social_households.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    relationship: Mapped[str | None] = mapped_column(String(20), nullable=True)

    person: Mapped[Person] = related(lazy="joined")
    household: Mapped[Household | None] = related(lazy="joined")

    @property
    def full_name(self) -> str:
        return self.person.full_name

    @property
    def dni(self) -> str | None:
        return self.person.dni


class Delivery(TenantMixin, AuditMixin, Base):
    """A benefit handed to one person on a date."""

    __tablename__ = "social_deliveries"
    __table_args__ = (CheckConstraint("quantity >= 1", name="quantity_positive"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    benefit_id: Mapped[uuid.UUID] = _fk("social_benefits.id")
    person_id: Mapped[uuid.UUID] = _fk("social_people.id")
    date: Mapped[date] = mapped_column(Date, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    note: Mapped[str] = _long_text()

    benefit: Mapped[Benefit] = related(lazy="joined")
    person: Mapped[SocialPerson] = related(lazy="joined")


class Intervention(TenantMixin, AuditMixin, Base):
    """Something the team did with a person: an interview, a visit, a referral.

    `description` is reserved text: see `access.reads_reserved_text`.
    """

    __tablename__ = "social_interventions"

    id: Mapped[uuid.UUID] = uuid_pk()
    intervention_type_id: Mapped[uuid.UUID] = _fk("social_intervention_types.id")
    person_id: Mapped[uuid.UUID] = _fk("social_people.id")
    date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = _long_text()
    performed_by: Mapped[str] = _text(200)

    intervention_type: Mapped[InterventionType] = related(lazy="joined")
    person: Mapped[SocialPerson] = related(lazy="joined")
