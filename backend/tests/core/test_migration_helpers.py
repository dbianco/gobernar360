"""What a migration gets from the helpers of `core/db.py`, on a table made for the test and
rolled back with it."""

import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from gobernar360.core.db import (
    APP_ROLE,
    PUBLIC_ROLE,
    TENANT_SETTING,
    create_public_role,
    enable_public_copy_rls,
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


def privileges(connection, role: str = APP_ROLE) -> set[str]:
    return set(
        connection.scalars(
            text(
                "SELECT privilege_type FROM information_schema.role_table_grants "
                "WHERE table_name = 'helper rows' AND grantee = :role"
            ),
            {"role": role},
        )
    )


def rows_seen(connection, municipality_id, role: str = APP_ROLE) -> list[int]:
    """The rows that role sees with that tenant set (None: none, '': once set)."""
    connection.execute(text(f"SET LOCAL ROLE {role}"))
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


def test_published_copies_are_read_by_all_and_written_by_their_municipality(connection):
    ours, theirs = uuid.uuid4(), uuid.uuid4()
    enable_public_copy_rls("helper rows")
    connection.execute(
        text('INSERT INTO "helper rows" VALUES (1, :ours), (2, :theirs)'),
        {"ours": ours, "theirs": theirs},
    )

    assert rows_seen(connection, None, PUBLIC_ROLE) == [1, 2]
    assert rows_seen(connection, ours) == [1, 2]
    assert privileges(connection, PUBLIC_ROLE) == {"SELECT"}
    assert privileges(connection) == {"SELECT", "INSERT", "UPDATE", "DELETE"}

    # `ours` is still the municipality of this transaction.
    connection.execute(text(f"SET LOCAL ROLE {APP_ROLE}"))
    changed = connection.execute(text('UPDATE "helper rows" SET id = id + 10'))
    assert changed.rowcount == 1
    with pytest.raises(ProgrammingError, match="row-level security"), connection.begin_nested():
        connection.execute(
            text('INSERT INTO "helper rows" VALUES (3, :theirs)'), {"theirs": theirs}
        )
    connection.execute(text("RESET ROLE"))
    assert rows_seen(connection, None, PUBLIC_ROLE) == [2, 11]


def test_row_security_of_published_copies_binds_their_owner_too(connection):
    enable_public_copy_rls("helper rows")

    flags = connection.execute(
        text(
            "SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'helper rows'"
        )
    ).one()

    assert tuple(flags) == (True, True)


def test_the_public_role_is_created_once(connection, monkeypatch):
    """Under another name: the real one belongs to the whole cluster."""
    name = f"public_{uuid.uuid4().hex}"
    monkeypatch.setattr("gobernar360.core.db.PUBLIC_ROLE", name)
    found = text("SELECT rolcanlogin, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = :name")
    assert connection.execute(found, {"name": name}).all() == []

    create_public_role()
    create_public_role()

    assert [tuple(row) for row in connection.execute(found, {"name": name})] == [
        (True, False, False)
    ]
