"""Meetings, their agenda and their minutes. Viewers read; editors prepare, record and close.

A closed meeting cannot change. Every route that writes to a meeting loads it with
`_open_meeting`, which also locks it, so nothing slips in while it is being closed.
"""

import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime

from fastapi import APIRouter, Response
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.exc import IntegrityError

from gobernar360.core.errors import (
    agenda_changed,
    invalid_reference,
    meeting_already_open,
    meeting_before_last,
    meeting_closed,
    meeting_not_closed,
    not_found,
    validation_error,
)
from gobernar360.dashboards.cabinet import agenda, minutes
from gobernar360.dashboards.cabinet.access import KEY, Editor, Viewer
from gobernar360.dashboards.cabinet.models import AgendaItem, Attendee, Meeting, Taken
from gobernar360.dashboards.cabinet.present import (
    item_title,
    present_commitment,
    present_commitments,
)
from gobernar360.dashboards.cabinet.schemas import (
    AgendaEntryIn,
    AgendaProposalOut,
    CommitmentOut,
    ItemIn,
    ItemOut,
    ItemPatch,
    MeetingDetail,
    MeetingIn,
    MeetingOut,
    MeetingPatch,
    OrderIn,
    ProposalOut,
)
from gobernar360.platform import commitments, directory, subjects
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import Today
from gobernar360.platform.commitment_models import Commitment
from gobernar360.platform.commitment_schemas import CommitmentIn
from gobernar360.platform.directory import UserRef
from gobernar360.platform.listing import Page, PagingParams, SearchText, contains, page_of
from gobernar360.platform.tenant_crud import (
    create_entity,
    delete_entity,
    get_or_404,
    update_entity,
)

router = APIRouter()


def _open_meeting(ctx: RequestContext, meeting_id: uuid.UUID) -> Meeting:
    """The meeting, locked until the request ends and known to be open."""
    meeting = ctx.db.get(Meeting, meeting_id, with_for_update=True)
    if meeting is None:
        raise not_found()
    if meeting.closed_at is not None:
        raise meeting_closed()
    return meeting


def open_item(ctx: RequestContext, item_id: uuid.UUID) -> AgendaItem:
    """An agenda item whose meeting is open, locked as the meeting is."""
    item = get_or_404(ctx, AgendaItem, item_id)
    _open_meeting(ctx, item.meeting_id)
    return item


def _check_date(ctx: RequestContext, meeting_date: date) -> None:
    last = agenda.last_closed_meeting(ctx)
    if last is not None and meeting_date < last.date:
        raise meeting_before_last()


def _set_attendees(ctx: RequestContext, meeting: Meeting, user_ids: Iterable[uuid.UUID]) -> None:
    wanted = set(user_ids)
    current = {
        row.user_id: row
        for row in ctx.db.scalars(select(Attendee).where(Attendee.meeting_id == meeting.id))
    }
    # Someone already in the list may have left the municipality since: they stay.
    directory.resolve_members(ctx, wanted - set(current), "attendee_ids")
    for user_id in current.keys() - wanted:
        delete_entity(ctx, current[user_id])
    for user_id in sorted(wanted - current.keys()):
        fields = {"meeting_id": meeting.id, "user_id": user_id}
        create_entity(ctx, Attendee(**fields), fields)


def _detail(ctx: RequestContext, meeting: Meeting, today: date) -> MeetingDetail:
    items = agenda.items_of(ctx, meeting)
    taken = minutes.commitments_of(ctx, meeting)
    item_of = minutes.items_taken_in(ctx, taken)
    carried = minutes.carried_over_to(ctx, meeting)
    topics = list(
        ctx.db.scalars(
            select(Commitment).where(
                Commitment.id.in_([i.commitment_id for i in items if i.commitment_id])
            )
        ).unique()
    )
    rows = {c.id: c for c in (*taken, *carried, *topics)}
    shown = {c.id: c for c in present_commitments(ctx, list(rows.values()), today)}
    seen = subjects.present(ctx, [item.subject for item in items])
    return MeetingDetail(
        id=meeting.id,
        date=meeting.date,
        closed=meeting.closed_at is not None,
        closed_at=meeting.closed_at,
        attendees=[UserRef.model_validate(u) for u in minutes.attendees_of(ctx, meeting)],
        guests=meeting.guests,
        notes=meeting.notes,
        items=[
            ItemOut(
                id=item.id,
                source=item.source,
                title=item_title(
                    item,
                    seen.get(item.subject),
                    shown[item.commitment_id].description if item.commitment_id else None,
                ),
                notes=item.notes,
                discussed=item.discussed,
                carried=item.carried_from_id is not None,
                subject=seen.get(item.subject),
                topic=shown.get(item.commitment_id),
                commitments=[shown[c.id] for c in taken if item_of[c.id] == item.id],
            )
            for item in items
        ],
        carried_over=[shown[c.id] for c in carried],
    )


