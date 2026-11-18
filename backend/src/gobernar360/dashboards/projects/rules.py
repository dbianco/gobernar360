"""Rules that derive a project's delay, alerts and progress. Pure functions, no database."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

FINISHED = "finished"
DELAYED = "delayed"
EFFECTIVE_STATUSES = ("not_started", "in_progress", DELAYED, FINISHED)


@dataclass(frozen=True)
class MilestoneState:
    due_date: date
    completed_on: date | None


def milestone_in_alert(milestone: MilestoneState, today: date) -> bool:
    """A milestone is in alert once its due date has passed without being completed."""
    return milestone.completed_on is None and milestone.due_date < today


def effective_status(
    status: str, end_date: date | None, milestones: Sequence[MilestoneState], today: date
) -> str:
    """The stored status, or "delayed" when the project is behind its dates."""
    if status == FINISHED:
        return FINISHED
    past_end_date = end_date is not None and end_date < today
    if past_end_date or any(milestone_in_alert(m, today) for m in milestones):
        return DELAYED
    return status


def progress_percent(
    status: str, milestones: Sequence[MilestoneState], manual_progress: int | None
) -> int:
    """Progress from 0 to 100: completed milestones, or the manual value when there are none."""
    if status == FINISHED:
        return 100
    if milestones:
        completed = sum(1 for m in milestones if m.completed_on is not None)
        return round(100 * completed / len(milestones))
    return manual_progress or 0
