"""commitments

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-24 14:50:00

Commitments become the platform's, so any member can give one without a cabinet meeting:
the cabinet's tables of commitments and history are renamed (rows, policies and grants stay
as they are), and which agenda item each was taken on moves to a table of the cabinet's.
People attached to a commitment, and what each person was told about it, are new.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from gobernar360.core.db import enable_tenant_rls

# revision identifiers, used by Alembic.
revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RENAMED_TABLES = {
    "cabinet_commitments": "commitments",
    "cabinet_progress_entries": "commitment_entries",
}
RENAMED_INDEXES = {
    "ix_cabinet_commitments_municipality_id": "ix_commitments_municipality_id",
    "ix_cabinet_commitments_owner_id": "ix_commitments_owner_id",
    "ix_cabinet_commitments_subject": "ix_commitments_subject",
    "ix_cabinet_progress_entries_commitment_id": "ix_commitment_entries_commitment_id",
    "ix_cabinet_progress_entries_municipality_id": "ix_commitment_entries_municipality_id",
}


def _create_tenant_table(name: str, *columns: sa.Column | sa.Constraint) -> None:
    def timestamp(column: str) -> sa.Column:
        return sa.Column(
            column, sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        )

    op.create_table(
        name,
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        *columns,
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        timestamp("created_at"),
        timestamp("updated_at"),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{name}_municipality_id", name, ["municipality_id"])


def _commitment_fk() -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["commitment_id"], ["commitments.id"], ondelete="CASCADE")


def _user_fk() -> sa.ForeignKeyConstraint:
    return sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT")


def upgrade() -> None:
    """Upgrade schema."""
    for old, new in RENAMED_TABLES.items():
        op.rename_table(old, new)
    for old, new in RENAMED_INDEXES.items():
        op.execute(f"ALTER INDEX {old} RENAME TO {new}")

    op.add_column("commitments", sa.Column("source", sa.String(length=50), nullable=True))
    op.execute("UPDATE commitments SET source = 'cabinet'")

    _create_tenant_table(
        "cabinet_taken",
        sa.Column("commitment_id", sa.Uuid(), nullable=False),
        sa.Column("item_id", sa.Uuid(), nullable=False),
        _commitment_fk(),
        sa.ForeignKeyConstraint(["item_id"], ["cabinet_agenda_items.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("commitment_id"),
    )
    op.create_index("ix_cabinet_taken_item_id", "cabinet_taken", ["item_id"])
    op.execute(
        "INSERT INTO cabinet_taken (commitment_id, item_id, municipality_id, created_at, "
        "updated_at, created_by, updated_by) SELECT id, item_id, municipality_id, created_at, "
        "created_at, created_by, created_by FROM commitments"
    )
    # Its foreign key and its index go with it.
    op.drop_column("commitments", "item_id")

    _create_tenant_table(
        "commitment_followers",
        sa.Column("commitment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        _commitment_fk(),
        _user_fk(),
        sa.UniqueConstraint("commitment_id", "user_id"),
    )
    _create_tenant_table(
        "commitment_notices",
        sa.Column("commitment_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        _commitment_fk(),
        _user_fk(),
        sa.CheckConstraint("kind IN ('assigned', 'done')", name="kind_valid"),
    )
    for table in ("commitment_followers", "commitment_notices"):
        for column in ("commitment_id", "user_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_commitment_notices_unread",
        "commitment_notices",
        ["municipality_id", "user_id"],
        postgresql_where=sa.text("read_at IS NULL"),
    )

    for table in ("cabinet_taken", "commitment_followers", "commitment_notices"):
        enable_tenant_rls(table)


def downgrade() -> None:
    """Downgrade schema. Informal commitments have no place in the older schema: they go."""
    op.drop_table("commitment_notices")
    op.drop_table("commitment_followers")
    op.execute("DELETE FROM commitments WHERE id NOT IN (SELECT commitment_id FROM cabinet_taken)")
    op.add_column("commitments", sa.Column("item_id", sa.Uuid(), nullable=True))
    op.execute(
        "UPDATE commitments SET item_id = cabinet_taken.item_id FROM cabinet_taken "
        "WHERE cabinet_taken.commitment_id = commitments.id"
    )
    op.alter_column("commitments", "item_id", nullable=False)
    op.drop_table("cabinet_taken")
    op.drop_column("commitments", "source")

    for old, new in RENAMED_INDEXES.items():
        op.execute(f"ALTER INDEX {new} RENAME TO {old}")
    for old, new in RENAMED_TABLES.items():
        op.rename_table(new, old)
    op.create_foreign_key(
        "cabinet_commitments_item_id_fkey",
        "cabinet_commitments",
        "cabinet_agenda_items",
        ["item_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_cabinet_commitments_item_id", "cabinet_commitments", ["item_id"])
