"""Commitments and their follow-up.

Viewers read. Editors change what was agreed and record what came of it; whoever owes a
commitment may add progress notes to it whatever their level. What was agreed is fixed once
its meeting closes; its owner and due date can still change, which its history records.
"""

import uuid
from datetime import date
from typing import Any, Literal

from fastapi import APIRouter
from sqlalchemy import Select, case, select

from gobernar360.core.errors import commitment_finished, forbidden, validation_error
from gobernar360.dashboards.cabinet import members
from gobernar360.dashboards.cabinet.access import KEY, Editor, Viewer
from gobernar360.dashboards.cabinet.meetings_router import open_item
from gobernar360.dashboards.cabinet.models import Commitment, ProgressEntry
from gobernar360.dashboards.cabinet.present import present_commitment, present_commitments
from gobernar360.dashboards.cabinet.rules import DONE, OPEN, OVERDUE
from gobernar360.dashboards.cabinet.schemas import (
    CommitmentDetail,
    CommitmentOut,
    CommitmentPatch,
    EffectiveState,
    HistoryEntry,
    NoteIn,
    StateIn,
)
from gobernar360.platform import subjects
from gobernar360.platform.access import AccessLevel, RequestContext, effective_level
from gobernar360.platform.clock import Today
from gobernar360.platform.listing import Page, PagingParams, SearchText, every_word, page_of
from gobernar360.platform.models import User
from gobernar360.platform.tenant_crud import create_entity, delete_entity, get_or_404, update_entity

router = APIRouter()

# What to list: one effective state, or every commitment still to be delivered.
StateFilter = EffectiveState | Literal["pending"]


def query_commitments(
    today: date,
    q: str | None = None,
    state: str | None = None,
    owner_id: uuid.UUID | None = None,
) -> Select[Any]:
    """Commitments matching the filters: those still open first, by due date."""
    query = (
        select(Commitment)
        .join(User, User.id == Commitment.owner_id)
        .where(*every_word(q, Commitment.description, User.full_name))
        .order_by(
            case((Commitment.state == OPEN, 0), else_=1),
            Commitment.due_date,
            Commitment.created_at,
            Commitment.id,
        )
    )
    if owner_id is not None:
        query = query.where(Commitment.owner_id == owner_id)
    if state == "pending":
        query = query.where(Commitment.state == OPEN)
    elif state == OVERDUE:
        query = query.where(Commitment.state == OPEN, Commitment.due_date < today)
    elif state == OPEN:
        query = query.where(Commitment.state == OPEN, Commitment.due_date >= today)
    elif state is not None:
        query = query.where(Commitment.state == state)
    return query


def _detail(ctx: RequestContext, commitment: Commitment, today: date) -> CommitmentDetail:
    ctx.db.refresh(commitment)
    rows = ctx.db.execute(
        select(ProgressEntry, User.full_name)
        .outerjoin(User, User.id == ProgressEntry.created_by)
        .where(ProgressEntry.commitment_id == commitment.id)
        .order_by(ProgressEntry.created_at.desc(), ProgressEntry.id)
    )
    return CommitmentDetail(
        **present_commitment(ctx, commitment, today).model_dump(),
        history=[
            HistoryEntry(
                id=entry.id,
                at=entry.created_at,
                author=author,
                note=entry.note,
                changes=entry.changes,
            )
            for entry, author in rows
        ],
    )


def _record(
    ctx: RequestContext, commitment: Commitment, note: str = "", changes: dict | None = None
) -> None:
    fields = {"commitment_id": commitment.id, "note": note, "changes": changes or {}}
    create_entity(ctx, ProgressEntry(**fields), fields)


@router.get("/commitments")
def list_commitments(
    ctx: Viewer,
    today: Today,
    paging: PagingParams,
    q: SearchText = None,
    state: StateFilter | None = None,
    owner_id: uuid.UUID | None = None,
    mine: bool = False,
) -> Page[CommitmentOut]:
    query = query_commitments(today, q, state, ctx.user.id if mine else owner_id)
    page = page_of(ctx, query, paging)
    return Page[CommitmentOut](
        items=present_commitments(ctx, page["items"], today), total=page["total"]
    )


@router.get("/commitments/{commitment_id}")
def get_commitment(commitment_id: uuid.UUID, ctx: Viewer, today: Today) -> CommitmentDetail:
    return _detail(ctx, get_or_404(ctx, Commitment, commitment_id), today)


@router.patch("/commitments/{commitment_id}")
def update_commitment(
    commitment_id: uuid.UUID, payload: CommitmentPatch, ctx: Editor, today: Today
) -> CommitmentDetail:
    commitment = get_or_404(ctx, Commitment, commitment_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.keys() & {"description", "subject"}:
        # Locks the meeting, so it cannot be closed with the text half changed.
        open_item(ctx, commitment.item_id)
    if commitment.state != OPEN:
        raise commitment_finished()
    recorded: dict[str, list[str]] = {}
    if "subject" in changes:
        changes["subject"] = payload.subject and subjects.resolve(ctx, payload.subject, today)
    if "owner_id" in changes and changes["owner_id"] != commitment.owner_id:
        owner = members.resolve_member(ctx, changes["owner_id"], "owner_id")
        recorded["owner"] = [commitment.owner.full_name, owner.full_name]
    if "due_date" in changes and changes["due_date"] != commitment.due_date:
        recorded["due_date"] = [
            commitment.due_date.isoformat(),
            changes["due_date"].isoformat(),
        ]
    update_entity(ctx, commitment, changes)
    if recorded:
        _record(ctx, commitment, changes=recorded)
    return _detail(ctx, commitment, today)


@router.delete("/commitments/{commitment_id}", status_code=204)
def delete_commitment(commitment_id: uuid.UUID, ctx: Editor) -> None:
    """Remove one recorded by mistake, while its meeting is open. Later it is dropped."""
    commitment = get_or_404(ctx, Commitment, commitment_id)
    open_item(ctx, commitment.item_id)
    delete_entity(ctx, commitment)


@router.post("/commitments/{commitment_id}/notes", status_code=201)
def add_note(
    commitment_id: uuid.UUID, payload: NoteIn, ctx: Viewer, today: Today
) -> CommitmentDetail:
    commitment = get_or_404(ctx, Commitment, commitment_id)
    level = effective_level(ctx.db, ctx.membership, KEY)
    if level < AccessLevel.EDITOR and commitment.owner_id != ctx.user.id:
        raise forbidden()
    _record(ctx, commitment, note=payload.note)
    return _detail(ctx, commitment, today)


@router.post("/commitments/{commitment_id}/state")
def set_state(
    commitment_id: uuid.UUID, payload: StateIn, ctx: Editor, today: Today
) -> CommitmentDetail:
    """Mark it done or dropped, or open it again."""
    commitment = get_or_404(ctx, Commitment, commitment_id)
    completed_on = None
    if payload.state == DONE:
        completed_on = payload.completed_on or today
        if completed_on > today:
            raise validation_error("completed_on must not be in the future.")
    changes = {"state": payload.state, "completed_on": completed_on}
    recorded = {}
    if payload.state != commitment.state:
        recorded["state"] = [commitment.state, payload.state]
    if completed_on is not None and completed_on != commitment.completed_on:
        before = commitment.completed_on
        recorded["completed_on"] = [before and before.isoformat(), completed_on.isoformat()]
    if not recorded and not payload.note:
        # Saying the same again adds nothing to the history.
        return _detail(ctx, commitment, today)
    update_entity(ctx, commitment, changes)
    _record(ctx, commitment, payload.note, recorded)
    return _detail(ctx, commitment, today)