@router.get("/agenda-proposal")
def get_agenda_proposal(ctx: Editor, today: Today, date: date) -> AgendaProposalOut:
    """What a meeting on that date would discuss. Looking at it changes nothing."""
    proposals = agenda.propose(ctx, date, today)
    seen = subjects.present(ctx, [p.subject for p in proposals])
    proposed = [p.commitment for p in proposals if p.commitment is not None]
    shown = {c.id: c for c in present_commitments(ctx, proposed, today)}
    last = agenda.last_closed_meeting(ctx)
    return AgendaProposalOut(
        proposals=[
            ProposalOut(
                key=p.key,
                source=p.source,
                title=item_title(
                    p, seen.get(p.subject), p.commitment.description if p.commitment else None
                ),
                subject=seen.get(p.subject),
                commitment=shown[p.commitment.id] if p.commitment else None,
                carried=p.carried_from is not None,
            )
            for p in proposals
        ],
        to_carry_over=len(agenda.open_commitments(ctx)),
        dashboards_not_considered=agenda.dashboards_not_considered(ctx),
        previous_meeting_date=last.date if last else None,
    )


def _mentions(word: str) -> ColumnElement[bool]:
    """Meetings where the word was written: notes, agenda or commitments."""
    items = select(AgendaItem.id).where(AgendaItem.meeting_id == Meeting.id)
    return or_(
        contains(Meeting.notes, word),
        contains(Meeting.guests, word),
        items.where(or_(contains(AgendaItem.title, word), contains(AgendaItem.notes, word)))
        .correlate(Meeting)
        .exists(),
        items.join(Taken, Taken.item_id == AgendaItem.id)
        .join(Commitment, Commitment.id == Taken.commitment_id)
        .where(contains(Commitment.description, word))
        .correlate(Meeting)
        .exists(),
    )


@router.get("/meetings")
def list_meetings(ctx: Viewer, paging: PagingParams, q: SearchText = None) -> Page[MeetingOut]:
    """Meetings, the open one and then the latest first."""
    page = page_of(
        ctx,
        select(Meeting)
        .where(*(_mentions(word) for word in (q or "").split()))
        .order_by(Meeting.date.desc(), Meeting.created_at.desc(), Meeting.id),
        paging,
    )
    ids = [meeting.id for meeting in page["items"]]

    def count(query) -> dict[uuid.UUID, int]:
        return dict(
            ctx.db.execute(
                query.where(AgendaItem.meeting_id.in_(ids)).group_by(AgendaItem.meeting_id)
            ).all()
        )

    items = count(select(AgendaItem.meeting_id, func.count()))
    taken = count(
        select(AgendaItem.meeting_id, func.count()).join(Taken, Taken.item_id == AgendaItem.id)
    )
    return Page[MeetingOut](
        items=[
            MeetingOut(
                id=meeting.id,
                date=meeting.date,
                closed=meeting.closed_at is not None,
                closed_at=meeting.closed_at,
                items=items.get(meeting.id, 0),
                commitments=taken.get(meeting.id, 0),
            )
            for meeting in page["items"]
        ],
        total=page["total"],
    )


def _agenda_from(
    ctx: RequestContext, entries: list[AgendaEntryIn], meeting_date: date, today: date
) -> list[AgendaItem]:
    """The items of an accepted agenda. Only what is proposed now can be accepted."""
    keys = [entry.key for entry in entries if entry.key is not None]
    if len(set(keys)) != len(keys):
        raise validation_error("A proposal cannot be accepted twice.")
    proposals = {p.key: p for p in agenda.propose(ctx, meeting_date, today)} if keys else {}
    if not proposals.keys() >= set(keys):
        raise agenda_changed()
    items = []
    for position, entry in enumerate(entries):
        if entry.key is None:
            item = AgendaItem(source="manual", title=entry.title, position=position)
        else:
            accepted = proposals[entry.key]
            item = AgendaItem(
                source=accepted.source,
                title=accepted.title,
                position=position,
                commitment_id=accepted.commitment.id if accepted.commitment else None,
                carried_from_id=accepted.carried_from.id if accepted.carried_from else None,
            )
            item.subject = accepted.subject
        items.append(item)
    return items


@router.post("/meetings", status_code=201)
def create_meeting(payload: MeetingIn, ctx: Editor, today: Today) -> MeetingDetail:
    """Prepare the next meeting: its agenda is set and open commitments carry over to it."""
    _check_date(ctx, payload.date)
    items = _agenda_from(ctx, payload.agenda, payload.date, today)
    meeting = Meeting(date=payload.date, guests=payload.guests)
    try:
        with ctx.db.begin_nested():
            create_entity(ctx, meeting, payload.model_dump())
    except IntegrityError as error:
        # The index that lets a municipality have one open meeting at a time.
        raise meeting_already_open() from error
    _set_attendees(ctx, meeting, payload.attendee_ids)
    for item in items:
        item.meeting_id = meeting.id
        create_entity(ctx, item, {"meeting_id": meeting.id, "source": item.source})
    agenda.carry_over(ctx, meeting)
    return _detail(ctx, meeting, today)


@router.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: uuid.UUID, ctx: Viewer, today: Today) -> MeetingDetail:
    return _detail(ctx, get_or_404(ctx, Meeting, meeting_id), today)


