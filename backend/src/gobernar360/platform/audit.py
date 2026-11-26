"""Records who created and changed tenant data."""

import uuid
from datetime import UTC, datetime
from typing import Any

from gobernar360.platform.access import RequestContext
from gobernar360.platform.models import AuditLog


def _author(ctx: RequestContext) -> uuid.UUID | None:
    """Who is changing the data; None for a command (`access.system_context`)."""
    return ctx.user.id if ctx.user else None


def record_change(
    ctx: RequestContext, action: str, entity: Any, changes: dict[str, Any] | None = None
) -> None:
    """Append an audit entry for `entity`, which must already have its id."""
    ctx.db.add(
        AuditLog(
            municipality_id=ctx.municipality_id,
            user_id=_author(ctx),
            action=action,
            entity_type=entity.__tablename__,
            entity_id=str(entity.id),
            changes=changes,
        )
    )


def apply_audit_fields(ctx: RequestContext, entity: Any, creating: bool) -> None:
    if creating:
        entity.created_by = _author(ctx)
    entity.updated_by = _author(ctx)
    entity.updated_at = datetime.now(UTC)
