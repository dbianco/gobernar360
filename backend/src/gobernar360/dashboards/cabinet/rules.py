"""Rules about commitments. Pure functions, no database."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

OPEN = "open"
DONE = "done"
DROPPED = "dropped"
OVERDUE = "overdue"
# In the order they are shown.
EFFECTIVE_STATES = (OVERDUE, OPEN, DONE, DROPPED)


@dataclass(frozen=True)
class CommitmentState:
    state: str
    due_date: date
    completed_on: date | None


def effective_state(state: str, due_date: date, today: date) -> str:
    """The stored state, or "overdue" for an open commitment past its due date."""
    return OVERDUE if state == OPEN and due_date < today else state


def on_time_share(commitments: Iterable[CommitmentState], today: date) -> float | None:
    """Share delivered by their due date, of those delivered or already overdue.

    Overdue ones count against it: leaving them out would reward not delivering. Those
    still in time and those dropped do not count either way.
    """
    on_time = due = 0
    for commitment in commitments:
        state = effective_state(commitment.state, commitment.due_date, today)
        if state not in (DONE, OVERDUE):
            continue
        due += 1
        on_time += state == DONE and commitment.completed_on <= commitment.due_date
    return round(on_time / due, 4) if due else None


def light_to_discuss[T](lights: Iterable[tuple[int, int, str, T]], today: date) -> T | None:
    """Which of a dashboard's lights, if any, belongs in the agenda.

    The latest one, when it is yellow or red. Otherwise the one of the month that just
    ended, when it is red: the light of the month in progress is provisional, and a green
    one set early does not settle a month that closed in red.

    Lights are (year, month, color, value), newest first and none later than today.
    """
    current = today.year * 12 + today.month
    for position, (year, month, color, value) in enumerate(lights):
        is_latest = position == 0
        if is_latest and color in ("yellow", "red"):
            return value
        if year * 12 + month == current - 1 and color == "red":
            return value
    return None
