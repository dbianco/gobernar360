"""Platform tables: municipalities, users, sessions, memberships, grants and audit log."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    false,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import Base, TenantMixin, created_at_column, uuid_pk

MUNICIPALITY_KINDS = ("municipality", "commune")
GRANT_LEVELS = ("viewer", "editor", "admin")
AUDIT_ACTIONS = ("create", "update", "delete")


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


class Municipality(Base):
    __tablename__ = "municipalities"
    __table_args__ = (CheckConstraint(_in("kind", MUNICIPALITY_KINDS), name="kind_valid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Always stored normalised (trimmed, lowercase).
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True)
    full_name: Mapped[str] = mapped_column(String(200), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_platform_operator: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = created_at_column()


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = uuid_pk()
    # Only the SHA-256 of the cookie token is stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    active_municipality_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("municipalities.id", ondelete="SET NULL"), nullable=True
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "municipality_id"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    municipality_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("municipalities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_admin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )

    user: Mapped[User] = relationship(lazy="joined")
    municipality: Mapped[Municipality] = relationship(lazy="joined")
    grants: Mapped[list["DashboardGrant"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin"
    )


class MunicipalityDashboard(Base):
    """A dashboard enabled for a municipality by the platform operator."""

    __tablename__ = "municipality_dashboards"

    municipality_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("municipalities.id", ondelete="CASCADE"), primary_key=True
    )
    dashboard_key: Mapped[str] = mapped_column(String(50), primary_key=True)


class DashboardGrant(Base):
    __tablename__ = "dashboard_grants"
    __table_args__ = (CheckConstraint(_in("level", GRANT_LEVELS), name="level_valid"),)

    membership_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("memberships.id", ondelete="CASCADE"), primary_key=True
    )
    dashboard_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    level: Mapped[str] = mapped_column(String(20), nullable=False)


class AuditLog(TenantMixin, Base):
    __tablename__ = "audit_log"
    __table_args__ = (CheckConstraint(_in("action", AUDIT_ACTIONS), name="action_valid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    # Null for changes made by the system rather than a signed-in user.
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    changes: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = created_at_column()
