"""What the team did with each person.

Reading needs viewer access and loading data needs editor access. The
description is reserved text: every response goes through `present`, which
leaves it out for readers below editor level.
"""

import uuid
from collections.abc import Iterable
from datetime import date
from typing import Any

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from sqlalchemy import ColumnElement, select

from gobernar360.dashboards.social.access import Editor, Viewer, reads_reserved_text
from gobernar360.dashboards.social.models import Intervention, InterventionType, SocialPerson
from gobernar360.dashboards.social.schemas import (
    InterventionIn,
    InterventionOut,
    InterventionPatch,
    NamedRef,
    PersonRef,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.api_types import Year
from gobernar360.platform.audit import apply_audit_fields, record_change
from gobernar360.platform.listing import Page, PagingParams, SearchText, every_word, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import create_entity, delete_entity, get_or_404, resolve

router = APIRouter()


def in_year(year: int) -> ColumnElement[bool]:
    return Intervention.date.between(date(year, 1, 1), date(year, 12, 31))


def _for_audit(changes: dict[str, Any]) -> dict[str, Any]:
    """What the audit trail keeps of a change: that the description was written, not its text.

    The trail outlives the record, and reserved text must not survive there.
    """
    if "description" not in changes:
        return changes
    return jsonable_encoder(changes | {"description": "[reserved]"})


def present(ctx: RequestContext, interventions: Iterable[Intervention]) -> list[InterventionOut]:
    """Interventions as this reader may see them."""
    with_text = reads_reserved_text(ctx)
    return [
        InterventionOut(
            id=intervention.id,
            date=intervention.date,
            intervention_type=NamedRef.model_validate(intervention.intervention_type),
            person=PersonRef.model_validate(intervention.person),
            performed_by=intervention.performed_by,
            description=intervention.description if with_text else None,
        )
        for intervention in interventions
    ]


@router.get("/interventions")
def list_interventions(
    ctx: Viewer,
    paging: PagingParams,
    year: Year | None = None,
    intervention_type_id: uuid.UUID | None = None,
    person_id: uuid.UUID | None = None,
    household_id: uuid.UUID | None = None,
    q: SearchText = None,
) -> Page[InterventionOut]:
    query = select(Intervention).order_by(Intervention.date.desc(), Intervention.id)
    if q and q.strip():
        # Who it concerned, by name or document, or its type. Never the reserved text.
        query = (
            query.join(SocialPerson, Intervention.person_id == SocialPerson.id)
            .join(Person, SocialPerson.person_id == Person.id)
            .join(InterventionType, Intervention.intervention_type_id == InterventionType.id)
            .where(
                *every_word(
                    q,
                    Person.first_name,
                    Person.last_name,
                    InterventionType.name,
                    document=Person.dni,
                )
            )
        )
    if year is not None:
        query = query.where(in_year(year))
    if intervention_type_id is not None:
        query = query.where(Intervention.intervention_type_id == intervention_type_id)
    if person_id is not None:
        query = query.where(Intervention.person_id == person_id)
    if household_id is not None:
        query = query.where(
            Intervention.person_id.in_(
                select(SocialPerson.id).where(SocialPerson.household_id == household_id)
            )
        )
    page = page_of(ctx, query, paging)
    return {"items": present(ctx, page["items"]), "total": page["total"]}


@router.post("/interventions", status_code=201)
def create_intervention(payload: InterventionIn, ctx: Editor) -> InterventionOut:
    resolve(ctx, InterventionType, payload.intervention_type_id, "intervention_type_id")
    resolve(ctx, SocialPerson, payload.person_id, "person_id")
    intervention = create_entity(
        ctx, Intervention(**payload.model_dump()), _for_audit(payload.model_dump())
    )
    ctx.db.refresh(intervention)
    return present(ctx, [intervention])[0]


@router.patch("/interventions/{intervention_id}")
def update_intervention(
    intervention_id: uuid.UUID, payload: InterventionPatch, ctx: Editor
) -> InterventionOut:
    intervention = get_or_404(ctx, Intervention, intervention_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(intervention, field, value)
    apply_audit_fields(ctx, intervention, creating=False)
    ctx.db.flush()
    record_change(ctx, "update", intervention, _for_audit(jsonable_encoder(changes)))
    ctx.db.refresh(intervention)
    return present(ctx, [intervention])[0]


@router.delete("/interventions/{intervention_id}", status_code=204)
def delete_intervention(intervention_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, get_or_404(ctx, Intervention, intervention_id))
