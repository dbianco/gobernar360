"""Create, update and delete helpers shared by dashboard modules.

They work on the request's tenant-scoped session, so rows of other
municipalities are simply not found, and they write the audit trail.
"""

import uuid
from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.exc import IntegrityError

from gobernar360.core.errors import in_use, invalid_reference, not_found
from gobernar360.platform.access import RequestContext
from gobernar360.platform.audit import apply_audit_fields, record_change


def get_or_404[T](ctx: RequestContext, model: type[T], entity_id: uuid.UUID) -> T:
    entity = ctx.db.get(model, entity_id)
    if entity is None:
        raise not_found()
    return entity


def resolve[T](ctx: RequestContext, model: type[T], entity_id: uuid.UUID, field: str) -> T:
    """Load a row referenced by a request body.

    Foreign keys are not subject to row-level security, so every referenced id
    must be checked here; otherwise a row could point at another municipality's data.
    """
    entity = ctx.db.get(model, entity_id)
    if entity is None:
        raise invalid_reference(f"{field} does not reference an existing record.")
    return entity


def create_entity[T](ctx: RequestContext, entity: T, changes: dict[str, Any]) -> T:
    entity.municipality_id = ctx.municipality_id
    apply_audit_fields(ctx, entity, creating=True)
    ctx.db.add(entity)
    ctx.db.flush()
    record_change(ctx, "create", entity, jsonable_encoder(changes))
    return entity


def update_entity[T](ctx: RequestContext, entity: T, changes: dict[str, Any]) -> T:
    for field, value in changes.items():
        setattr(entity, field, value)
    apply_audit_fields(ctx, entity, creating=False)
    ctx.db.flush()
    record_change(ctx, "update", entity, jsonable_encoder(changes))
    return entity


def delete_entity(ctx: RequestContext, entity: Any) -> None:
    record_change(ctx, "delete", entity)
    ctx.db.delete(entity)
    try:
        ctx.db.flush()
    except IntegrityError as error:
        # The request's transaction is rolled back, which also drops the audit entry.
        raise in_use() from error
