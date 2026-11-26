"""Notices to residents, and each municipality's connection to CiDi. All are tenant data
under row-level security."""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk

CIDI, EMAIL = "cidi", "email"
CHANNELS = (CIDI, EMAIL)

QUEUED, HANDED_OVER, FAILED, NO_CHANNEL = "queued", "handed_over", "failed", "no_channel"
STATES = (QUEUED, HANDED_OVER, FAILED, NO_CHANNEL)

NOT_REQUESTED, REQUESTED, APPROVED = "not_requested", "requested", "approved"
ADHESION_STATES = (NOT_REQUESTED, REQUESTED, APPROVED)


class ResidentNotice(TenantMixin, AuditMixin, Base):
    """Something a resident is told about what they asked for, by one channel.

    The text is frozen when it is queued, so what was sent can always be read. It only says
    "handed over": whether that has any legal effect is not for the platform to say.
    """

    __tablename__ = "resident_notices"
    __table_args__ = (
        # Asking twice for the same event tells the person once.
        UniqueConstraint("event_key", "person_id", "channel"),
        CheckConstraint(f"channel IN {CHANNELS}", name="channel_valid"),
        CheckConstraint(f"state IN {STATES}", name="state_valid"),
        CheckConstraint(
            "(state = 'handed_over') = (handed_over_at IS NOT NULL)", name="handed_over_when"
        ),
        Index(
            "ix_resident_notices_queued",
            "next_attempt_at",
            postgresql_where=text("state = 'queued'"),
        ),
        Index("ix_resident_notices_subject", "subject_dashboard", "subject_kind", "subject_ref"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    person_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("people.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    # What it is about, as the dashboard that asked for it calls it.
    subject_dashboard: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_kind: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_ref: Mapped[str] = mapped_column(String(50), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    channel: Mapped[str] = mapped_column(String(10), nullable=False)
    state: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    # Plain text.
    body: Mapped[str] = mapped_column(Text, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Whatever CiDi calls the message.
    external_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    handed_over_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CidiConnection(TenantMixin, AuditMixin, Base):
    """How far the municipality's own adhesion to CiDi is."""

    __tablename__ = "cidi_connections"
    __table_args__ = (
        UniqueConstraint("municipality_id"),
        CheckConstraint(f"adhesion_state IN {ADHESION_STATES}", name="adhesion_state_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    adhesion_state: Mapped[str] = mapped_column(
        String(20), nullable=False, default=NOT_REQUESTED, server_default=NOT_REQUESTED
    )
    adhesion_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    # The number the Province gave the request.
    adhesion_file: Mapped[str] = mapped_column(
        String(100), nullable=False, default="", server_default=""
    )


class CidiConnectionValue(TenantMixin, AuditMixin, Base):
    """One piece of the connection. Secrets are only stored encrypted (`cidi/connection.py`)."""

    __tablename__ = "cidi_connection_values"
    __table_args__ = (
        UniqueConstraint("municipality_id", "name"),
        CheckConstraint("num_nulls(value, encrypted) = 1", name="plain_or_secret"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[str | None] = mapped_column(String(500), nullable=True)
    encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
