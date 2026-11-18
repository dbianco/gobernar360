"""Records who created and changed tenant data."""

from datetime import UTC, datetime
from typing import Any

from gobernar360.platform.access import RequestContext
from gobernar360.platform.models import AuditLog


def record_change(
    ctx: RequestContext, action: str, entity: Any, changes: dict[str, Any] | None = None
) -> None:
    """Append an audit entry for `entity`, which must already have its id."""
    ctx.db.add(
        AuditLog(
            municipality_id=ctx.municipality_id,
            user_id=ctx.user.id,
            action=action,
            entity_type=entity.__tablename__,
            entity_id=str(entity.id),
            changes=changes,
        )
    )


def apply_audit_fields(ctx: RequestContext, entity: Any, creating: bool) -> None:
    if creating:
        entity.created_by = ctx.user.id
    entity.updated_by = ctx.user.id
    entity.updated_at = datetime.now(UTC)
