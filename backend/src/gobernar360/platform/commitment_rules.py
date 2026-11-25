"""Rules about commitments. Pure functions, no database."""

from datetime import date

OPEN = "open"
DONE = "done"
DROPPED = "dropped"
OVERDUE = "overdue"
# In the order they are shown.
EFFECTIVE_STATES = (OVERDUE, OPEN, DONE, DROPPED)


def effective_state(state: str, due_date: date, today: date) -> str:
    """The stored state, or "overdue" for an open commitment past its due date."""
    return OVERDUE if state == OPEN and due_date < today else state
