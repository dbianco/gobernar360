"""Reading a municipality's configuration (Configuración)."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.platform.models import MunicipalitySettings


def find(db: Session, municipality_id: uuid.UUID) -> MunicipalitySettings | None:
    return db.scalar(
        select(MunicipalitySettings).where(MunicipalitySettings.municipality_id == municipality_id)
    )


def sso_municipality_ids(db: Session) -> set[uuid.UUID]:
    """Municipalities whose administrators allow single sign-on. None do by default."""
    return set(
        db.scalars(
            select(MunicipalitySettings.municipality_id).where(MunicipalitySettings.sso_enabled)
        )
    )
