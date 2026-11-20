"""Tables of the procedures dashboard. All are tenant data protected by row-level security."""

import uuid
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk

# Who issues or keeps a piece of data; listed from closest to the municipality outwards.
SOURCE_LEVELS = ("municipal", "provincial", "national", "other")
AUDIENCES = ("people", "organizations", "both")
CHANNELS = ("in_person", "online", "both")
# How a requirement is asked for today.
FORMATS = ("paper", "digital")


def _fk(target: str, ondelete: str = "RESTRICT") -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=False, index=True)


def _optional_fk(target: str) -> Mapped[uuid.UUID | None]:
    return mapped_column(Uuid, ForeignKey(target, ondelete="RESTRICT"), nullable=True, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _name() -> Mapped[str]:
    return mapped_column(String(200), nullable=False)


def _long_text() -> Mapped[str]:
    return mapped_column(Text, nullable=False, default="", server_default="")


class Area(TenantMixin, AuditMixin, Base):
    """An office of the municipality that runs procedures or keeps data."""

    __tablename__ = "procedures_areas"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class Source(TenantMixin, AuditMixin, Base):
    """The authoritative holder of a piece of data or issuer of a document."""

    __tablename__ = "procedures_sources"
    __table_args__ = (
        CheckConstraint(_in("level", SOURCE_LEVELS), name="level_valid"),
        CheckConstraint("area_id IS NULL OR level = 'municipal'", name="area_only_when_municipal"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()
    level: Mapped[str] = mapped_column(String(20), nullable=False)
    area_id: Mapped[uuid.UUID | None] = _optional_fk("procedures_areas.id")

    area: Mapped[Area | None] = relationship(lazy="joined")


class Requirement(TenantMixin, AuditMixin, Base):
    """Something procedures ask for, from the municipality's single list.

    Without a source, the person brings it themselves.
    """

    __tablename__ = "procedures_requirements"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()
    description: Mapped[str] = _long_text()
    source_id: Mapped[uuid.UUID | None] = _optional_fk("procedures_sources.id")

    source: Mapped[Source | None] = relationship(lazy="joined")


class Procedure(TenantMixin, AuditMixin, Base):
    """A procedure the municipality offers to people or organisations."""

    __tablename__ = "procedures_procedures"
    __table_args__ = (
        CheckConstraint(_in("audience", AUDIENCES), name="audience_valid"),
        CheckConstraint(_in("channel", CHANNELS), name="channel_valid"),
        CheckConstraint("cost IS NULL OR (cost >= 0 AND NOT is_free)", name="cost_valid"),
        CheckConstraint("duration_days >= 0", name="duration_days_not_negative"),
        CheckConstraint("annual_volume >= 0", name="annual_volume_not_negative"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()
    description: Mapped[str] = _long_text()
    area_id: Mapped[uuid.UUID] = _fk("procedures_areas.id")
    audience: Mapped[str] = mapped_column(String(20), nullable=False)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    # Where it is done online, when it can be.
    url: Mapped[str] = mapped_column(String(500), nullable=False, default="", server_default="")
    is_free: Mapped[bool] = mapped_column(Boolean, nullable=False)
    cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    # Estimated days to resolve it, and estimated times it is done in a year.
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Procedures no longer offered stay in the inventory but out of every count.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    area: Mapped[Area] = relationship(lazy="joined")


class ProcedureRequirement(TenantMixin, AuditMixin, Base):
    """A requirement asked for by one procedure, and how it is asked for today."""

    __tablename__ = "procedures_procedure_requirements"
    __table_args__ = (
        UniqueConstraint("procedure_id", "requirement_id"),
        CheckConstraint(_in("format", FORMATS), name="format_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    procedure_id: Mapped[uuid.UUID] = _fk("procedures_procedures.id", ondelete="CASCADE")
    requirement_id: Mapped[uuid.UUID] = _fk("procedures_requirements.id")
    mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    note: Mapped[str] = _long_text()

    requirement: Mapped[Requirement] = relationship(lazy="joined")
