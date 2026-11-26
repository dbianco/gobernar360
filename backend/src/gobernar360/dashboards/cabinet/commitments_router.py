"""The commitments taken in meetings, as the cabinet follows them.

Their state, notes and history are the platform's (`platform.commitments_router`), as those
of any commitment. What was agreed is the cabinet's: it is fixed once its meeting closes.
"""

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter
from sqlalchemy import Select, select

from gobernar360.core.errors import commitment_finished, not_found
from gobernar360.dashboards.cabinet.access import Editor, Viewer
from gobernar360.dashboards.cabinet.meetings_router import is_being_agreed, open_item
from gobernar360.dashboards.cabinet.models import Taken
from gobernar360.dashboards.cabinet.present import present_commitment, present_commitments
from gobernar360.dashboards.cabinet.schemas import CommitmentOut
from gobernar360.platform import commitments, subjects
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import Today
from gobernar360.platform.commitment_models import Commitment
from gobernar360.platform.commitment_rules import OPEN
from gobernar360.platform.commitment_schemas import CommitmentPatch, StateFilter
from gobernar360.platform.listing import Page, PagingParams, SearchText, page_of
from gobernar360.platform.tenant_crud import delete_entity, update_entity

router = APIRouter()


def query_taken(
    today: date,
    q: str | None = None,
    state: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> Select[Any]:
    """Commitments taken in meetings matching the filters, as `query_commitments` orders them."""
    query = commitments.query_commitments(today, q, state).join(
        Taken, Taken.commitment_id == Commitment.id
    )
    return query if owner_id is None else query.where(Commitment.owner_id == owner_id)


def _load(ctx: RequestContext, commitment_id: uuid.UUID) -> tuple[Commitment, Taken]:
    taken = ctx.db.scalar(select(Taken).where(Taken.commitment_id == commitment_id))
    if taken is None:
        raise not_found()
    return commitments.load(ctx, commitment_id, lock=True), taken


@router.get("/commitments")
def list_commitments(
    ctx: Viewer,
    today: Today,
    paging: PagingParams,
    q: SearchText = None,
    state: StateFilter | None = None,
    owner_id: uuid.UUID | None = None,
) -> Page[CommitmentOut]:
    page = page_of(ctx, query_taken(today, q, state, owner_id), paging)
    return Page[CommitmentOut](
        items=present_commitments(ctx, page["items"], today), total=page["total"]
    )


@router.patch("/commitments/{commitment_id}")
def update_commitment(
    commitment_id: uuid.UUID, payload: CommitmentPatch, ctx: Editor, today: Today
) -> CommitmentOut:
    """Correct what was agreed while its meeting is open; the rest, while it is open itself.

    A date changed while the meeting is open is what was agreed. Later it is a new date, and
    the figures keep the one agreed.
    """
    commitment, taken = _load(ctx, commitment_id)
    fields = payload.model_dump(exclude_unset=True)
    text = {name: fields.pop(name) for name in ("description", "subject") if name in fields}
    if text:
        # Locks the meeting, so it cannot be closed with the text half changed.
        open_item(ctx, taken.item_id)
        if commitment.state != OPEN:
            raise commitment_finished()
        if "subject" in text:
            text["subject"] = payload.subject and subjects.resolve(ctx, payload.subject, today)
        update_entity(ctx, commitment, text)
    agreed = "due_date" in fields and is_being_agreed(ctx, taken.item_id)
    commitments.reschedule(ctx, commitment, **fields, agreed=agreed)
    ctx.db.refresh(commitment)
    return present_commitment(ctx, commitment, today)


@router.delete("/commitments/{commitment_id}", status_code=204)
def delete_commitment(commitment_id: uuid.UUID, ctx: Editor) -> None:
    """Remove one recorded by mistake, while its meeting is open. Later it is dropped."""
    commitment, taken = _load(ctx, commitment_id)
    open_item(ctx, taken.item_id)
    delete_entity(ctx, commitment)
