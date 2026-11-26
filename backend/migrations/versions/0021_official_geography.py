"""official_geography

Revision ID: 0021
Revises: 0020
Create Date: 2026-11-26 10:00:00

The official geography of each municipality (task 21): where it is in the provincial and
national services, the public facilities drawn on its maps, and where the boundary of a
zone came from.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from gobernar360.core.db import enable_tenant_rls
from gobernar360.platform.geo.types import Geometry

# revision identifiers, used by Alembic.
revision: str = "0021"
down_revision: str | Sequence[str] | None = "0020"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "municipality_settings", sa.Column("idecor_key", sa.String(length=6), nullable=True)
    )
    op.add_column(
        "municipality_settings", sa.Column("conae_layer", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "zone_versions",
        sa.Column("source", sa.String(length=300), server_default="", nullable=False),
    )

    op.create_table(
        "geo_reference_features",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("layer", sa.String(length=20), nullable=False),
        sa.Column("source_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=300), nullable=False),
        sa.Column(
            "properties",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("location", Geometry("Point"), nullable=False),
        sa.Column("source_url", sa.String(length=1000), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.CheckConstraint("layer IN ('health', 'schools')", name="layer_valid"),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        # With the municipality: two neighbours whose radii overlap share facilities.
        sa.UniqueConstraint("municipality_id", "layer", "source_id"),
    )
    op.create_index(
        op.f("ix_geo_reference_features_municipality_id"),
        "geo_reference_features",
        ["municipality_id"],
    )
    enable_tenant_rls("geo_reference_features")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_geo_reference_features_municipality_id"), table_name="geo_reference_features"
    )
    op.drop_table("geo_reference_features")
    op.drop_column("zone_versions", "source")
    op.drop_column("municipality_settings", "conae_layer")
    op.drop_column("municipality_settings", "idecor_key")
