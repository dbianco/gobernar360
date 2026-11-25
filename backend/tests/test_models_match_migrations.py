"""The models and the migrations describe the same schema.

Migrations are hand-edited (see CLAUDE.md), so nothing else notices when a model gains a
column, an index or a constraint that no migration creates, or the other way round.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from gobernar360.core.db import Base, get_admin_engine
from gobernar360.platform.geo.types import is_ours


def test_the_migrated_database_has_exactly_what_the_models_declare():
    with get_admin_engine().connect() as connection:
        context = MigrationContext.configure(
            connection,
            opts={
                "compare_type": True,
                "compare_server_default": True,
                "include_object": is_ours,
            },
        )
        differences = compare_metadata(context, Base.metadata)

    assert differences == []


def test_only_the_table_of_postgis_is_left_out_of_the_comparison():
    def ours(kind, name):
        return is_ours(None, name, kind, True, None)

    assert ours("table", "spatial_ref_sys") is False
    assert ours("table", "zones") is True
    assert ours("column", "spatial_ref_sys") is True
    assert ours("index", "zones") is True
