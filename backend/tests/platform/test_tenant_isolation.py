import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError

from gobernar360.core.db import platform_session, tenant_session
from gobernar360.platform.models import AuditLog
from tests.factories import make_municipality


def _audit_row(municipality_id) -> AuditLog:
    return AuditLog(
        municipality_id=municipality_id,
        action="create",
        entity_type="example",
        entity_id="1",
    )


@pytest.fixture
def two_municipalities_with_one_row_each():
    first = make_municipality("Noetinger")
    second = make_municipality("Saira")
    for municipality in (first, second):
        with tenant_session(municipality.id) as session:
            session.add(_audit_row(municipality.id))
    return first, second


def test_tenant_session_only_sees_its_own_rows(two_municipalities_with_one_row_each):
    first, _ = two_municipalities_with_one_row_each

    with tenant_session(first.id) as session:
        rows = session.scalars(select(AuditLog)).all()

    assert [row.municipality_id for row in rows] == [first.id]


def test_tenant_session_cannot_insert_rows_for_another_municipality():
    first = make_municipality("Noetinger")
    second = make_municipality("Saira")

    with pytest.raises(DBAPIError, match="row-level security"):
        with tenant_session(first.id) as session:
            session.add(_audit_row(second.id))


def test_session_without_tenant_sees_no_tenant_rows(two_municipalities_with_one_row_each):
    with platform_session() as session:
        rows = session.scalars(select(AuditLog)).all()

    assert rows == []


def test_connection_reused_after_a_tenant_session_sees_no_tenant_rows(
    two_municipalities_with_one_row_each,
):
    # The tenant setting is transaction-local; a pooled connection must not keep it.
    first, _ = two_municipalities_with_one_row_each
    with tenant_session(first.id) as session:
        session.scalars(select(AuditLog)).all()

    with platform_session() as session:
        rows = session.scalars(select(AuditLog)).all()

    assert rows == []


def test_app_role_does_not_bypass_rls():
    with platform_session() as session:
        flags = session.execute(
            text("SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user")
        ).one()

    assert tuple(flags) == (False, False)
