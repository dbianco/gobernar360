"""What a migration gets from `enable_tenant_rls` and `grant_app_access`, on a table made for
the test and rolled back with it."""

import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from gobernar360.core.db import (
    APP_ROLE,
    TENANT_SETTING,
    enable_tenant_rls,
    get_admin_engine,
    grant_app_access,
)


@pytest.fixture
def connection():
    with get_admin_engine().connect() as connection:
        transaction = connection.begin()
        with Operations.context(MigrationContext.configure(connection)):
            connection.execute(
                text('CREATE TABLE "helper rows" (id int, municipality_id uuid NOT NULL)')
            )
            yield connection
        transaction.rollback()


def privileges(connection) -> set[str]:
    return set(
        connection.scalars(
            text(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE table_name = 'helper rows' AND grantee = :role"
            ),
            {"role": APP_ROLE},
        )
    )


def rows_seen(connection, municipality_id) -> list[int]:
    """The rows the API's role sees with that tenant set (None: none, '': once set)."""
    connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    if municipality_id is not None:
        connection.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": TENANT_SETTING, "value": str(municipality_id)},
        )
    seen = list(connection.scalars(text('SELECT id FROM "helper rows" ORDER BY id')))
    connection.execute(text("RESET ROLE"))
    return seen


def test_a_table_is_closed_to_the_api_until_it_is_granted(connection):
    assert privileges(connection) == set()

    grant_app_access("helper rows")

    assert privileges(connection) == {"SELECT", "INSERT", "UPDATE", "DELETE"}
    # A platform table: no policy hides its rows.
    assert not connection.scalar(
        text("SELECT relrowsecurity FROM pg_class WHERE relname = 'helper rows'")
    )


def test_a_tenant_table_shows_only_the_rows_of_the_municipality_set(connection):
    ours, theirs = uuid.uuid4(), uuid.uuid4()
    enable_tenant_rls("helper rows")
    connection.execute(
        text('INSERT INTO "helper rows" VALUES (1, :ours), (2, :theirs), (3, :ours)'),
        {"ours": ours, "theirs": theirs},
    )

    assert rows_seen(connection, None) == []
    assert rows_seen(connection, ours) == [1, 3]
    assert rows_seen(connection, theirs) == [2]
    # What a pooled connection that once had the setting reports.
    assert rows_seen(connection, "") == []
    assert privileges(connection) == {"SELECT", "INSERT", "UPDATE", "DELETE"}


def test_row_security_binds_the_owner_of_the_table_too(connection):
    enable_tenant_rls("helper rows")

    flags = connection.execute(
        text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'helper rows'"
        )
    ).one()

    assert tuple(flags) == (True, True)
