"""The states a complaint goes through and the only moves allowed between them."""

RECEIVED = "received"
ASSIGNED = "assigned"
IN_PROGRESS = "in_progress"
WAITING = "waiting"
RESOLVED = "resolved"
CLOSED = "closed"
REJECTED = "rejected"
REOPENED = "reopened"

STATES = (RECEIVED, ASSIGNED, IN_PROGRESS, WAITING, RESOLVED, CLOSED, REJECTED, REOPENED)

TRANSITIONS: dict[str, tuple[str, ...]] = {
    RECEIVED: (ASSIGNED, REJECTED),
    ASSIGNED: (IN_PROGRESS, WAITING, RESOLVED, REJECTED),
    IN_PROGRESS: (WAITING, RESOLVED, REJECTED),
    # Back to work once the resident answers, or dropped when they never do.
    WAITING: (IN_PROGRESS, REJECTED),
    RESOLVED: (CLOSED, REOPENED),
    REOPENED: (IN_PROGRESS, WAITING, RESOLVED, REJECTED),
    CLOSED: (),
    REJECTED: (),
}

# Someone still has to act on these.
OPEN_STATES = (RECEIVED, ASSIGNED, IN_PROGRESS, WAITING, REOPENED)
# Solved, for every resolution figure.
SOLVED_STATES = (RESOLVED, CLOSED)
# Moves that must say why.
NOTE_REQUIRED = (REJECTED, REOPENED)

# Kinds of timeline entries.
CREATED = "created"
TRANSITION = "transition"
REASSIGNED = "reassigned"
RETYPED = "retyped"
COMMENT = "comment"
EVENT_KINDS = (CREATED, TRANSITION, REASSIGNED, RETYPED, COMMENT)


def allowed_moves(state: str) -> tuple[str, ...]:
    return TRANSITIONS[state]


def can_move(state: str, to_state: str) -> bool:
    return to_state in TRANSITIONS.get(state, ())


def is_open(state: str) -> bool:
    return state in OPEN_STATES
