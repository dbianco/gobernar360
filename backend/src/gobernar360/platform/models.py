"""Platform tables: municipalities, users, sessions, memberships, grants, audit log, the
people registry, status lights, the history and targets of headline indicators, reports and
publication, and what outgoing email needs: link tokens, the outbox and notifications."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, created_at_column, uuid_pk

MUNICIPALITY_KINDS = ("municipality", "commune")
GRANT_LEVELS = ("viewer", "editor", "admin")
AUDIT_ACTIONS = ("create", "update", "delete")
TOKEN_PURPOSES = ("invitation", "password_reset")
AUTH_METHODS = ("password", "sso")
OUTBOX_STATUSES = ("pending", "sent", "failed")
STATUS_COLORS = ("green", "yellow", "red")
# A report version is a draft until closed; reopening a closed one supersedes it.
REPORT_STATUSES = ("draft", "closed", "superseded")


# The column helpers below run once, while the models are imported, where mutation testing
# cannot reach them (hence the pragmas); tests/test_models_match_migrations.py checks the
# schema they build against the migrations.
def _in(column: str, values: tuple[str, ...]) -> str:  # pragma: no mutate block
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
    # How to reach them; optional, set by the user from their account.
    phone: Mapped[str] = mapped_column(String(50), nullable=False, default="", server_default="")
    # None until the person chooses one through their invitation link.
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_platform_operator: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=true()
    )
    created_at: Mapped[datetime] = created_at_column()


class Session(Base):
    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint(_in("auth_method", AUTH_METHODS), name="auth_method_valid"),)

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
    # A single sign-on session only reaches municipalities that allow single sign-on.
    auth_method: Mapped[str] = mapped_column(
        String(20), nullable=False, default="password", server_default="password"
    )
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


def _text(length: int) -> Mapped[str]:  # pragma: no mutate block
    return mapped_column(String(length), nullable=False, default="", server_default="")


class Person(TenantMixin, AuditMixin, Base):
    """A resident in the municipality's single registry of people.

    Dashboards keep their own data about a person in their own tables and only
    show the people they incorporated.
    """

    __tablename__ = "people"
    __table_args__ = (UniqueConstraint("municipality_id", "dni"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Digits only. People without a known document have none.
    dni: Mapped[str | None] = mapped_column(String(20), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str] = _text(50)
    email: Mapped[str] = _text(200)
    address: Mapped[str] = _text(200)
    neighborhood: Mapped[str] = _text(100)

    @property
    def full_name(self) -> str:
        return f"{self.last_name}, {self.first_name}"


class DashboardStatus(TenantMixin, AuditMixin, Base):
    """The light a dashboard's administrator gave one month: their own reading of how it went."""

    __tablename__ = "dashboard_statuses"
    __table_args__ = (
        UniqueConstraint("municipality_id", "dashboard_key", "year", "month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="month_valid"),
        CheckConstraint(_in("color", STATUS_COLORS), name="color_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    dashboard_key: Mapped[str] = mapped_column(String(50), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(10), nullable=False)


class AccountToken(Base):
    """A single-use link that lets the owner of an email choose the account's password."""

    __tablename__ = "account_tokens"
    __table_args__ = (CheckConstraint(_in("purpose", TOKEN_PURPOSES), name="purpose_valid"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    purpose: Mapped[str] = mapped_column(String(20), nullable=False)
    # Only the SHA-256 of the token in the link is stored.
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = created_at_column()


class PasswordResetRequest(Base):
    """One "forgot my password" request, kept to rate limit them per address.

    Recorded for unknown addresses too, so the limit does not reveal which exist; the
    address itself is stored only as a hash.
    """

    __tablename__ = "password_reset_requests"

    id: Mapped[uuid.UUID] = uuid_pk()
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = created_at_column()


class EmailOutbox(Base):
    """An email waiting to be delivered, written in the transaction that caused it."""

    __tablename__ = "email_outbox"
    __table_args__ = (
        CheckConstraint(_in("status", OUTBOX_STATUSES), name="status_valid"),
        Index("ix_email_outbox_pending", "next_attempt_at", postgresql_where="status = 'pending'"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    to_address: Mapped[str] = mapped_column(String(320), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default="pending"
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The HTML version; `body` is the plain-text one sent alongside it.
    body_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = created_at_column()
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class NotificationOptOut(Base):
    """A kind of notification the user turned off in their account page."""

    __tablename__ = "notification_opt_outs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    kind: Mapped[str] = mapped_column(String(50), primary_key=True)


class NotificationSent(TenantMixin, Base):
    """Marks that an address was already told about one event, so it is never told twice."""

    __tablename__ = "notifications_sent"
    __table_args__ = (UniqueConstraint("municipality_id", "recipient", "kind", "event_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    # Normalised email address: a member's, or one from the municipality's recipient list.
    recipient: Mapped[str] = mapped_column(String(320), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class SsoLogin(Base):
    """A single sign-on attempt between leaving for the provider and coming back."""

    __tablename__ = "sso_logins"

    id: Mapped[uuid.UUID] = uuid_pk()
    # SHA-256 of the `state` sent to the provider; the browser holds the value in a cookie.
    state_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    nonce: Mapped[str] = mapped_column(String(100), nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(128), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = created_at_column()


class MunicipalitySettings(Base):
    """What a municipality's administrators configure for it.

    A platform table, like memberships: sign-in and password recovery read it before
    any municipality is chosen. Routes filter it by the active municipality.
    """

    __tablename__ = "municipality_settings"

    id: Mapped[uuid.UUID] = uuid_pk()
    municipality_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("municipalities.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    # Who receives notification emails. Empty: the administrators of each dashboard.
    notification_emails: Mapped[list[str]] = mapped_column(
        ARRAY(String(320)), nullable=False, default=list, server_default="{}"
    )
    sso_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    updated_at: Mapped[datetime] = created_at_column()
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class EmailTemplate(Base):
    """A municipality's own text for one kind of email; without one, the default is used."""

    __tablename__ = "email_templates"
    __table_args__ = (UniqueConstraint("municipality_id", "key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    municipality_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("municipalities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key: Mapped[str] = mapped_column(String(50), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    # Sanitised HTML with {{placeholders}}.
    html: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = created_at_column()
    updated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# Indicator values: counts, amounts, percentages and 0..1 ratios.
INDICATOR_VALUE = Numeric(18, 4)


class IndicatorSnapshot(TenantMixin, Base):
    """The value a dashboard's headline indicator had at the close of one month.

    Written only by the snapshot command. A null value means the indicator had no value
    that month (e.g. a ratio over nothing); a month without a row was never recorded.
    """

    __tablename__ = "indicator_snapshots"
    __table_args__ = (
        UniqueConstraint("municipality_id", "indicator_key", "year", "month"),
        CheckConstraint("month BETWEEN 1 AND 12", name="month_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    dashboard_key: Mapped[str] = mapped_column(String(50), nullable=False)
    indicator_key: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal | None] = mapped_column(INDICATOR_VALUE, nullable=True)
    # When the value was computed; unchanged when a later run finds the same value.
    taken_at: Mapped[datetime] = created_at_column()


class IndicatorTarget(TenantMixin, AuditMixin, Base):
    """What a dashboard's administrators set out to reach with an indicator in one year."""

    __tablename__ = "indicator_targets"
    __table_args__ = (UniqueConstraint("municipality_id", "indicator_key", "year"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dashboard_key: Mapped[str] = mapped_column(String(50), nullable=False)
    indicator_key: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    value: Mapped[Decimal] = mapped_column(INDICATOR_VALUE, nullable=False)


class MonthlyReport(TenantMixin, AuditMixin, Base):
    """One version of a month's management report.

    Closing freezes `content`: what the report shows never changes afterwards, whatever
    happens to the data it came from. Reopening supersedes the version and starts the next
    one as a draft.
    """

    __tablename__ = "monthly_reports"
    __table_args__ = (
        UniqueConstraint("municipality_id", "year", "month", "version"),
        CheckConstraint("month BETWEEN 1 AND 12", name="month_valid"),
        CheckConstraint(_in("status", REPORT_STATUSES), name="status_valid"),
        CheckConstraint("(status = 'draft') = (content IS NULL)", name="content_when_closed"),
        CheckConstraint("NOT published OR status = 'closed'", name="only_closed_published"),
        # At most one version of a month is not superseded: the draft or the closed one.
        Index(
            "uq_monthly_reports_current",
            "municipality_id",
            "year",
            "month",
            unique=True,
            postgresql_where=text("status <> 'superseded'"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    # A comment per dashboard key, written by the administrator who closes the month.
    comments: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reopened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )


class PublicSettings(TenantMixin, AuditMixin, Base):
    """Whether the municipality has a public page, at which address, and how it masks."""

    __tablename__ = "public_settings"
    __table_args__ = (
        UniqueConstraint("municipality_id"),
        UniqueConstraint("slug"),
        CheckConstraint(
            "small_count_threshold BETWEEN 0 AND 1000", name="small_count_threshold_range"
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=false()
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    # Counts from 1 to this minus one are shown as "fewer than" it.
    small_count_threshold: Mapped[int] = mapped_column(
        Integer, nullable=False, default=5, server_default="5"
    )


class PublishedDashboard(TenantMixin, AuditMixin, Base):
    """A dashboard whose lights are shown on the public page, and whose indicators may be."""

    __tablename__ = "published_dashboards"
    __table_args__ = (UniqueConstraint("municipality_id", "dashboard_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dashboard_key: Mapped[str] = mapped_column(String(50), nullable=False)


class PublishedIndicator(TenantMixin, AuditMixin, Base):
    """An aggregate indicator shown on the public page."""

    __tablename__ = "published_indicators"
    __table_args__ = (UniqueConstraint("municipality_id", "indicator_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    dashboard_key: Mapped[str] = mapped_column(String(50), nullable=False)
    indicator_key: Mapped[str] = mapped_column(String(100), nullable=False)


# Published copies. Written at publication time from the tenant tables; the public routes
# read only these, through a role that cannot read anything else. Removing the site row
# removes everything published under it.


def _site_fk() -> Mapped[uuid.UUID]:
    return mapped_column(
        Uuid,
        ForeignKey("public_sites.municipality_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )


class PublicSite(Base):
    __tablename__ = "public_sites"

    municipality_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("municipalities.id", ondelete="CASCADE"), primary_key=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    small_count_threshold: Mapped[int] = mapped_column(Integer, nullable=False)
    published_at: Mapped[datetime] = created_at_column()


class PublicDashboard(Base):
    __tablename__ = "public_dashboards"
    __table_args__ = (UniqueConstraint("municipality_id", "dashboard_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    municipality_id: Mapped[uuid.UUID] = _site_fk()
    dashboard_key: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # The lights of the last twelve months, oldest first: [{"year", "month", "color"}].
    lights: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)


class PublicIndicator(Base):
    __tablename__ = "public_indicators"
    __table_args__ = (UniqueConstraint("municipality_id", "indicator_key"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    municipality_id: Mapped[uuid.UUID] = _site_fk()
    dashboard_key: Mapped[str] = mapped_column(String(50), nullable=False)
    indicator_key: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    # The evolution as shown to the public, small counts already masked.
    data: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class PublicReport(Base):
    __tablename__ = "public_reports"
    __table_args__ = (UniqueConstraint("municipality_id", "year", "month"),)

    id: Mapped[uuid.UUID] = uuid_pk()
    municipality_id: Mapped[uuid.UUID] = _site_fk()
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    closed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # The public rendition of the report, with small counts masked.
    pdf: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
