"""How the municipality is delivering on what its cabinet agreed."""

from collections import Counter
from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from gobernar360.dashboards.cabinet.access import Viewer
from gobernar360.dashboards.cabinet.models import Meeting, Taken
from gobernar360.dashboards.cabinet.present import present_commitments, taken
from gobernar360.dashboards.cabinet.rules import CommitmentState, on_time_share
from gobernar360.dashboards.cabinet.schemas import CommitmentOut
from gobernar360.dashboards.registry import IndicatorDefinition, SummaryIndicator
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import Today
from gobernar360.platform.commitment_models import Commitment
from gobernar360.platform.commitment_rules import (
    DONE,
    EFFECTIVE_STATES,
    OPEN,
    OVERDUE,
    effective_state,
)
from gobernar360.platform.directory import UserRef

router = APIRouter()

MOST_POSTPONED = 10

# Commitments are judged by the date agreed in their meeting, which moving them does not
# change, and as they stand today: their history does not say how they stood at the end of a
# past month, so none of these can be rebuilt.
INDICATORS = (
    IndicatorDefinition(
        "cabinet.pending", higher_is_better=False, name="Compromisos pendientes", aggregate=True
    ),
    IndicatorDefinition(
        "cabinet.overdue", higher_is_better=False, name="Compromisos vencidos", aggregate=True
    ),
    IndicatorDefinition("cabinet.done", name="Compromisos cumplidos", aggregate=True),
    IndicatorDefinition(
        "cabinet.on_time_ratio", "ratio", name="Cumplidos en término", aggregate=True
    ),
)


class OwnerRow(BaseModel):
    owner: UserRef
    by_state: dict[str, int]
    on_time_share: float | None


class SummaryOut(BaseModel):
    total: int
    by_state: dict[str, int]
    on_time_share: float | None
    # Whoever owes the most overdue first.
    by_owner: list[OwnerRow]
    # Still open, the most postponed first.
    most_postponed: list[CommitmentOut]
    closed_meetings: int
    last_meeting: date | None


def _judged(commitment: CommitmentOut) -> CommitmentState:
    """The commitment by the date agreed, not by the one it was moved to."""
    stored = OPEN if commitment.state == OVERDUE else commitment.state
    return CommitmentState(stored, commitment.agreed_due_date, commitment.completed_on)


def _states(commitments: list[CommitmentOut], today: date) -> dict[str, int]:
    judged = [_judged(c) for c in commitments]
    counts = Counter(effective_state(c.state, c.due_date, today) for c in judged)
    return {state: counts[state] for state in EFFECTIVE_STATES}


def _on_time(commitments: list[CommitmentOut], today: date) -> float | None:
    return on_time_share((_judged(c) for c in commitments), today)


def _by_owner(commitments: list[CommitmentOut], today: date) -> list[OwnerRow]:
    grouped: dict[object, list[CommitmentOut]] = {}
    for commitment in commitments:
        grouped.setdefault(commitment.owner.id, []).append(commitment)
    rows = [
        OwnerRow(
            owner=group[0].owner,
            by_state=_states(group, today),
            on_time_share=_on_time(group, today),
        )
        for group in grouped.values()
    ]
    return sorted(
        rows,
        key=lambda row: (
            -row.by_state[OVERDUE],
            -row.by_state[OPEN],
            row.owner.full_name,
            str(row.owner.id),
        ),
    )


def _all(ctx: RequestContext, today: date) -> list[CommitmentOut]:
    rows = ctx.db.scalars(
        taken().order_by(Commitment.due_date, Commitment.created_at, Commitment.id)
    ).unique()
    return present_commitments(ctx, list(rows), today)


@router.get("/summary")
def get_dashboard_summary(ctx: Viewer, today: Today) -> SummaryOut:
    commitments = _all(ctx, today)
    postponed = [c for c in commitments if c.state in (OPEN, OVERDUE) and c.times_postponed]
    closed = ctx.db.scalars(
        select(Meeting.date).where(Meeting.closed_at.is_not(None)).order_by(Meeting.date.desc())
    ).all()
    return SummaryOut(
        total=len(commitments),
        by_state=_states(commitments, today),
        on_time_share=_on_time(commitments, today),
        by_owner=_by_owner(commitments, today),
        # Stable sort: among equals, the one due first.
        most_postponed=sorted(postponed, key=lambda c: -c.times_postponed)[:MOST_POSTPONED],
        closed_meetings=len(closed),
        last_meeting=closed[0] if closed else None,
    )


def get_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    """Indicators for the general overview and the monthly snapshot.

    Counted from the rows themselves, never from what a reader may see: the snapshot has no
    member to judge by (`system_context`).
    """
    rows = ctx.db.execute(
        select(Commitment.state, Commitment.agreed_due_date, Commitment.completed_on).join(
            Taken, Taken.commitment_id == Commitment.id
        )
    ).all()
    if not rows:
        return []
    counts = Counter(effective_state(state, due, today) for state, due, _ in rows)
    on_time = on_time_share((CommitmentState(*row) for row in rows), today)
    return [
        SummaryIndicator("cabinet.pending", counts[OPEN] + counts[OVERDUE]),
        SummaryIndicator("cabinet.overdue", counts[OVERDUE]),
        SummaryIndicator("cabinet.done", counts[DONE]),
        SummaryIndicator("cabinet.on_time_ratio", on_time, "ratio"),
    ]
