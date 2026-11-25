"""Builds what the API answers about commitments and agenda items, as each reader may see it."""

from collections.abc import Sequence
from datetime import date
from typing import Any

from sqlalchemy import func, select

from gobernar360.dashboards.cabinet.models import AgendaItem, Carryover, Commitment, Meeting
from gobernar360.dashboards.cabinet.rules import effective_state
from gobernar360.dashboards.cabinet.schemas import (
    CommitmentOut,
    MeetingRef,
    UserRef,
)
from gobernar360.platform import subjects
from gobernar360.platform.access import RequestContext
from gobernar360.platform.subjects import SubjectOut
from gobernar360.platform.texts import text


def meeting_ref(meeting: Meeting) -> MeetingRef:
    return MeetingRef(id=meeting.id, date=meeting.date, closed=meeting.closed_at is not None)


def times_postponed(ctx: RequestContext, ids: Sequence[Any]) -> dict[Any, int]:
    return dict(
        ctx.db.execute(
            select(Carryover.commitment_id, func.count())
            .where(Carryover.commitment_id.in_(ids))
            .group_by(Carryover.commitment_id)
        ).all()
    )


def present_commitments(
    ctx: RequestContext, commitments: Sequence[Commitment], today: date
) -> list[CommitmentOut]:
    postponed = times_postponed(ctx, [c.id for c in commitments])
    seen = subjects.present(ctx, [c.subject for c in commitments])
    meetings = {
        meeting.id: meeting_ref(meeting)
        for meeting in ctx.db.scalars(
            select(Meeting).where(Meeting.id.in_({c.item.meeting_id for c in commitments}))
        )
    }
    return [
        CommitmentOut(
            id=commitment.id,
            description=commitment.description,
            owner=UserRef.model_validate(commitment.owner),
            due_date=commitment.due_date,
            state=effective_state(commitment.state, commitment.due_date, today),
            completed_on=commitment.completed_on,
            times_postponed=postponed.get(commitment.id, 0),
            subject=seen.get(commitment.subject),
            item_id=commitment.item_id,
            meeting=meetings[commitment.item.meeting_id],
        )
        for commitment in commitments
    ]


def present_commitment(ctx: RequestContext, commitment: Commitment, today: date) -> CommitmentOut:
    return present_commitments(ctx, [commitment], today)[0]


def item_title(item: AgendaItem, subject: SubjectOut | None, commitment: str | None) -> str:
    """What an agenda item is called, for a reader who sees its subject as `subject`."""
    if item.source == "light":
        return light_title(subject)
    return commitment if item.source == "commitment" else item.title


def light_title(subject: SubjectOut) -> str:
    # Month lights are never "deleted": a dashboard's months always exist.
    return subject.label or text("cabinet.restrictedLight")
