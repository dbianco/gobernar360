"""What every complaint route needs: the calendar, clock readings and timeline entries."""

import uuid
from collections.abc import Sequence
from dataclasses import asdict
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, text

from gobernar360.core.errors import not_found
from gobernar360.dashboards.complaints.clock import (
    MONDAY_TO_FRIDAY,
    Calendar,
    ClockReading,
    Step,
    read_clock,
)
from gobernar360.dashboards.complaints.lifecycle import TRANSITION
from gobernar360.dashboards.complaints.models import (
    Complaint,
    ComplaintEvent,
    Holiday,
    WorkingWeek,
)
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import LOCAL_TIMEZONE


def local_date(moment: datetime) -> date:
    """The Argentine calendar day a moment falls on."""
    return moment.astimezone(LOCAL_TIMEZONE).date()


def load_calendar(ctx: RequestContext) -> Calendar:
    week = ctx.db.scalar(select(WorkingWeek.weekdays))
    holidays = ctx.db.scalars(select(Holiday.date)).all()
    return Calendar(
        working_weekdays=frozenset(week) if week else MONDAY_TO_FRIDAY,
        holidays=frozenset(holidays),
    )


def load_steps(
    ctx: RequestContext, complaint_ids: Sequence[uuid.UUID] | None = None
) -> dict[uuid.UUID, list[Step]]:
    """State changes per complaint, in order; every complaint's when no ids are given."""
    query = (
        select(ComplaintEvent.complaint_id, ComplaintEvent.at, ComplaintEvent.to_state)
        .where(ComplaintEvent.kind == TRANSITION)
        .order_by(ComplaintEvent.complaint_id, ComplaintEvent.position)
    )
    if complaint_ids is not None:
        if not complaint_ids:
            return {}
        query = query.where(ComplaintEvent.complaint_id.in_(complaint_ids))
    steps: dict[uuid.UUID, list[Step]] = {}
    for complaint_id, at, to_state in ctx.db.execute(query):
        steps.setdefault(complaint_id, []).append(Step(on=local_date(at), to_state=to_state))
    return steps


def reading_of(
    complaint: Complaint, steps: Sequence[Step], today: date, calendar: Calendar
) -> ClockReading:
    return read_clock(
        received_on=local_date(complaint.received_at),
        steps=steps,
        target_days=complaint.target_days,
        today=today,
        calendar=calendar,
    )


def readings(
    ctx: RequestContext,
    complaints: Sequence[Complaint],
    today: date,
    calendar: Calendar | None = None,
) -> dict[uuid.UUID, ClockReading]:
    calendar = calendar or load_calendar(ctx)
    steps = load_steps(ctx, [complaint.id for complaint in complaints])
    return {
        complaint.id: reading_of(complaint, steps.get(complaint.id, []), today, calendar)
        for complaint in complaints
    }


def present(complaint: Complaint, reading: ClockReading) -> dict[str, Any]:
    """A complaint as a list item, with its clock."""
    return {
        "id": complaint.id,
        "number": complaint.number,
        "received_at": complaint.received_at,
        "type": complaint.type,
        "area": complaint.area,
        "zone": complaint.zone,
        "address": complaint.address,
        "state": complaint.state,
        "person": complaint.person,
        "clock": asdict(reading),
    }


def present_many(
    ctx: RequestContext, complaints: Sequence[Complaint], today: date
) -> list[dict[str, Any]]:
    found = readings(ctx, complaints, today)
    return [present(complaint, found[complaint.id]) for complaint in complaints]


def lock_complaint(ctx: RequestContext, complaint_id: uuid.UUID) -> Complaint:
    """Load a complaint about to change, making concurrent changes to it wait their turn."""
    complaint = ctx.db.scalar(
        select(Complaint)
        .where(Complaint.id == complaint_id)
        .with_for_update(of=Complaint)
        .execution_options(populate_existing=True)
    )
    if complaint is None:
        raise not_found()
    return complaint


def next_number(ctx: RequestContext) -> int:
    """The municipality's next complaint number. Holds a lock until the request ends."""
    ctx.db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
        {"key": f"complaints:{ctx.municipality_id}"},
    )
    return (ctx.db.scalar(select(func.max(Complaint.number))) or 0) + 1


def add_event(
    ctx: RequestContext, complaint: Complaint, kind: str, at: datetime, **fields: Any
) -> ComplaintEvent:
    """Append an entry to the complaint's timeline, signed by the member acting."""
    last = ctx.db.scalar(
        select(func.max(ComplaintEvent.position)).where(ComplaintEvent.complaint_id == complaint.id)
    )
    event = ComplaintEvent(
        municipality_id=ctx.municipality_id,
        complaint_id=complaint.id,
        position=0 if last is None else last + 1,
        kind=kind,
        at=at,
        user_id=ctx.user.id,
        **fields,
    )
    ctx.db.add(event)
    ctx.db.flush()
    return event
