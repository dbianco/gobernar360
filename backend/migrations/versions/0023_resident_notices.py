"""resident_notices

Revision ID: 0023
Revises: 0022
Create Date: 2026-11-26 12:00:00

Telling residents what happened to what they asked for (task 19): their CUIL in the people
registry, the notices, how each municipality sends them and its connection to CiDi.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from gobernar360.core.db import enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = "0023"
down_revision: str | Sequence[str] | None = "0022"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _tenant_columns() -> list[sa.Column]:
    return [
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
    ]


def _id() -> sa.Column:
    return sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("people", sa.Column("cuil", sa.String(length=11), nullable=True))
    op.create_unique_constraint(
        "people_municipality_id_cuil_key", "people", ["municipality_id", "cuil"]
    )
    op.create_check_constraint("cuil_digits", "people", "cuil ~ '^[0-9]{11}$'")

    op.add_column(
        "municipality_settings",
        sa.Column(
            "resident_notice_channel",
            sa.String(length=20),
            server_default="email",
            nullable=False,
        ),
    )
    op.add_column(
        "municipality_settings",
        sa.Column("cidi_ordinance", sa.String(length=200), server_default="", nullable=False),
    )
    op.create_check_constraint(
        "resident_notice_channel_valid",
        "municipality_settings",
        "resident_notice_channel IN ('email', 'cidi_then_email', 'cidi')",
    )

    op.create_table(
        "cidi_connections",
        _id(),
        sa.Column(
            "adhesion_state", sa.String(length=20), server_default="not_requested", nullable=False
        ),
        sa.Column("adhesion_date", sa.Date(), nullable=True),
        sa.Column("adhesion_file", sa.String(length=100), server_default="", nullable=False),
        *_tenant_columns(),
        sa.CheckConstraint(
            "adhesion_state IN ('not_requested', 'requested', 'approved')",
            name="adhesion_state_valid",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("municipality_id"),
    )
    op.create_index(
        op.f("ix_cidi_connections_municipality_id"), "cidi_connections", ["municipality_id"]
    )
    enable_tenant_rls("cidi_connections")

    op.create_table(
        "cidi_connection_values",
        _id(),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("value", sa.String(length=500), nullable=True),
        sa.Column("encrypted", sa.LargeBinary(), nullable=True),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
        *_tenant_columns(),
        sa.CheckConstraint("num_nulls(value, encrypted) = 1", name="plain_or_secret"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("municipality_id", "name"),
    )
    op.create_index(
        op.f("ix_cidi_connection_values_municipality_id"),
        "cidi_connection_values",
        ["municipality_id"],
    )
    enable_tenant_rls("cidi_connection_values")

    op.create_table(
        "resident_notices",
        _id(),
        sa.Column("person_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=50), nullable=False),
        sa.Column("subject_dashboard", sa.String(length=50), nullable=False),
        sa.Column("subject_kind", sa.String(length=50), nullable=False),
        sa.Column("subject_ref", sa.String(length=50), nullable=False),
        sa.Column("event_key", sa.String(length=200), nullable=False),
        sa.Column("channel", sa.String(length=10), nullable=False),
        sa.Column("state", sa.String(length=20), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("external_id", sa.String(length=200), nullable=True),
        sa.Column("handed_over_at", sa.DateTime(timezone=True), nullable=True),
        *_tenant_columns(),
        sa.CheckConstraint("channel IN ('cidi', 'email')", name="channel_valid"),
        sa.CheckConstraint(
            "state IN ('queued', 'handed_over', 'failed', 'no_channel')", name="state_valid"
        ),
        sa.CheckConstraint(
            "(state = 'handed_over') = (handed_over_at IS NOT NULL)", name="handed_over_when"
        ),
        sa.ForeignKeyConstraint(["person_id"], ["people.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("event_key", "person_id", "channel"),
    )
    op.create_index(
        op.f("ix_resident_notices_municipality_id"), "resident_notices", ["municipality_id"]
    )
    op.create_index(op.f("ix_resident_notices_person_id"), "resident_notices", ["person_id"])
    op.create_index(
        "ix_resident_notices_queued",
        "resident_notices",
        ["next_attempt_at"],
        postgresql_where=sa.text("state = 'queued'"),
    )
    op.create_index(
        "ix_resident_notices_subject",
        "resident_notices",
        ["subject_dashboard", "subject_kind", "subject_ref"],
    )
    enable_tenant_rls("resident_notices")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("resident_notices")
    op.drop_table("cidi_connection_values")
    op.drop_table("cidi_connections")
    op.drop_constraint("resident_notice_channel_valid", "municipality_settings", type_="check")
    op.drop_column("municipality_settings", "cidi_ordinance")
    op.drop_column("municipality_settings", "resident_notice_channel")
    op.drop_constraint("cuil_digits", "people", type_="check")
    op.drop_constraint("people_municipality_id_cuil_key", "people", type_="unique")
    op.drop_column("people", "cuil")
