"""Zones and which records belong to them. All are tenant data under row-level security."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from gobernar360.core.db import AuditMixin, Base, TenantMixin, uuid_pk
from gobernar360.platform.geo.types import Geometry


class Zone(TenantMixin, AuditMixin, Base):
    """A neighbourhood or district a municipality defines. Its boundaries are its versions."""

    __tablename__ = "zones"
    __table_args__ = (
        Index(
            "uq_zones_municipality_id_name",
            "municipality_id",
            text("lower(name::text)"),
            unique=True,
            postgresql_where=text("retired_at IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # A zone that is no longer used is kept for the periods it was in force.
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ZoneVersion(TenantMixin, AuditMixin, Base):
    """A zone's boundary during a period. Moving a boundary adds a version; the ones before
    it are never changed, so figures of past periods keep the boundaries they had."""

    __tablename__ = "zone_versions"
    __table_args__ = (
        UniqueConstraint("zone_id", "version"),
        CheckConstraint("valid_to >= valid_from", name="period_ordered"),
        CheckConstraint("ST_IsValid(boundary) AND NOT ST_IsEmpty(boundary)", name="boundary_valid"),
        Index(
            "uq_zone_versions_current",
            "zone_id",
            unique=True,
            postgresql_where=text("valid_to IS NULL"),
        ),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    zone_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("zones.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    boundary: Mapped[dict[str, Any]] = mapped_column(
        Geometry("MultiPolygon"), nullable=False, deferred=True
    )
    valid_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL while this is the zone's boundary.
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Where an official boundary comes from, e.g. the law that approves it. Empty for the
    # ones people drew.
    source: Mapped[str] = mapped_column(String(300), nullable=False, default="", server_default="")

    zone: Mapped[Zone] = relationship(lazy="joined")


class RecordZone(TenantMixin, Base):
    """A record that lies in a zone version. Written only by the database's triggers (see
    the migration), so it cannot drift from the locations and boundaries."""

    __tablename__ = "record_zones"
    __table_args__ = (Index("ix_record_zones_record", "record_table", "record_id"),)

    zone_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("zone_versions.id", ondelete="CASCADE"), primary_key=True
    )
    record_table: Mapped[str] = mapped_column(String(63), primary_key=True)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)


HEALTH, SCHOOLS = "health", "schools"
REFERENCE_LAYERS = (HEALTH, SCHOOLS)


class ReferenceFeature(TenantMixin, Base):
    """A public facility published by an official source, shown on the maps for reference.

    Not a record: it has no zones, nobody edits it, and each import of its layer replaces it
    (`geo/reference_import.py`). It says nothing about any person.
    """

    __tablename__ = "geo_reference_features"
    __table_args__ = (
        UniqueConstraint("municipality_id", "layer", "source_id"),
        CheckConstraint(f"layer IN {REFERENCE_LAYERS}", name="layer_valid"),
    )

    id: Mapped[uuid.UUID] = uuid_pk()
    layer: Mapped[str] = mapped_column(String(20), nullable=False)
    # What the source calls it, to recognise it in the next import.
    source_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    properties: Mapped[dict[str, str]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    location: Mapped[dict[str, Any]] = mapped_column(
        Geometry("Point"), nullable=False, deferred=True
    )
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
