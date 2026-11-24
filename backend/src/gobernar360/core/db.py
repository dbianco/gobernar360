"""Database engines, declarative base and tenant-scoped sessions.

Tenant isolation is enforced by PostgreSQL row-level security: every tenant
table carries municipality_id and a policy comparing it with the
transaction-local setting app.municipality_id.
"""

import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from functools import lru_cache

from sqlalchemy import DateTime, Engine, ForeignKey, Uuid, create_engine, func, text
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, declared_attr, mapped_column

from gobernar360.core.config import get_settings

APP_ROLE = "gobernar360_app"
# Reads the published copies and nothing else.
PUBLIC_ROLE = "gobernar360_public"
TENANT_SETTING = "app.municipality_id"


class Base(DeclarativeBase):
    pass


# The column helpers below run once, while the models are imported, where mutation testing
# cannot reach them (hence the pragmas); tests/test_models_match_migrations.py checks the
# schema they build against the migrations.
def uuid_pk() -> Mapped[uuid.UUID]:  # pragma: no mutate block
    return mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


def created_at_column() -> Mapped[datetime]:  # pragma: no mutate block
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TenantMixin:
    """Marks a table as tenant data. Its migration must call enable_tenant_rls()."""

    @declared_attr
    def municipality_id(cls) -> Mapped[uuid.UUID]:  # pragma: no mutate block
        return mapped_column(
            Uuid, ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False, index=True
        )


class AuditMixin:
    @declared_attr
    def created_at(cls) -> Mapped[datetime]:  # pragma: no mutate block
        return created_at_column()

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:  # pragma: no mutate block
        return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @declared_attr
    def created_by(cls) -> Mapped[uuid.UUID | None]:  # pragma: no mutate block
        return mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    @declared_attr
    def updated_by(cls) -> Mapped[uuid.UUID | None]:  # pragma: no mutate block
        return mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


@lru_cache
def get_engine() -> Engine:
    """Engine for the API role, which is subject to row-level security."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_admin_engine() -> Engine:
    """Engine for the owner role. Used by migrations and test setup only."""
    return create_engine(get_settings().admin_database_url, pool_pre_ping=True)


@lru_cache
def get_public_engine() -> Engine:
    """Engine for the public role, which can only read the published copies."""
    return create_engine(get_settings().public_database_url, pool_pre_ping=True)


@contextmanager
def public_session() -> Iterator[Session]:
    """Read-only session of the public role: no tenant, no account data, no writes."""
    with Session(get_public_engine()) as session, session.begin():
        session.execute(text("SET TRANSACTION READ ONLY"))
        yield session


def get_public_db() -> Iterator[Session]:
    """FastAPI dependency for the public routes."""
    with public_session() as session:
        yield session


@contextmanager
def platform_session() -> Iterator[Session]:
    """Session with no tenant set: platform tables only, tenant tables appear empty."""
    with Session(get_engine(), expire_on_commit=False) as session, session.begin():
        yield session


@contextmanager
def tenant_session(municipality_id: uuid.UUID) -> Iterator[Session]:
    """Session whose single transaction is scoped to one municipality.

    The setting is transaction-local, so callers must flush rather than commit:
    after a commit the session would see no tenant rows at all.
    """
    with Session(get_engine(), expire_on_commit=False) as session, session.begin():
        set_tenant(session, municipality_id)
        yield session


def set_tenant(session: Session, municipality_id: uuid.UUID) -> None:
    """Scope the session's current transaction to one municipality."""
    session.execute(
        text("SELECT set_config(:name, :value, true)"),
        {"name": TENANT_SETTING, "value": str(municipality_id)},
    )


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session and one transaction per request."""
    with platform_session() as session:
        yield session


# The two migration helpers run only while migrating, never in a test, so mutation testing
# cannot reach them (hence the pragmas); tests/platform/test_tenant_isolation.py checks
# what they set up on every tenant table.
def grant_app_access(table_name: str) -> None:  # pragma: no mutate block
    """Migration helper: let the API role read and write a table."""
    from alembic import op

    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{table_name}" TO {APP_ROLE}')


def create_public_role() -> None:  # pragma: no mutate block
    """Migration helper: the role of the public routes, when the cluster does not have it.

    Fresh databases get it from db/init; the password here only matches that default and
    must be changed wherever the database is reachable by others.
    """
    from alembic import op

    op.execute(
        f"DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{PUBLIC_ROLE}') "
        f"THEN CREATE ROLE {PUBLIC_ROLE} LOGIN PASSWORD '{PUBLIC_ROLE}'; END IF; END $$"
    )


def enable_public_copy_rls(table_name: str) -> None:  # pragma: no mutate block
    """Migration helper for a table of published copies.

    Anyone allowed to read it sees every row: the public routes run with no municipality
    set. The API role may only write the rows of the municipality its transaction is set to,
    and the public role may only read.
    """
    from alembic import op

    tenant = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')::uuid"
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(f'CREATE POLICY public_read ON "{table_name}" FOR SELECT USING (true)')
    op.execute(
        f'CREATE POLICY tenant_write ON "{table_name}" FOR ALL TO {APP_ROLE} '
        f"USING (municipality_id = {tenant}) WITH CHECK (municipality_id = {tenant})"
    )
    grant_app_access(table_name)
    op.execute(f'GRANT SELECT ON "{table_name}" TO {PUBLIC_ROLE}')


def enable_tenant_rls(table_name: str) -> None:  # pragma: no mutate block
    """Migration helper: restrict a tenant table to the current municipality."""
    from alembic import op

    # A pooled connection that once had the setting reports '' instead of NULL
    # afterwards, and ''::uuid would raise; NULLIF turns both into "no tenant".
    tenant = f"NULLIF(current_setting('{TENANT_SETTING}', true), '')::uuid"
    op.execute(f'ALTER TABLE "{table_name}" ENABLE ROW LEVEL SECURITY')
    op.execute(f'ALTER TABLE "{table_name}" FORCE ROW LEVEL SECURITY')
    op.execute(
        f'CREATE POLICY tenant_isolation ON "{table_name}" '
        f"USING (municipality_id = {tenant}) WITH CHECK (municipality_id = {tenant})"
    )
    grant_app_access(table_name)
