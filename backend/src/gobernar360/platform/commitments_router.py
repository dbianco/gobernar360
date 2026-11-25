"""Commitments of every member: those they owe, gave or are attached to, and what they are
told about them. Who may do what is decided in `platform.commitments`."""

import datetime as dt
import uuid
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter
from sqlalchemy import select

from gobernar360.platform import commitments, subjects
from gobernar360.platform.access import Context, RequestContext
from gobernar360.platform.clock import Today
from gobernar360.platform.commitment_models import Commitment, CommitmentEntry
from gobernar360.platform.commitment_rules import OPEN, effective_state
from gobernar360.platform.commitment_schemas import (
    CommitmentDetail,
    CommitmentIn,
    CommitmentOut,
    CommitmentPatch,
    HistoryEntry,
    NewsOut,
    NoteIn,
    NotificationRow,
    NotificationsOut,
    OriginOut,
    ReadIn,
    RightsOut,
    StateFilter,
    StateIn,
)
from gobernar360.platform.directory import UserRef
from gobernar360.platform.listing import Page, PagingParams, SearchText, page_of
from gobernar360.platform.models import User
from gobernar360.platform.tenant_crud import update_entity

router = APIRouter(tags=["commitments"])


def present(ctx: RequestContext, rows: list[Commitment], today: dt.date) -> list[CommitmentOut]:
    ids = [row.id for row in rows]
    seen = subjects.present(ctx, [row.subject for row in rows])
    origins = commitments.origins(ctx, rows)
    followers = commitments.followers_of(ctx, ids)
    rights = commitments.rights_on(ctx, rows)
    creators = {
        user.id: user
        for user in ctx.db.scalars(
            select(User).where(User.id.in_({row.created_by for row in rows if row.source is None}))
        )
    }

    def origin(row: Commitment) -> OriginOut | None:
        if row.id not in origins or not commitments.sees_source(ctx, row):
            return None
        return OriginOut(label=origins[row.id].label, path=origins[row.id].path)

    def creator(row: Commitment) -> UserRef | None:
        user = creators.get(row.created_by) if row.source is None else None
        return UserRef.model_validate(user) if user else None

    return [
        CommitmentOut(
            id=row.id,
            description=row.description,
            owner=UserRef.model_validate(row.owner),
            creator=creator(row),
            due_date=row.due_date,
            state=effective_state(row.state, row.due_date, today),
            completed_on=row.completed_on,
            times_postponed=origins[row.id].times_postponed if row.id in origins else 0,
            subject=seen.get(row.subject),
            source=row.source,
            origin=origin(row),
            followers=[UserRef.model_validate(user) for user in followers.get(row.id, [])],
            rights=RightsOut(**asdict(rights[row.id])),
        )
        for row in rows
    ]


