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
TENANT_SETTING = "app.municipality_id"


class Base(DeclarativeBase):
    pass


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4, server_default=text("gen_random_uuid()")
    )


def created_at_column() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class TenantMixin:
    """Marks a table as tenant data. Its migration must call enable_tenant_rls()."""

    @declared_attr
    def municipality_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(
            Uuid, ForeignKey("municipalities.id", ondelete="RESTRICT"), nullable=False, index=True
        )


class AuditMixin:
    @declared_attr
    def created_at(cls) -> Mapped[datetime]:
        return created_at_column()

    @declared_attr
    def updated_at(cls) -> Mapped[datetime]:
        return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    @declared_attr
    def created_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    @declared_attr
    def updated_by(cls) -> Mapped[uuid.UUID | None]:
        return mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)


@lru_cache
def get_engine() -> Engine:
    """Engine for the API role, which is subject to row-level security."""
    return create_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_admin_engine() -> Engine:
    """Engine for the owner role. Used by migrations and test setup only."""
    return create_engine(get_settings().admin_database_url, pool_pre_ping=True)


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
        session.execute(
            text("SELECT set_config(:name, :value, true)"),
            {"name": TENANT_SETTING, "value": str(municipality_id)},
        )
        yield session


def grant_app_access(table_name: str) -> None:
    """Migration helper: let the API role read and write a table."""
    from alembic import op

    op.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{table_name}" TO {APP_ROLE}')


def enable_tenant_rls(table_name: str) -> None:
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
