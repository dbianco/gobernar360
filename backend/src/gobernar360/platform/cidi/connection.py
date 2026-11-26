"""A municipality's connection to CiDi, which it obtains when its adhesion is approved.

Until the Province's specification says which data it is made of, it is a set of named
values. Three are plain; anything else, such as a key, a certificate or a token, is a secret.
Secrets go in and never come out of the API: they are stored encrypted, and only what
delivers notices reads them (`load`).
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core import secrets
from gobernar360.platform.resident_notice_models import (
    APPROVED,
    CidiConnection,
    CidiConnectionValue,
)

SYSTEM_NAME, PUBLICATION_URL, CONTACT = "system_name", "publication_url", "contact"
PLAIN_VALUES = (SYSTEM_NAME, PUBLICATION_URL, CONTACT)
# What is missing when the adhesion is not approved yet.
ADHESION = "adhesion"


@dataclass(frozen=True)
class Connection:
    """Everything there is to connect with, decrypted. Never leaves the delivery command."""

    municipality_id: uuid.UUID
    values: dict[str, str]
    # Left out of its text, so that no log ever has them.
    secrets: dict[str, str] = field(repr=False)


def find(db: Session) -> CidiConnection | None:
    return db.scalar(select(CidiConnection))


def stored(db: Session) -> dict[str, CidiConnectionValue]:
    rows = db.scalars(select(CidiConnectionValue).order_by(CidiConnectionValue.name))
    return {row.name: row for row in rows}


def missing(adhesion_state: str, plain: dict[str, str]) -> list[str]:
    """What the municipality still needs before choosing CiDi as a channel."""
    lacking = [] if adhesion_state == APPROVED else [ADHESION]
    return lacking + [name for name in PLAIN_VALUES if not plain.get(name)]


def _owner(municipality_id: uuid.UUID, name: str) -> str:
    return f"{municipality_id}:{name}"


def set_secret(
    row: CidiConnectionValue, municipality_id: uuid.UUID, value: str, now: datetime
) -> None:
    row.value, row.encrypted = None, secrets.encrypt(value, _owner(municipality_id, row.name))
    row.set_at = now


def load(db: Session, municipality_id: uuid.UUID) -> Connection:
    """For the delivery command only. `db` must be scoped to the municipality."""
    plain: dict[str, str] = {}
    secret: dict[str, str] = {}
    for name, row in stored(db).items():
        if row.encrypted is None:
            plain[name] = row.value
        else:
            secret[name] = secrets.decrypt(row.encrypted, _owner(municipality_id, name))
    return Connection(municipality_id, plain, secret)
