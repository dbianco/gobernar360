"""agreed_dates

Revision ID: 0024
Revises: 0023
Create Date: 2026-11-26 13:00:00

The date a commitment was agreed for, which later changes do not move, and telling whoever
gave a commitment that its owner left.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0024"
down_revision: str | Sequence[str] | None = "0023"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOTICES = "commitment_notices"

# The date before the first change its history tells of, or the one it still has.
FIRST_DATE = """
UPDATE commitments SET agreed_due_date = COALESCE(
    (
        SELECT (entry.changes -> 'due_date' ->> 0)::date
        FROM commitment_entries AS entry
        WHERE entry.commitment_id = commitments.id AND entry.changes ? 'due_date'
        ORDER BY entry.created_at, entry.id
        LIMIT 1
    ),
    due_date
)
"""


def _notice_kinds(*kinds: str) -> None:
    op.drop_constraint("kind_valid", NOTICES, type_="check")
    listed = ", ".join(f"'{kind}'" for kind in kinds)
    op.create_check_constraint("kind_valid", NOTICES, f"kind IN ({listed})")


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("commitments", sa.Column("agreed_due_date", sa.Date(), nullable=True))
    op.execute(FIRST_DATE)
    op.alter_column("commitments", "agreed_due_date", nullable=False)
    _notice_kinds("assigned", "done", "owner_left")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(f"DELETE FROM {NOTICES} WHERE kind = 'owner_left'")
    _notice_kinds("assigned", "done")
    op.drop_column("commitments", "agreed_due_date")
