"""Reading a municipality's configuration (Configuración)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.platform.geo import backgrounds
from gobernar360.platform.geo.backgrounds import Background
from gobernar360.platform.models import DEFAULT_SMALL_ZONE_THRESHOLD, MunicipalitySettings


def find(db: Session, municipality_id: uuid.UUID) -> MunicipalitySettings | None:
    return db.scalar(
        select(MunicipalitySettings).where(MunicipalitySettings.municipality_id == municipality_id)
    )


def small_zone_threshold(db: Session, municipality_id: uuid.UUID) -> int:
    row = find(db, municipality_id)
    return row.small_zone_threshold if row else DEFAULT_SMALL_ZONE_THRESHOLD


def background_in_use(row: MunicipalitySettings | None) -> Background:
    """The background of the municipality's maps."""
    if row is None:
        return backgrounds.in_use(backgrounds.DEFAULT)
    return backgrounds.in_use(row.map_background, row.conae_layer)


def sso_municipality_ids(db: Session) -> set[uuid.UUID]:
    """Municipalities whose administrators allow single sign-on. None do by default."""
    return set(
        db.scalars(
            select(MunicipalitySettings.municipality_id).where(MunicipalitySettings.sso_enabled)
        )
    )
