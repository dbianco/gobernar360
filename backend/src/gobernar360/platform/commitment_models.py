"""Tables of commitments: what somebody owes somebody, agreed in a meeting or not. All are
tenant data protected by row-level security."""

import datetime as dt
import uuid
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk
from gobernar360.platform.models import User
from gobernar360.platform.subjects import SubjectMixin, subject_check

# "overdue" is never stored: it is an open commitment past its due date.
STORED_STATES = ("open", "done", "dropped")
# What a person is told about: it was given to them, or one they follow was delivered.
NOTICE_KINDS = ("assigned", "done")


# The column helpers below run once, while the models are imported, where mutation testing
# cannot reach them (hence the pragmas); tests/test_models_match_migrations.py checks the
# schema they build against the migrations.
def _fk(target: str, ondelete: str = "RESTRICT") -> Mapped[uuid.UUID]:  # pragma: no mutate block
    return mapped_column(Uuid, ForeignKey(target, ondelete=ondelete), nullable=False, index=True)


def _in(column: str, values: tuple[str, ...]) -> str:  # pragma: no mutate block
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Commitment(SubjectMixin, TenantMixin, AuditMixin, Base):
    """What was agreed, who owes it and by when.

    `source` is the dashboard that recorded it (a cabinet meeting): its members see it and
    its editors change it. Without one it is informal, and its creator's: see
    `platform.commitments` for who sees and who changes each.
    """

    __tablename__ = "commitments"
    __table_args__ = (
        CheckConstraint(_in("state", STORED_STATES), name="state_valid"),
        CheckConstraint("(state = 'done') = (completed_on IS NOT NULL)", name="done_has_date"),
        subject_check(),
        Index(
            "ix_commitments_subject",
            "municipality_id",
            "subject_dashboard",
            "subject_kind",
            "subject_ref",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    owner_id: Mapped[uuid.UUID] = _fk("users.id")
    due_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    state: Mapped[str] = mapped_column(
        String(20), nullable=False, default="open", server_default="open"
    )
    completed_on: Mapped[dt.date | None] = mapped_column(Date, nullable=True)

    owner: Mapped[User] = relationship(foreign_keys=[owner_id], lazy="joined", innerjoin=True)


class CommitmentFollower(TenantMixin, AuditMixin, Base):
    """Somebody attached to a commitment: they see it and are told when it is done."""

    __tablename__ = "commitment_followers"
    __table_args__ = (UniqueConstraint("commitment_id", "user_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    commitment_id: Mapped[uuid.UUID] = _fk("commitments.id", ondelete="CASCADE")
    user_id: Mapped[uuid.UUID] = _fk("users.id")


class CommitmentEntry(TenantMixin, AuditMixin, Base):
    """One entry of a commitment's history: a progress note, a change, or both.
    Entries are only ever added."""

    __tablename__ = "commitment_entries"

    id: Mapped[uuid.UUID] = uuid_pk()
    commitment_id: Mapped[uuid.UUID] = _fk("commitments.id", ondelete="CASCADE")
    note: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    # field -> [before, after], as text: state, due_date, owner, completed_on, description.
    changes: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )


class CommitmentNotice(TenantMixin, AuditMixin, Base):
    """Something a person was told inside the app about a commitment. `created_by` did it."""

    __tablename__ = "commitment_notices"
    __table_args__ = (
        CheckConstraint(_in("kind", NOTICE_KINDS), name="kind_valid"),
        Index(
            "ix_commitment_notices_unread",
            "municipality_id",
            "user_id",
            postgresql_where="read_at IS NULL",
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    commitment_id: Mapped[uuid.UUID] = _fk("commitments.id", ondelete="CASCADE")
    user_id: Mapped[uuid.UUID] = _fk("users.id")
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    read_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
