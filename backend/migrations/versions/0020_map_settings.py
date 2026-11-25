"""map_settings

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-25 10:00:00

What each municipality chooses for its maps: the background, and from how many sensitive
records a count per zone is shown.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0020"
down_revision: str | Sequence[str] | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "municipality_settings",
        sa.Column("small_zone_threshold", sa.Integer(), server_default="5", nullable=False),
    )
    op.add_column(
        "municipality_settings",
        sa.Column(
            "map_background", sa.String(length=30), server_default="standard", nullable=False
        ),
    )
    op.add_column(
        "municipality_settings", sa.Column("map_api_key", sa.String(length=100), nullable=True)
    )
    op.create_check_constraint(
        "small_zone_threshold_range",
        "municipality_settings",
        "small_zone_threshold BETWEEN 2 AND 100",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint("small_zone_threshold_range", "municipality_settings", type_="check")
    op.drop_column("municipality_settings", "map_api_key")
    op.drop_column("municipality_settings", "map_background")
    op.drop_column("municipality_settings", "small_zone_threshold")
