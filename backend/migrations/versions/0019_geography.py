"""geography

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-24 12:00:00

Zones with versions, the location of projects, social households and economic actors, and
the functions and triggers that keep every record's zones up to date.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from gobernar360.core.db import enable_tenant_rls
from gobernar360.platform.geo.located import LINE, POINT, disable_location, enable_location
from gobernar360.platform.geo.types import Geometry

# revision identifiers, used by Alembic.
revision: str = "0019"
down_revision: str | Sequence[str] | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCATED_TABLES = {
    "projects_projects": (POINT, LINE),
    "social_households": (POINT,),
    "economic_actors": (POINT,),
}

# The functions run as whoever changes the data, so row-level security applies to the API;
# they also filter by municipality themselves, because the owner role bypasses it.

# A line that only touches a zone's border at a point does not cross it; a street that runs
# along the border between two zones belongs to both. Asked as a relation (some length of
# the line inside the zone, or along its border) instead of measuring ST_Intersection:
# GEOS 3.9, which postgis/postgis:16-3.4 ships, answers an empty intersection for a line
# lying on the border.
BELONGS = """
CREATE FUNCTION geo_belongs(record geometry, boundary geometry) RETURNS boolean
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT CASE
        WHEN NOT ST_Intersects(record, boundary) THEN false
        WHEN ST_Dimension(record) = 0 THEN true
        ELSE ST_Relate(record, boundary, '1********')
            OR ST_Relate(record, boundary, '*1*******')
    END
$$
"""

# A boundary change and a location change that overlap in time would each miss the other.
# Boundary changes take the lock alone; location changes share it among themselves.
LOCK_KEY = """
CREATE FUNCTION geo_lock_key(municipality uuid) RETURNS bigint
LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
    SELECT hashtextextended('geo:' || municipality::text, 0)
$$
"""

ASSIGN_RECORD = """
CREATE FUNCTION geo_assign_record() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
BEGIN
    IF TG_OP <> 'INSERT' THEN
        PERFORM pg_advisory_xact_lock_shared(geo_lock_key(OLD.municipality_id));
        DELETE FROM record_zones
        WHERE record_table = TG_TABLE_NAME AND record_id = OLD.id
            AND municipality_id = OLD.municipality_id;
    END IF;
    IF TG_OP <> 'DELETE' AND NEW.location IS NOT NULL THEN
        PERFORM pg_advisory_xact_lock_shared(geo_lock_key(NEW.municipality_id));
        INSERT INTO record_zones (municipality_id, zone_version_id, record_table, record_id)
        SELECT NEW.municipality_id, version.id, TG_TABLE_NAME, NEW.id
        FROM zone_versions AS version
        WHERE version.municipality_id = NEW.municipality_id
            AND version.boundary && NEW.location
            AND geo_belongs(NEW.location, version.boundary);
    END IF;
    RETURN NULL;
END
$$
"""

# The located tables are the ones with the trigger, so a dashboard only has to call
# enable_location() for its records to follow the zones.
LOCATED = """
CREATE FUNCTION geo_located_tables() RETURNS SETOF name
LANGUAGE sql STABLE AS $$
    SELECT class.relname
    FROM pg_trigger AS trigger JOIN pg_class AS class ON class.oid = trigger.tgrelid
    WHERE trigger.tgname = 'assign_zones' AND NOT trigger.tgisinternal
$$
"""

ASSIGN_VERSION = """
CREATE FUNCTION geo_assign_version() RETURNS trigger
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    located name;
BEGIN
    PERFORM pg_advisory_xact_lock(geo_lock_key(NEW.municipality_id));
    DELETE FROM record_zones WHERE zone_version_id = NEW.id;
    FOR located IN SELECT geo_located_tables() LOOP
        EXECUTE format(
            'INSERT INTO record_zones (municipality_id, zone_version_id, record_table, record_id)
             SELECT record.municipality_id, $1, %L, record.id
             FROM %I AS record
             WHERE record.municipality_id = $2
                AND record.location && $3
                AND geo_belongs(record.location, $3)',
            located, located
        ) USING NEW.id, NEW.municipality_id, NEW.boundary;
    END LOOP;
    RETURN NULL;
END
$$
"""

REASSIGN = """
CREATE FUNCTION geo_reassign(municipality uuid, OUT added bigint, OUT removed bigint)
LANGUAGE plpgsql SET search_path = public, pg_temp AS $$
DECLARE
    located name;
    affected bigint;
