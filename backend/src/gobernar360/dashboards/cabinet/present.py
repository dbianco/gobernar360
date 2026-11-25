"""Builds what the API answers about commitments and agenda items, as each reader may see it."""

import uuid
from collections.abc import Collection, Sequence
from datetime import date
from typing import Any

from sqlalchemy import Select, func, select

from gobernar360.dashboards.cabinet.models import AgendaItem, Carryover, Meeting, Taken
from gobernar360.dashboards.cabinet.schemas import CommitmentOut, MeetingRef
from gobernar360.dashboards.registry import CommitmentOrigin
from gobernar360.platform import commitments as platform_commitments
from gobernar360.platform import subjects
from gobernar360.platform.access import RequestContext
from gobernar360.platform.commitment_models import Commitment
from gobernar360.platform.commitment_rules import effective_state
from gobernar360.platform.directory import UserRef
from gobernar360.platform.subjects import SubjectOut
from gobernar360.platform.texts import format_date, text


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


def taken() -> Select[Any]:
    """The commitments taken in meetings. Informal ones are not the cabinet's."""
    return select(Commitment).join(Taken, Taken.commitment_id == Commitment.id)


def present_commitments(
    ctx: RequestContext, commitments: Sequence[Commitment], today: date
) -> list[CommitmentOut]:
    ids = [c.id for c in commitments]
    postponed = times_postponed(ctx, ids)
    seen = subjects.present(ctx, [c.subject for c in commitments])
    followers = platform_commitments.followers_of(ctx, ids)
    where = {
        commitment_id: (item_id, meeting_ref(meeting))
        for commitment_id, item_id, meeting in ctx.db.execute(
            select(Taken.commitment_id, Taken.item_id, Meeting)
            .join(AgendaItem, AgendaItem.id == Taken.item_id)
            .join(Meeting, Meeting.id == AgendaItem.meeting_id)
            .where(Taken.commitment_id.in_(ids))
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
            followers=[UserRef.model_validate(user) for user in followers.get(commitment.id, [])],
            item_id=where[commitment.id][0],
            meeting=where[commitment.id][1],
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


def origins(ctx: RequestContext, ids: Collection[uuid.UUID]) -> dict[uuid.UUID, CommitmentOrigin]:
    """Which meeting each commitment was taken in, for whoever shows it (see the registry)."""
    postponed = times_postponed(ctx, list(ids))
    rows = ctx.db.execute(
        select(Taken.commitment_id, Meeting.id, Meeting.date)
        .join(AgendaItem, AgendaItem.id == Taken.item_id)
        .join(Meeting, Meeting.id == AgendaItem.meeting_id)
        .where(Taken.commitment_id.in_(ids))
    )
    return {
        commitment_id: CommitmentOrigin(
            label=text("cabinet.origin", date=format_date(held)),
            path=f"/d/cabinet/meetings/{meeting_id}",
            times_postponed=postponed.get(commitment_id, 0),
        )
        for commitment_id, meeting_id, held in rows
    }
