"""Tables of the complaints dashboard. All are tenant data protected by row-level security."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk
from gobernar360.dashboards.complaints.lifecycle import EVENT_KINDS, STATES
from gobernar360.platform.models import Person, User

MAX_TARGET_DAYS = 365


def _fk(target: str, ondelete: str = "RESTRICT") -> Mapped[uuid.UUID]:
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=False, index=True)


def _optional_fk(target: str, ondelete: str = "RESTRICT") -> Mapped[uuid.UUID | None]:
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=True, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _name() -> Mapped[str]:
    return mapped_column(String(200), nullable=False)


class Area(TenantMixin, AuditMixin, Base):
    """An office of the municipality that solves complaints; each has its own queue."""

    __tablename__ = "complaints_areas"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class Zone(TenantMixin, AuditMixin, Base):
    """A part of town, from the list the municipality defines."""

    __tablename__ = "complaints_zones"

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()


class ComplaintType(TenantMixin, AuditMixin, Base):
    """What a complaint is about, the area it goes to and how long solving it should take."""

    __tablename__ = "complaints_types"
    __table_args__ = (
        CheckConstraint(f"target_days BETWEEN 1 AND {MAX_TARGET_DAYS}", name="target_days_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = _name()
    area_id: Mapped[uuid.UUID] = _fk("complaints_areas.id")
    # Target resolution time, in business days of the municipality's calendar.
    target_days: Mapped[int] = mapped_column(Integer, nullable=False)
    # Types no longer offered stay in every figure but are not used for new complaints.
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )

    area: Mapped[Area] = relationship(lazy="joined")


class WorkingWeek(TenantMixin, AuditMixin, Base):
    """The weekdays the municipality works. Without a row, Monday to Friday."""

    __tablename__ = "complaints_working_weeks"
    __table_args__ = (
        UniqueConstraint("municipality_id"),
        CheckConstraint("cardinality(weekdays) > 0", name="weekdays_not_empty"),
        CheckConstraint("weekdays <@ ARRAY[1,2,3,4,5,6,7]::smallint[]", name="weekdays_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # ISO weekdays, Monday = 1.
    weekdays: Mapped[list[int]] = mapped_column(ARRAY(SmallInteger), nullable=False)


class Holiday(TenantMixin, AuditMixin, Base):
    __tablename__ = "complaints_holidays"
    __table_args__ = (UniqueConstraint("municipality_id", "date"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    date: Mapped[date] = mapped_column(Date, nullable=False)
    name: Mapped[str] = _name()


class Complaint(TenantMixin, AuditMixin, Base):
    """One case raised by a resident, followed until it is solved."""

    __tablename__ = "complaints_complaints"
    __table_args__ = (
        UniqueConstraint("municipality_id", "number"),
        CheckConstraint(_in("state", STATES), name="state_valid"),
        CheckConstraint(f"target_days BETWEEN 1 AND {MAX_TARGET_DAYS}", name="target_days_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    # Correlative within the municipality: what people quote on the phone.
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    type_id: Mapped[uuid.UUID] = _fk("complaints_types.id")
    area_id: Mapped[uuid.UUID] = _fk("complaints_areas.id")
    zone_id: Mapped[uuid.UUID] = _fk("complaints_zones.id")
    address: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # The resident who complained, from the registry; null when anonymous.
    person_id: Mapped[uuid.UUID | None] = _optional_fk("people.id")
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    # Copied from the type when the complaint is registered or retyped, so later changes to
    # the type do not rewrite how this case is judged.
    target_days: Mapped[int] = mapped_column(Integer, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    type: Mapped[ComplaintType] = relationship(lazy="joined")
    area: Mapped[Area] = relationship(lazy="joined")
    zone: Mapped[Zone] = relationship(lazy="joined")
    person: Mapped[Person | None] = relationship(lazy="joined")


class ComplaintEvent(TenantMixin, Base):
    """One entry of a complaint's timeline. Entries are only ever added."""

    __tablename__ = "complaints_events"
    __table_args__ = (
        UniqueConstraint("complaint_id", "position"),
        CheckConstraint(_in("kind", EVENT_KINDS), name="kind_valid"),
        CheckConstraint(f"from_state IS NULL OR {_in('from_state', STATES)}", name="from_valid"),
        CheckConstraint(f"to_state IS NULL OR {_in('to_state', STATES)}", name="to_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    complaint_id: Mapped[uuid.UUID] = _fk("complaints_complaints.id", ondelete="CASCADE")
    # Order within the complaint, starting at 0 with its creation.
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    from_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    to_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
    from_area_id: Mapped[uuid.UUID | None] = _optional_fk("complaints_areas.id")
    to_area_id: Mapped[uuid.UUID | None] = _optional_fk("complaints_areas.id")
    from_type_id: Mapped[uuid.UUID | None] = _optional_fk("complaints_types.id")
    to_type_id: Mapped[uuid.UUID | None] = _optional_fk("complaints_types.id")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Null if the account was later deleted.
    user_id: Mapped[uuid.UUID | None] = _optional_fk("users.id", ondelete="SET NULL")

    user: Mapped[User | None] = relationship(lazy="joined")
    from_area: Mapped[Area | None] = relationship(foreign_keys=[from_area_id], lazy="joined")
    to_area: Mapped[Area | None] = relationship(foreign_keys=[to_area_id], lazy="joined")
    from_type: Mapped[ComplaintType | None] = relationship(
        foreign_keys=[from_type_id], lazy="joined"
    )
    to_type: Mapped[ComplaintType | None] = relationship(foreign_keys=[to_type_id], lazy="joined")
