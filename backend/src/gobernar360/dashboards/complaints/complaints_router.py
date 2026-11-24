"""Complaints, their lifecycle and the areas' queues.

Reading needs viewer access; registering complaints and acting on them needs editor access.
Every change is stamped with the server's time: a step cannot be dated back.
"""

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Query
from pydantic import TypeAdapter, ValidationError
from sqlalchemy import or_, select

from gobernar360.core.errors import (
    case_not_open,
    invalid_transition,
    not_found,
    validation_error,
)
from gobernar360.dashboards.complaints.access import Editor, Viewer
from gobernar360.dashboards.complaints.cases import (
    add_event,
    load_calendar,
    load_steps,
    local_date,
    lock_complaint,
    next_number,
    present,
    present_many,
    reading_of,
    readings,
)
from gobernar360.dashboards.complaints.lifecycle import (
    COMMENT,
    CREATED,
    NOTE_REQUIRED,
    OPEN_STATES,
    REASSIGNED,
    RECEIVED,
    RETYPED,
    TRANSITION,
    allowed_moves,
    can_move,
    is_open,
)
from gobernar360.dashboards.complaints.models import (
    Area,
    Complaint,
    ComplaintEvent,
    ComplaintType,
    Zone,
)
from gobernar360.dashboards.complaints.schemas import (
    AssignmentIn,
    ClockStatus,
    CommentIn,
    ComplaintDetail,
    ComplaintIn,
    ComplaintOut,
    ComplaintPatch,
    LookupOut,
    QueueOut,
    State,
    TransitionIn,
)
from gobernar360.platform import people
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import Now, Today
from gobernar360.platform.listing import Page, PagingParams, SearchText, contains, page_of
from gobernar360.platform.models import Person
from gobernar360.platform.tenant_crud import create_entity, get_or_404, resolve, update_entity

router = APIRouter()

_dni = TypeAdapter(people.Dni)
NEWEST_FIRST = (Complaint.received_at.desc(), Complaint.number.desc())


def _detail(ctx: RequestContext, complaint: Complaint, today) -> dict[str, Any]:
    ctx.db.refresh(complaint)
    steps = load_steps(ctx, [complaint.id]).get(complaint.id, [])
    reading = reading_of(complaint, steps, today, load_calendar(ctx))
    timeline = ctx.db.scalars(
        select(ComplaintEvent)
        .where(ComplaintEvent.complaint_id == complaint.id)
        .order_by(ComplaintEvent.position)
    ).all()
    return present(complaint, reading) | {
        "description": complaint.description,
        "moves": list(allowed_moves(complaint.state)),
        "timeline": timeline,
    }


def _require_open(complaint: Complaint) -> None:
    if not is_open(complaint.state):
        raise case_not_open()


def _active_type(ctx: RequestContext, type_id: uuid.UUID) -> ComplaintType:
    complaint_type = resolve(ctx, ComplaintType, type_id, "type_id")
    if not complaint_type.is_active:
        raise validation_error("That complaint type is no longer in use.")
    return complaint_type


@router.get("/complaints")
def list_complaints(
    ctx: Viewer,
    today: Today,
    paging: PagingParams,
    q: SearchText = None,
    state: State | Literal["open"] | None = None,
    type_id: uuid.UUID | None = None,
    area_id: uuid.UUID | None = None,
    zone_id: uuid.UUID | None = None,
    status: ClockStatus | None = None,
) -> Page[ComplaintOut]:
    """Newest first. `q` matches the number, the address or the resident's name."""
    query = select(Complaint).outerjoin(Person, Complaint.person_id == Person.id)
    for word in (q or "").split():
        matches = [
            contains(Complaint.address, word),
            contains(Person.first_name, word),
            contains(Person.last_name, word),
        ]
        if word.isdigit():
            matches.append(Complaint.number == int(word))
        query = query.where(or_(*matches))
    if state == "open":
        query = query.where(Complaint.state.in_(OPEN_STATES))
    elif state is not None:
        query = query.where(Complaint.state == state)
    for column, value in (
        (Complaint.type_id, type_id),
        (Complaint.area_id, area_id),
        (Complaint.zone_id, zone_id),
    ):
        if value is not None:
            query = query.where(column == value)
    query = query.order_by(*NEWEST_FIRST)
    if status is None:
        page = page_of(ctx, query, paging)
        return {"items": present_many(ctx, page["items"], today), "total": page["total"]}
    # The clock is read, not stored, so this filter runs over the matching complaints.
    matching = ctx.db.scalars(query).unique().all()
    found = readings(ctx, matching, today)
    kept = [complaint for complaint in matching if found[complaint.id].status == status]
    page = kept[paging.offset : paging.offset + paging.limit]
    return {"items": [present(c, found[c.id]) for c in page], "total": len(kept)}


