"""municipality suspension

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-23 15:29:38.536120

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0011"
down_revision: str | Sequence[str] | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

FOREIGN_KEY = "municipalities_suspended_by_fkey"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "municipalities", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "municipalities",
        sa.Column("suspension_reason", sa.String(length=500), server_default="", nullable=False),
    )
    op.add_column("municipalities", sa.Column("suspended_by", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        FOREIGN_KEY, "municipalities", "users", ["suspended_by"], ["id"], ondelete="SET NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(FOREIGN_KEY, "municipalities", type_="foreignkey")
    op.drop_column("municipalities", "suspended_by")
    op.drop_column("municipalities", "suspension_reason")
    op.drop_column("municipalities", "suspended_at")