def _detail(ctx: RequestContext, commitment: Commitment, today: dt.date) -> CommitmentDetail:
    ctx.db.refresh(commitment)
    rows = ctx.db.execute(
        select(CommitmentEntry, User.full_name)
        .outerjoin(User, User.id == CommitmentEntry.created_by)
        .where(CommitmentEntry.commitment_id == commitment.id)
        .order_by(CommitmentEntry.created_at.desc(), CommitmentEntry.id)
    )
    return CommitmentDetail(
        **present(ctx, [commitment], today)[0].model_dump(),
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


@router.get("/commitments")
def list_commitments(
    ctx: Context,
    today: Today,
    paging: PagingParams,
    relation: Literal["mine", "given", "following"] = "mine",
    q: SearchText = None,
    state: StateFilter | None = None,
) -> Page[CommitmentOut]:
    query = commitments.query_commitments(today, q, state).where(
        commitments.relation(ctx, relation)
    )
    page = page_of(ctx, query, paging)
    return Page[CommitmentOut](items=present(ctx, list(page["items"]), today), total=page["total"])


@router.post("/commitments", status_code=201)
def create_commitment(payload: CommitmentIn, ctx: Context, today: Today) -> CommitmentDetail:
    """Give a commitment to any member, oneself included."""
    commitment = commitments.create(
        ctx,
        today,
        description=payload.description,
        owner_id=payload.owner_id,
        due_date=payload.due_date,
        subject=payload.subject,
        follower_ids=payload.follower_ids,
    )
    return _detail(ctx, commitment, today)


@router.get("/commitments/{commitment_id}")
def get_commitment(commitment_id: uuid.UUID, ctx: Context, today: Today) -> CommitmentDetail:
    return _detail(ctx, commitments.load(ctx, commitment_id), today)


@router.patch("/commitments/{commitment_id}")
def update_commitment(
    commitment_id: uuid.UUID, payload: CommitmentPatch, ctx: Context, today: Today
) -> CommitmentDetail:
    """The answer may have `rights.see` false: whoever gave theirs to somebody else no
    longer has to do with it."""
    commitment = commitments.load(ctx, commitment_id, lock=True)
    rights = commitments.rights(ctx, commitment)
    fields = payload.model_dump(exclude_unset=True)
    text = {name: fields.pop(name) for name in ("description", "subject") if name in fields}
    commitments.require(rights.edit or not text)
    commitments.require(rights.reschedule or not fields)
    commitments.reschedule(ctx, commitment, **fields)
    if text:
        if "subject" in text:
            text["subject"] = payload.subject and subjects.resolve(ctx, payload.subject, today)
        before = commitment.description
        update_entity(ctx, commitment, text)
        if commitment.description != before:
            commitments.record(
                ctx, commitment, changes={"description": [before, commitment.description]}
            )
    return _detail(ctx, commitment, today)


@router.post("/commitments/{commitment_id}/notes", status_code=201)
def add_note(
    commitment_id: uuid.UUID, payload: NoteIn, ctx: Context, today: Today
) -> CommitmentDetail:
    commitment = commitments.load(ctx, commitment_id)
    commitments.require(commitments.rights(ctx, commitment).note)
    commitments.record(ctx, commitment, note=payload.note)
    return _detail(ctx, commitment, today)


@router.post("/commitments/{commitment_id}/state")
def set_state(
    commitment_id: uuid.UUID, payload: StateIn, ctx: Context, today: Today
) -> CommitmentDetail:
    """Mark it done or dropped, or open it again."""
    commitment = commitments.load(ctx, commitment_id, lock=True)
    rights = commitments.rights(ctx, commitment)
    commitments.require(rights.finish if payload.state == "done" else rights.manage)
    commitments.set_state(ctx, commitment, today, payload.state, payload.completed_on, payload.note)
    return _detail(ctx, commitment, today)


@router.get("/notifications")
def list_notifications(ctx: Context, today: Today) -> NotificationsOut:
    """What the member owes and follows, with what they have not read about each."""
    rows = commitments.notification_rows(ctx, today)
    unread = commitments.unread_notices(ctx)

    def row(commitment: Commitment) -> NotificationRow:
        return NotificationRow(
            id=commitment.id,
            description=commitment.description,
            owner=UserRef.model_validate(commitment.owner),
            due_date=commitment.due_date,
            state=effective_state(commitment.state, commitment.due_date, today),
            completed_on=commitment.completed_on,
            news=[
                NewsOut(kind=notice.kind, actor=actor and actor.full_name, at=notice.created_at)
                for notice, actor in unread.get(commitment.id, [])
            ],
        )

    mine = [c for c in rows if c.owner_id == ctx.user.id]
    return NotificationsOut(
        mine=[row(c) for c in mine if c.state == OPEN],
        # What is news comes first; the rest keeps its order.
        others=sorted(
            (row(c) for c in rows if c.owner_id != ctx.user.id), key=lambda r: not r.news
        ),
    )


@router.post("/notifications/read", status_code=204)
def mark_read(payload: ReadIn, ctx: Context) -> None:
    commitments.mark_read(ctx, payload.commitment_id)