@router.post("/complaints", status_code=201)
def create_complaint(payload: ComplaintIn, ctx: Editor, now: Now) -> ComplaintDetail:
    """Received now, routed to the type's area, with the type's target."""
    complaint_type = _active_type(ctx, payload.type_id)
    resolve(ctx, Zone, payload.zone_id, "zone_id")
    person_id = None
    if payload.person_id is not None:
        person_id = resolve(ctx, Person, payload.person_id, "person_id").id
    elif payload.new_person is not None:
        person_id = people.create_person(ctx, payload.new_person).id
    fields = {
        "type_id": complaint_type.id,
        "area_id": complaint_type.area_id,
        "zone_id": payload.zone_id,
        "address": payload.address,
        "description": payload.description,
        "person_id": person_id,
        "state": RECEIVED,
        "target_days": complaint_type.target_days,
    }
    complaint = Complaint(number=next_number(ctx), received_at=now, **fields)
    create_entity(ctx, complaint, fields | {"number": complaint.number})
    add_event(
        ctx,
        complaint,
        CREATED,
        now,
        to_state=RECEIVED,
        to_area_id=complaint_type.area_id,
        to_type_id=complaint_type.id,
    )
    return _detail(ctx, complaint, local_date(now))


@router.get("/complaints/{complaint_id}")
def get_complaint(complaint_id: uuid.UUID, ctx: Viewer, today: Today) -> ComplaintDetail:
    return _detail(ctx, get_or_404(ctx, Complaint, complaint_id), today)


@router.patch("/complaints/{complaint_id}")
def update_complaint(
    complaint_id: uuid.UUID, payload: ComplaintPatch, ctx: Editor, now: Now
) -> ComplaintDetail:
    """Correct an open complaint. A new type brings its own target; the area stays."""
    complaint = lock_complaint(ctx, complaint_id)
    _require_open(complaint)
    changes = payload.model_dump(exclude_unset=True)
    if "zone_id" in changes:
        resolve(ctx, Zone, changes["zone_id"], "zone_id")
    retyped_from = None
    if changes.get("type_id", complaint.type_id) != complaint.type_id:
        new_type = _active_type(ctx, changes["type_id"])
        retyped_from = complaint.type_id
        changes["target_days"] = new_type.target_days
    else:
        changes.pop("type_id", None)
    if changes:
        update_entity(ctx, complaint, changes)
    if retyped_from is not None:
        add_event(
            ctx, complaint, RETYPED, now, from_type_id=retyped_from, to_type_id=complaint.type_id
        )
    return _detail(ctx, complaint, local_date(now))


@router.post("/complaints/{complaint_id}/transitions", status_code=201)
def move_complaint(
    complaint_id: uuid.UUID, payload: TransitionIn, ctx: Editor, now: Now
) -> ComplaintDetail:
    """Move the complaint to another state, if its current state allows it."""
    complaint = lock_complaint(ctx, complaint_id)
    from_state, to_state = complaint.state, payload.to_state
    if not can_move(from_state, to_state):
        raise invalid_transition(f"A complaint in state {from_state} cannot move to {to_state}.")
    if to_state in NOTE_REQUIRED and not payload.note:
        raise validation_error(f"Moving a complaint to {to_state} needs a note saying why.")
    update_entity(ctx, complaint, {"state": to_state})
    add_event(
        ctx,
        complaint,
        TRANSITION,
        now,
        from_state=from_state,
        to_state=to_state,
        note=payload.note,
    )
    return _detail(ctx, complaint, local_date(now))


