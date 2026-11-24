"""The service clock: business days a complaint has used of its target.

Pure functions over dates, so they can be tested without a database.

- A stretch from day A to day B counts the business days after A up to and including B:
  the day a complaint arrives is not counted, as with administrative deadlines.
- The clock runs from reception, stops while the case waits for the resident and starts
  again the day the wait ends. It stops when the case is resolved or rejected.
- Reopening picks the clock up from the day the case had been marked resolved: the days
  it spent wrongly resolved count, because the problem was still there.
"""

import math
from bisect import bisect_left, bisect_right
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta

from gobernar360.dashboards.complaints.lifecycle import (
    CLOSED,
    REJECTED,
    REOPENED,
    RESOLVED,
    SOLVED_STATES,
    WAITING,
)

MONDAY_TO_FRIDAY = frozenset({1, 2, 3, 4, 5})
# Guards against walking forever through a calendar with no business day left.
MAX_DAYS_AHEAD = 366 * 20

ON_TIME = "on_time"
AT_RISK = "at_risk"
OVERDUE = "overdue"
CLOCK_STATUSES = (ON_TIME, AT_RISK, OVERDUE)


@dataclass(frozen=True)
class Calendar:
    """Which days count: working weekdays (ISO, Monday = 1) minus holidays."""

    working_weekdays: frozenset[int] = MONDAY_TO_FRIDAY
    holidays: frozenset[date] = frozenset()
    _holidays_on_working_days: tuple[date, ...] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        if not self.working_weekdays:
            raise ValueError("A calendar needs at least one working weekday.")
        counted = sorted(day for day in self.holidays if day.isoweekday() in self.working_weekdays)
        object.__setattr__(self, "_holidays_on_working_days", tuple(counted))

    def is_business_day(self, day: date) -> bool:
        return day.isoweekday() in self.working_weekdays and day not in self.holidays

    def business_days_between(self, start: date, end: date) -> int:
        """Business days after `start` up to and including `end`; 0 when end <= start."""
        if end <= start:
            return 0
        span = (end - start).days
        weeks, rest = divmod(span, 7)
        count = weeks * len(self.working_weekdays)
        for offset in range(1, rest + 1):
            if (start + timedelta(days=weeks * 7 + offset)).isoweekday() in self.working_weekdays:
                count += 1
        holidays = self._holidays_on_working_days
        count -= bisect_right(holidays, end) - bisect_left(holidays, start + timedelta(days=1))
        return count

    def add_business_days(self, start: date, days: int) -> date:
        """The `days`-th business day after `start` (`start` itself when days is 0)."""
        day, counted = start, 0
        for _ in range(MAX_DAYS_AHEAD):
            if counted >= days:
                return day
            day += timedelta(days=1)
            if self.is_business_day(day):
                counted += 1
        raise ValueError("The calendar has no business days ahead.")


@dataclass(frozen=True)
class Step:
    """A change of state, on the local date it happened."""

    on: date
    to_state: str


@dataclass(frozen=True)
class ClockReading:
    target_days: int
    used_days: int
    # Negative once the target has been exceeded.
    left_days: int
    # The business day on which the target is reached. While waiting, assuming the case
    # resumes today.
    deadline: date
    # on_time / at_risk / overdue; None for a rejected complaint, which has no outcome.
    status: str | None
    paused: bool
    # The day it was last resolved, for complaints currently resolved or closed.
    resolved_on: date | None


def risk_margin(target_days: int) -> int:
    """Days left at which a case counts as at risk: a quarter of the target, at least one."""
    return max(1, math.ceil(target_days / 4))


def clock_status(target_days: int, used_days: int, finished: bool) -> str:
    left = target_days - used_days
    if left < 0:
        return OVERDUE
    if finished:
        return ON_TIME
    return AT_RISK if left <= risk_margin(target_days) else ON_TIME


def read_clock(
    received_on: date,
    steps: Iterable[Step],
    target_days: int,
    today: date,
    calendar: Calendar,
) -> ClockReading:
    """Read the clock of one complaint from its state changes, in order."""
    segments: list[tuple[date, date]] = []
    running_since: date | None = received_on
    stopped_on: date | None = None
    state = None
    for step in steps:
        if step.to_state in (WAITING, RESOLVED, REJECTED):
            if running_since is not None:
                segments.append((running_since, step.on))
                running_since = None
            if step.to_state != WAITING:
                stopped_on = step.on
        elif step.to_state == REOPENED:
            running_since, stopped_on = stopped_on, None
        elif step.to_state != CLOSED and state == WAITING:
            running_since = step.on
        state = step.to_state

    closed_days = [calendar.business_days_between(start, end) for start, end in segments]
    used = sum(closed_days)
    if running_since is not None:
        used += calendar.business_days_between(running_since, today)
    paused = state == WAITING
    deadline = _deadline(
        segments, closed_days, running_since, stopped_on, today, target_days, calendar
    )
    if state == REJECTED:
        status = None
    else:
        status = clock_status(target_days, used, finished=state in SOLVED_STATES)
    return ClockReading(
        target_days=target_days,
        used_days=used,
        left_days=target_days - used,
        deadline=deadline,
        status=status,
        paused=paused,
        resolved_on=stopped_on if state in SOLVED_STATES else None,
    )


def _deadline(
    segments: Sequence[tuple[date, date]],
    closed_days: Sequence[int],
    running_since: date | None,
    stopped_on: date | None,
    today: date,
    target_days: int,
    calendar: Calendar,
) -> date:
    remaining = target_days
    for (start, _), days in zip(segments, closed_days, strict=True):
        if days >= remaining:
            return calendar.add_business_days(start, remaining)
        remaining -= days
    # Not reached yet: it will be, counting on from where the clock runs or would run again.
    resume = running_since or stopped_on or today
    return calendar.add_business_days(resume, remaining)
