"""Working out again the zones of every record, in bulk."""

import uuid
from dataclasses import dataclass

from sqlalchemy import text

from gobernar360.core.db import tenant_session


@dataclass(frozen=True)
class Reassigned:
    """What was missing and what was left over. Both are zero unless data was loaded around
    the database's triggers, e.g. restored from a backup with them off."""

    added: int
    removed: int


def reassign(municipality_id: uuid.UUID) -> Reassigned:
    with tenant_session(municipality_id) as db:
        row = db.execute(
            text("SELECT added, removed FROM geo_reassign(:municipality_id)"),
            {"municipality_id": municipality_id},
        ).one()
    return Reassigned(row.added, row.removed)
