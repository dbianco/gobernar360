"""Tables of the cabinet dashboard. All are tenant data protected by row-level security.

The commitments themselves are the platform's (`platform.commitment_models`)."""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk
from gobernar360.platform.subjects import SubjectMixin, subject_check

# Where an agenda item came from: typed, a status light or a commitment.
ITEM_SOURCES = ("manual", "light", "commitment")


# The column helpers below run once, while the models are imported, where mutation testing
# cannot reach them (hence the pragmas); tests/test_models_match_migrations.py checks the
# schema they build against the migrations.
def _fk(target: str, ondelete: str = "RESTRICT") -> Mapped[uuid.UUID]:  # pragma: no mutate block
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=False, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:  # pragma: no mutate block
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def _long_text() -> Mapped[str]:  # pragma: no mutate block
    return mapped_column(Text, nullable=False, default="", server_default="")


class Meeting(TenantMixin, AuditMixin, Base):
    """A cabinet meeting. Closing it freezes it; a municipality has one open at a time."""

    __tablename__ = "cabinet_meetings"
    __table_args__ = (
        Index(
            "uq_cabinet_meetings_one_open",
            "municipality_id",
            unique=True,
            postgresql_where=text("closed_at IS NULL"),
        ),
        CheckConstraint("(closed_at IS NULL) = (minutes IS NULL)", name="closed_has_minutes"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    # People without an account who also came.
    guests: Mapped[str] = _long_text()
    notes: Mapped[str] = _long_text()
    closed_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # What the meeting recorded, copied when it was closed: later changes to its commitments
    # or to what they point at do not reach it. See minutes.py.
    minutes: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True), nullable=True)


class Attendee(TenantMixin, AuditMixin, Base):
    """A member of the municipality who attends a meeting."""

    __tablename__ = "cabinet_attendees"
    __table_args__ = (UniqueConstraint("meeting_id", "user_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _fk("cabinet_meetings.id", ondelete="CASCADE")
    user_id: Mapped[uuid.UUID] = _fk("users.id")


class AgendaItem(SubjectMixin, TenantMixin, AuditMixin, Base):
    """A point of a meeting's agenda: what was discussed about it and what was agreed."""

    __tablename__ = "cabinet_agenda_items"
    __table_args__ = (
        CheckConstraint(_in("source", ITEM_SOURCES), name="source_valid"),
        CheckConstraint("(source = 'commitment') = (commitment_id IS NOT NULL)", name="topic"),
        CheckConstraint("source <> 'light' OR subject_ref IS NOT NULL", name="light_has_subject"),
        subject_check(),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    meeting_id: Mapped[uuid.UUID] = _fk("cabinet_meetings.id", ondelete="CASCADE")
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    # Typed by a person. Empty for lights and commitments, named after what they are about:
    # a stored name would tell it to members who may not see the subject.
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="", server_default="")
    notes: Mapped[str] = _long_text()
    # Items left undiscussed when the meeting closes are proposed for the next one.
    discussed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    # The commitment the item is about, for those that follow one up.
    commitment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("commitments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # The undiscussed item of the previous meeting this one comes from.
    carried_from_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("cabinet_agenda_items.id", ondelete="SET NULL"), nullable=True, index=True
    )


class Taken(TenantMixin, AuditMixin, Base):
    """That a commitment was taken on an agenda item, and so in its meeting."""

    __tablename__ = "cabinet_taken"

    id: Mapped[uuid.UUID] = uuid_pk()
    commitment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("commitments.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    item_id: Mapped[uuid.UUID] = _fk("cabinet_agenda_items.id")


class Carryover(TenantMixin, AuditMixin, Base):
    """A commitment still open when a later meeting was prepared.

    How many times a commitment was postponed is how many of these it has: being unique
    per meeting, no meeting can count twice.
    """

    __tablename__ = "cabinet_carryovers"
    __table_args__ = (UniqueConstraint("commitment_id", "meeting_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    commitment_id: Mapped[uuid.UUID] = _fk("commitments.id", ondelete="CASCADE")
    meeting_id: Mapped[uuid.UUID] = _fk("cabinet_meetings.id", ondelete="CASCADE")
