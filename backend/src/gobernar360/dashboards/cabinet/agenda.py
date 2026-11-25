"""The agenda proposed for a new meeting, and carrying open commitments over to it."""

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select

from gobernar360.dashboards import registry
from gobernar360.dashboards.cabinet.models import AgendaItem, Carryover, Meeting
from gobernar360.dashboards.cabinet.present import taken
from gobernar360.dashboards.cabinet.rules import light_to_discuss
from gobernar360.dashboards.registry import MONTH
from gobernar360.platform import status, subjects
from gobernar360.platform.access import RequestContext, effective_levels, enabled_dashboard_keys
from gobernar360.platform.commitment_models import Commitment
from gobernar360.platform.commitment_rules import OPEN
from gobernar360.platform.subjects import Subject
from gobernar360.platform.tenant_crud import create_entity


@dataclass(frozen=True)
class Proposal:
    # Identifies it while nothing changes: accepting a meeting's agenda refers to it.
    key: str
    source: str
    title: str = ""
    subject: Subject | None = None
    commitment: Commitment | None = None
    carried_from: AgendaItem | None = None


def last_closed_meeting(ctx: RequestContext) -> Meeting | None:
    return ctx.db.scalars(
        select(Meeting)
        .where(Meeting.closed_at.is_not(None))
        .order_by(Meeting.date.desc(), Meeting.closed_at.desc())
        .limit(1)
    ).first()


def open_commitments(ctx: RequestContext) -> list[Commitment]:
    return list(
        ctx.db.scalars(
            taken()
            .where(Commitment.state == OPEN)
            .order_by(Commitment.due_date, Commitment.created_at, Commitment.id)
        ).unique()
    )


def items_of(ctx: RequestContext, meeting: Meeting) -> list[AgendaItem]:
    return list(
        ctx.db.scalars(
            select(AgendaItem)
            .where(AgendaItem.meeting_id == meeting.id)
            .order_by(AgendaItem.position, AgendaItem.created_at, AgendaItem.id)
        )
    )


def _lights(ctx: RequestContext, today: date) -> list[Proposal]:
    """Dashboards whose light asks for attention, those in red first.

    Only the member's own dashboards: proposing the rest would tell them their lights.
    """
    levels = effective_levels(ctx.db, ctx.membership)
    by_color: dict[str, list[Proposal]] = {"red": [], "yellow": []}
    for module in registry.all_modules():
        if module.key not in levels:
            continue
        lights = status.recent(ctx.db, module.key, today)
        light = light_to_discuss([(row.year, row.month, row.color, row) for row in lights], today)
        if light is not None:
            ref = subjects.month_ref(light.year, light.month)
            by_color[light.color].append(
                Proposal(
                    key=f"light:{module.key}:{ref}",
                    source="light",
                    subject=Subject(module.key, MONTH, ref),
                )
            )
    return by_color["red"] + by_color["yellow"]


def _commitments(ctx: RequestContext, meeting_date: date, today: date) -> list[Proposal]:
    """Commitments overdue today or due before the meeting, the oldest first."""
    limit = max(meeting_date, today)
    return [
        Proposal(key=f"commitment:{c.id}", source="commitment", commitment=c)
        for c in open_commitments(ctx)
        if c.due_date < limit
    ]


def _carried(ctx: RequestContext) -> list[Proposal]:
    """What the previous meeting left undiscussed, in the order it had."""
    previous = last_closed_meeting(ctx)
    proposals = []
    for item in items_of(ctx, previous) if previous else []:
        if item.discussed:
            continue
        commitment = ctx.db.get(Commitment, item.commitment_id) if item.commitment_id else None
        if commitment is not None and commitment.state != OPEN:
            # Delivered or dropped meanwhile: nothing left to discuss.
            continue
        proposals.append(
            Proposal(
                key=f"item:{item.id}",
                source=item.source,
                title=item.title,
                subject=item.subject,
                commitment=commitment,
                carried_from=item,
            )
        )
    return proposals


def propose(ctx: RequestContext, meeting_date: date, today: date) -> list[Proposal]:
    """The whole proposal: lights, then commitments, then what was carried.

    Something carried that is also proposed on its own account appears once, where it
    would anyway.
    """
    fresh = _lights(ctx, today) + _commitments(ctx, meeting_date, today)
    lights = {p.subject for p in fresh if p.source == "light"}
    commitments = {p.commitment.id for p in fresh if p.commitment is not None}
    return fresh + [
        p
        for p in _carried(ctx)
        if not (p.source == "light" and p.subject in lights)
        and not (p.commitment is not None and p.commitment.id in commitments)
    ]


def dashboards_not_considered(ctx: RequestContext) -> int:
    enabled = enabled_dashboard_keys(ctx.db, ctx.municipality_id)
    return len(enabled - set(effective_levels(ctx.db, ctx.membership)))


def carry_over(ctx: RequestContext, meeting: Meeting) -> None:
    """Carry every open commitment to a meeting just created, counting it as postponed."""
    for commitment in open_commitments(ctx):
        fields = {"commitment_id": commitment.id, "meeting_id": meeting.id}
        create_entity(ctx, Carryover(**fields), fields)