@router.patch("/meetings/{meeting_id}")
def update_meeting(
    meeting_id: uuid.UUID, payload: MeetingPatch, ctx: Editor, today: Today
) -> MeetingDetail:
    meeting = _open_meeting(ctx, meeting_id)
    changes = payload.model_dump(exclude_unset=True)
    if "date" in changes:
        _check_date(ctx, changes["date"])
    attendee_ids = changes.pop("attendee_ids", None)
    if attendee_ids is not None:
        _set_attendees(ctx, meeting, attendee_ids)
    if changes:
        update_entity(ctx, meeting, changes)
    return _detail(ctx, meeting, today)


@router.delete("/meetings/{meeting_id}", status_code=204)
def delete_meeting(meeting_id: uuid.UUID, ctx: Editor) -> None:
    """Discard an open meeting that took no commitments. What it carried over no longer
    counts as postponed."""
    delete_entity(ctx, _open_meeting(ctx, meeting_id))


@router.post("/meetings/{meeting_id}/close")
def close_meeting(meeting_id: uuid.UUID, ctx: Editor, today: Today) -> MeetingDetail:
    """Freeze the meeting and its minutes, for good."""
    meeting = _open_meeting(ctx, meeting_id)
    # Not among the audited changes: the audit log need not repeat the whole minutes.
    meeting.minutes = minutes.snapshot(ctx, meeting, today)
    update_entity(ctx, meeting, {"closed_at": datetime.now(UTC)})
    return _detail(ctx, meeting, today)


@router.get("/meetings/{meeting_id}/minutes.html")
def download_minutes(meeting_id: uuid.UUID, ctx: Viewer) -> Response:
    meeting = get_or_404(ctx, Meeting, meeting_id)
    if meeting.closed_at is None:
        raise meeting_not_closed()
    filename = f"acta-gabinete-{meeting.date.isoformat()}.html"
    return Response(
        content=minutes.document(ctx, meeting),
        media_type="text/html; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/meetings/{meeting_id}/items", status_code=201)
def create_item(meeting_id: uuid.UUID, payload: ItemIn, ctx: Editor, today: Today) -> MeetingDetail:
    meeting = _open_meeting(ctx, meeting_id)
    last = ctx.db.scalar(
        select(func.max(AgendaItem.position)).where(AgendaItem.meeting_id == meeting.id)
    )
    item = AgendaItem(
        meeting_id=meeting.id,
        source="manual",
        title=payload.title,
        position=0 if last is None else last + 1,
    )
    if payload.subject is not None:
        item.subject = subjects.resolve(ctx, payload.subject, today)
    create_entity(ctx, item, payload.model_dump())
    return _detail(ctx, meeting, today)


@router.put("/meetings/{meeting_id}/items/order")
def order_items(
    meeting_id: uuid.UUID, payload: OrderIn, ctx: Editor, today: Today
) -> MeetingDetail:
    """Every item of the meeting, in the order wanted."""
    meeting = _open_meeting(ctx, meeting_id)
    items = {item.id: item for item in agenda.items_of(ctx, meeting)}
    if sorted(payload.item_ids) != sorted(items):
        raise invalid_reference("item_ids must be the items of the meeting, each once.")
    for position, item_id in enumerate(payload.item_ids):
        if items[item_id].position != position:
            update_entity(ctx, items[item_id], {"position": position})
    return _detail(ctx, meeting, today)


@router.patch("/items/{item_id}")
def update_item(item_id: uuid.UUID, payload: ItemPatch, ctx: Editor, today: Today) -> MeetingDetail:
    item = open_item(ctx, item_id)
    changes = payload.model_dump(exclude_unset=True)
    if item.source != "manual" and changes.keys() & {"title", "subject"}:
        raise validation_error("Only items typed by a person can be renamed or linked.")
    if "subject" in changes:
        changes["subject"] = payload.subject and subjects.resolve(ctx, payload.subject, today)
    if changes.get("notes"):
        # Writing down what was said is discussing it, unless the request says otherwise.
        changes.setdefault("discussed", True)
    update_entity(ctx, item, changes)
    return _detail(ctx, get_or_404(ctx, Meeting, item.meeting_id), today)


@router.delete("/items/{item_id}", status_code=204)
def delete_item(item_id: uuid.UUID, ctx: Editor) -> None:
    delete_entity(ctx, open_item(ctx, item_id))


@router.post("/items/{item_id}/commitments", status_code=201)
def create_commitment(
    item_id: uuid.UUID, payload: CommitmentIn, ctx: Editor, today: Today
) -> CommitmentOut:
    """Record something agreed on an item of an open meeting."""
    item = open_item(ctx, item_id)
    commitment = commitments.create(
        ctx,
        today,
        description=payload.description,
        owner_id=payload.owner_id,
        due_date=payload.due_date,
        subject=payload.subject,
        follower_ids=payload.follower_ids,
        source=KEY,
    )
    fields = {"commitment_id": commitment.id, "item_id": item.id}
    create_entity(ctx, Taken(**fields), fields)
    if not item.discussed:
        update_entity(ctx, item, {"discussed": True})
    return present_commitment(ctx, commitment, today)
