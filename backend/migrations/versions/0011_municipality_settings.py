"""municipality_settings

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-22 16:10:00

Per-municipality configuration (notification recipients, single sign-on, email texts),
HTML emails, notifications tracked per address, and how each session signed in.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from gobernar360.core.db import grant_app_access

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _timestamp(name: str) -> sa.Column:
    return sa.Column(
        name, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "municipality_settings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.Column(
            "notification_emails",
            postgresql.ARRAY(sa.String(length=320)),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("sso_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        _timestamp("updated_at"),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("municipality_id"),
    )
    op.create_table(
        "email_templates",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=50), nullable=False),
        sa.Column("subject", sa.String(length=300), nullable=False),
        sa.Column("html", sa.Text(), nullable=False),
        _timestamp("updated_at"),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("municipality_id", "key"),
    )
    op.create_index(
        op.f("ix_email_templates_municipality_id"), "email_templates", ["municipality_id"]
    )
    grant_app_access("municipality_settings")
    grant_app_access("email_templates")

    op.add_column("email_outbox", sa.Column("body_html", sa.Text(), nullable=True))

    op.add_column(
        "sessions",
        sa.Column("auth_method", sa.String(length=20), server_default="password", nullable=False),
    )
    op.create_check_constraint(
        "auth_method_valid", "sessions", "auth_method IN ('password', 'sso')"
    )

    # Notifications are now tracked per address, so lists of addresses can receive them.
    op.add_column(
        "notifications_sent", sa.Column("recipient", sa.String(length=320), nullable=True)
    )
    op.execute(
        "UPDATE notifications_sent SET recipient = users.email "
        "FROM users WHERE users.id = notifications_sent.user_id"
    )
    op.alter_column("notifications_sent", "recipient", nullable=False)
    op.drop_constraint(
        "notifications_sent_municipality_id_user_id_kind_event_key_key",
        "notifications_sent",
        type_="unique",
    )
    op.drop_column("notifications_sent", "user_id")
    op.create_unique_constraint(
        "notifications_sent_municipality_id_recipient_kind_event_key_key",
        "notifications_sent",
        ["municipality_id", "recipient", "kind", "event_key"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column("notifications_sent", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE notifications_sent SET user_id = users.id "
        "FROM users WHERE users.email = notifications_sent.recipient"
    )
    # Addresses without an account cannot be represented before this revision.
    op.execute("DELETE FROM notifications_sent WHERE user_id IS NULL")
    op.alter_column("notifications_sent", "user_id", nullable=False)
    op.create_foreign_key(
        "notifications_sent_user_id_fkey",
        "notifications_sent",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.drop_constraint(
        "notifications_sent_municipality_id_recipient_kind_event_key_key",
        "notifications_sent",
        type_="unique",
    )
    op.drop_column("notifications_sent", "recipient")
    op.create_unique_constraint(
        "notifications_sent_municipality_id_user_id_kind_event_key_key",
        "notifications_sent",
        ["municipality_id", "user_id", "kind", "event_key"],
    )

    op.drop_constraint("auth_method_valid", "sessions", type_="check")
    op.drop_column("sessions", "auth_method")
    op.drop_column("email_outbox", "body_html")
    op.drop_index(op.f("ix_email_templates_municipality_id"), table_name="email_templates")
    op.drop_table("email_templates")
    op.drop_table("municipality_settings")