BEGIN
    added := 0;
    PERFORM pg_advisory_xact_lock(geo_lock_key(municipality));
    -- Of records that are no longer located at all.
    DELETE FROM record_zones
    WHERE municipality_id = municipality
        AND record_table::name NOT IN (SELECT geo_located_tables());
    GET DIAGNOSTICS removed = ROW_COUNT;
    FOR located IN SELECT geo_located_tables() LOOP
        EXECUTE format(
            'DELETE FROM record_zones AS assigned
             WHERE assigned.municipality_id = $1 AND assigned.record_table = %L
                AND NOT EXISTS (
                    SELECT FROM %I AS record, zone_versions AS version
                    WHERE record.id = assigned.record_id
                        AND record.municipality_id = $1
                        AND version.id = assigned.zone_version_id
                        AND geo_belongs(record.location, version.boundary)
                )',
            located, located
        ) USING municipality;
        GET DIAGNOSTICS affected = ROW_COUNT;
        removed := removed + affected;
        EXECUTE format(
            'INSERT INTO record_zones (municipality_id, zone_version_id, record_table, record_id)
             SELECT $1, version.id, %L, record.id
             FROM %I AS record, zone_versions AS version
             WHERE record.municipality_id = $1 AND version.municipality_id = $1
                AND record.location && version.boundary
                AND geo_belongs(record.location, version.boundary)
             ON CONFLICT DO NOTHING',
            located, located
        ) USING municipality;
        GET DIAGNOSTICS affected = ROW_COUNT;
        added := added + affected;
    END LOOP;
END
$$
"""


def _audited_columns() -> list[sa.Column]:
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


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    for function in (BELONGS, LOCK_KEY, LOCATED):
        op.execute(function)

    op.create_table(
        "zones",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        *_audited_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_zones_municipality_id"), "zones", ["municipality_id"])
    op.create_index(
        "uq_zones_municipality_id_name",
        "zones",
        ["municipality_id", sa.text("lower(name::text)")],
        unique=True,
        postgresql_where=sa.text("retired_at IS NULL"),
    )

    op.create_table(
        "zone_versions",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("zone_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("boundary", Geometry("MultiPolygon"), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        *_audited_columns(),
        sa.CheckConstraint("valid_to >= valid_from", name="period_ordered"),
        sa.CheckConstraint(
            "ST_IsValid(boundary) AND NOT ST_IsEmpty(boundary)", name="boundary_valid"
        ),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("zone_id", "version"),
    )
    op.create_index(op.f("ix_zone_versions_municipality_id"), "zone_versions", ["municipality_id"])
    op.create_index(op.f("ix_zone_versions_zone_id"), "zone_versions", ["zone_id"])
    op.create_index(
        "uq_zone_versions_current",
        "zone_versions",
        ["zone_id"],
        unique=True,
        postgresql_where=sa.text("valid_to IS NULL"),
    )

    op.create_table(
        "record_zones",
        sa.Column("zone_version_id", sa.Uuid(), nullable=False),
        sa.Column("record_table", sa.String(length=63), nullable=False),
        sa.Column("record_id", sa.Uuid(), nullable=False),
        sa.Column("municipality_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["municipality_id"], ["municipalities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["zone_version_id"], ["zone_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("zone_version_id", "record_table", "record_id"),
    )
    op.create_index(op.f("ix_record_zones_municipality_id"), "record_zones", ["municipality_id"])
    op.create_index("ix_record_zones_record", "record_zones", ["record_table", "record_id"])

    for table in ("zones", "zone_versions", "record_zones"):
        enable_tenant_rls(table)

    for function in (ASSIGN_RECORD, ASSIGN_VERSION, REASSIGN):
        op.execute(function)
    op.execute(
        "CREATE TRIGGER assign_records AFTER INSERT OR UPDATE OF boundary, municipality_id "
        "ON zone_versions FOR EACH ROW EXECUTE FUNCTION geo_assign_version()"
    )
    for table, kinds in LOCATED_TABLES.items():
        enable_location(table, kinds)


def downgrade() -> None:
    """Downgrade schema."""
    for table in LOCATED_TABLES:
        disable_location(table)
    op.drop_table("record_zones")
    op.drop_table("zone_versions")
    op.drop_table("zones")
    op.execute("DROP FUNCTION geo_reassign(uuid)")
    op.execute("DROP FUNCTION geo_assign_version()")
    op.execute("DROP FUNCTION geo_assign_record()")
    op.execute("DROP FUNCTION geo_located_tables()")
    op.execute("DROP FUNCTION geo_lock_key(uuid)")
    op.execute("DROP FUNCTION geo_belongs(geometry, geometry)")
    # PostGIS stays: the database may have come with it, and other extensions may need it.
