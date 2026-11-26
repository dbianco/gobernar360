"""procedures_cidi

Revision ID: 0022
Revises: 0021
Create Date: 2026-11-26 11:00:00

The level of the provincial account (CiDi) each procedure asks to sign in with.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0022"
down_revision: str | Sequence[str] | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLE = "procedures_procedures"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(TABLE, sa.Column("cidi_level", sa.Integer(), nullable=True))
    op.create_check_constraint("cidi_level_valid", TABLE, "cidi_level BETWEEN 1 AND 3")
    op.create_check_constraint(
        "cidi_only_online", TABLE, "cidi_level IS NULL OR channel <> 'in_person'"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("cidi_only_online", TABLE, type_="check")
    op.drop_constraint("cidi_level_valid", TABLE, type_="check")
    op.drop_column(TABLE, "cidi_level")
