"""The models and the migrations describe the same schema.

Migrations are hand-edited (see CLAUDE.md), so nothing else notices when a model gains a
column, an index or a constraint that no migration creates, or the other way round.
"""

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext

from gobernar360.core.db import Base, get_admin_engine


def test_the_migrated_database_has_exactly_what_the_models_declare():
    with get_admin_engine().connect() as connection:
        context = MigrationContext.configure(
            connection, opts={"compare_type": True, "compare_server_default": True}
        )
        differences = compare_metadata(context, Base.metadata)

    assert differences == []