@router.post("/complaints/{complaint_id}/assignment", status_code=201)
def reassign_complaint(
    complaint_id: uuid.UUID, payload: AssignmentIn, ctx: Editor, now: Now
) -> ComplaintDetail:
    """Send an open complaint to another area's queue. Its state does not change."""
    complaint = lock_complaint(ctx, complaint_id)
    _require_open(complaint)
    area = resolve(ctx, Area, payload.area_id, "area_id")
    if area.id == complaint.area_id:
        raise validation_error("The complaint is already in that area.")
    from_area_id = complaint.area_id
    update_entity(ctx, complaint, {"area_id": area.id})
    add_event(
        ctx,
        complaint,
        REASSIGNED,
        now,
        from_area_id=from_area_id,
        to_area_id=area.id,
        note=payload.note,
    )
    return _detail(ctx, complaint, local_date(now))


@router.post("/complaints/{complaint_id}/comments", status_code=201)
def comment_complaint(
    complaint_id: uuid.UUID, payload: CommentIn, ctx: Editor, now: Now
) -> ComplaintDetail:
    """Add a note to the timeline without changing anything else; allowed in any state."""
    complaint = lock_complaint(ctx, complaint_id)
    add_event(ctx, complaint, COMMENT, now, note=payload.note)
    return _detail(ctx, complaint, local_date(now))


def _open_readings(ctx: RequestContext, today, area_id: uuid.UUID | None = None):
    query = select(Complaint).where(Complaint.state.in_(OPEN_STATES))
    if area_id is not None:
        query = query.where(Complaint.area_id == area_id)
    complaints = ctx.db.scalars(query).unique().all()
    return complaints, readings(ctx, complaints, today)


@router.get("/queues")
def list_queues(ctx: Viewer, today: Today) -> list[QueueOut]:
    """Every area with how many open complaints it holds and how they stand."""
    complaints, found = _open_readings(ctx, today)
    areas = ctx.db.scalars(select(Area).order_by(Area.name, Area.id)).all()
    queues = {
        area.id: QueueOut(area=area, open=0, at_risk=0, overdue=0, paused=0) for area in areas
    }
    for complaint in complaints:
        queue, reading = queues[complaint.area_id], found[complaint.id]
        queue.open += 1
        queue.at_risk += reading.status == "at_risk"
        queue.overdue += reading.status == "overdue"
        queue.paused += reading.paused
    return list(queues.values())


@router.get("/queues/{area_id}")
def get_queue(area_id: uuid.UUID, ctx: Viewer, today: Today) -> list[ComplaintOut]:
    """An area's open complaints, closest to their deadline first.

    Fewest business days left first (overdue ones lead); on a tie, running clocks before
    paused ones, then the oldest.
    """
    if ctx.db.get(Area, area_id) is None:
        raise not_found()
    complaints, found = _open_readings(ctx, today, area_id)
    ordered = sorted(
        complaints,
        key=lambda c: (found[c.id].left_days, found[c.id].paused, c.received_at, c.number),
    )
    return [present(complaint, found[complaint.id]) for complaint in ordered]


@router.get("/people/lookup")
def lookup_person(ctx: Editor, dni: Annotated[str, Query(max_length=30)]) -> LookupOut:
    """Whether the municipality's registry has a person with exactly this document."""
    try:
        normalised = _dni.validate_python(dni)
    except ValidationError as error:
        raise validation_error("dni must have 6 to 9 digits.") from error
    return LookupOut(person=people.find_by_dni(ctx, normalised))
