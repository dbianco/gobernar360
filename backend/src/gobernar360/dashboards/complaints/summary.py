"""Analysis of the complaints: the backlog today and how the period's complaints were solved.

Period figures are about the complaints *received* in the period, so a spreadsheet over
the cases CSV of the same period gives the same medians. The exception is "resolved per
month", which counts resolutions by the month they happened.
"""

import re
import unicodedata
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from gobernar360.core.errors import validation_error
from gobernar360.dashboards.complaints.access import Viewer
from gobernar360.dashboards.complaints.cases import (
    load_calendar,
    load_steps,
    local_date,
    reading_of,
)
from gobernar360.dashboards.complaints.clock import (
    AT_RISK,
    CLOCK_STATUSES,
    ON_TIME,
    OVERDUE,
    ClockReading,
)
from gobernar360.dashboards.complaints.lifecycle import OPEN_STATES, SOLVED_STATES
from gobernar360.dashboards.complaints.models import Complaint
from gobernar360.dashboards.complaints.schemas import (
    AgeCount,
    Backlog,
    GroupResolution,
    MonthFlow,
    NameCount,
    Period,
    RepeatedGroup,
    Resolution,
    StateCount,
    StatusCount,
    SummaryOut,
)
from gobernar360.dashboards.complaints.stats import median, percentile, ratio
from gobernar360.dashboards.registry import IndicatorDefinition, SummaryIndicator
from gobernar360.platform.access import RequestContext
from gobernar360.platform.clock import Today

router = APIRouter()

DEFAULT_MONTHS = 12
DEFAULT_REPEAT_DAYS = 30
TOP = 10
MAX_REPEATED_GROUPS = 20
# Calendar days since reception; the last bucket has no upper end.
AGE_BUCKETS = ((0, 7), (8, 15), (16, 30), (31, 60), (61, 90), (91, None))


@dataclass(frozen=True)
class Window:
    start: date
    end: date

    def __contains__(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True)
class Case:
    complaint: Complaint
    received_on: date
    reading: ClockReading

    @property
    def solved(self) -> bool:
        return self.complaint.state in SOLVED_STATES

    @property
    def open(self) -> bool:
        return self.complaint.state in OPEN_STATES


def default_window(today: date) -> Window:
    """The last twelve months, counting the current one."""
    index = today.year * 12 + today.month - 1 - (DEFAULT_MONTHS - 1)
    return Window(date(index // 12, index % 12 + 1, 1), today)


# The summary has a row per month of the period.
MAX_PERIOD_YEARS = 10


def get_window(
    today: Today,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
) -> Window:
    default = default_window(today)
    window = Window(date_from or default.start, date_to or default.end)
    if window.start > window.end:
        raise validation_error("from must not be after to.")
    months = (window.end.year - window.start.year) * 12 + window.end.month - window.start.month
    if months > MAX_PERIOD_YEARS * 12:
        raise validation_error(f"The period can cover at most {MAX_PERIOD_YEARS} years.")
    return window


PeriodParams = Annotated[Window, Depends(get_window)]
RepeatDays = Annotated[int, Query(ge=1, le=365)]


def load_cases(ctx: RequestContext, today: date) -> list[Case]:
    """Every complaint of the municipality with its clock read as of `today`."""
    query = select(Complaint).order_by(Complaint.received_at, Complaint.number)
    complaints = ctx.db.scalars(query).unique().all()
    calendar = load_calendar(ctx)
    steps = load_steps(ctx)
    return [
        Case(
            complaint=complaint,
            received_on=local_date(complaint.received_at),
            reading=reading_of(complaint, steps.get(complaint.id, []), today, calendar),
        )
        for complaint in complaints
    ]


def received_in(cases: Iterable[Case], window: Window) -> list[Case]:
    return [case for case in cases if case.received_on in window]


def resolution_of(cases: Sequence[Case]) -> Resolution:
    solved = [case.reading for case in cases if case.solved]
    days = [reading.used_days for reading in solved]
    on_time = sum(reading.status == ON_TIME for reading in solved)
    return Resolution(
        received=len(cases),
        resolved=len(solved),
        on_time=on_time,
        on_time_ratio=ratio(on_time, len(solved)),
        median_days=_rounded(median(days)),
        p90_days=_rounded(percentile(days, 0.9)),
    )


def _rounded(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


def resolution_by(
    cases: Sequence[Case], key: Callable[[Complaint], tuple[uuid.UUID, str]]
) -> list[GroupResolution]:
    groups: dict[tuple[uuid.UUID, str], list[Case]] = defaultdict(list)
    for case in cases:
        groups[key(case.complaint)].append(case)
    rows = [
        GroupResolution(id=group_id, name=name, **resolution_of(members).model_dump())
        for (group_id, name), members in groups.items()
    ]
    return sorted(rows, key=lambda row: (normalise_address(row.name), str(row.id)))


def by_type(complaint: Complaint) -> tuple[uuid.UUID, str]:
    return complaint.type_id, complaint.type.name


def by_area(complaint: Complaint) -> tuple[uuid.UUID, str]:
    return complaint.area_id, complaint.area.name


def _backlog(cases: Sequence[Case], today: date) -> Backlog:
    open_cases = [case for case in cases if case.open]
    states = Counter(case.complaint.state for case in open_cases)
    statuses = Counter(case.reading.status for case in open_cases)
    ages = [(today - case.received_on).days for case in open_cases]
    return Backlog(
        open=len(open_cases),
        overdue=statuses[OVERDUE],
        at_risk=statuses[AT_RISK],
        paused=sum(case.reading.paused for case in open_cases),
        by_state=[StateCount(state=state, count=states[state]) for state in OPEN_STATES],
        by_status=[StatusCount(status=status, count=statuses[status]) for status in CLOCK_STATUSES],
        ageing=[
            AgeCount(
                min_days=low,
                max_days=high,
                count=sum(low <= age and (high is None or age <= high) for age in ages),
            )
            for low, high in AGE_BUCKETS
        ],
    )


def _months(window: Window) -> list[str]:
    first = window.start.year * 12 + window.start.month - 1
    last = window.end.year * 12 + window.end.month - 1
    return [f"{index // 12:04d}-{index % 12 + 1:02d}" for index in range(first, last + 1)]


def _monthly(cases: Sequence[Case], window: Window) -> list[MonthFlow]:
    received = Counter(case.received_on.strftime("%Y-%m") for case in received_in(cases, window))
    resolved = Counter(
        case.reading.resolved_on.strftime("%Y-%m")
        for case in cases
        if case.reading.resolved_on is not None and case.reading.resolved_on in window
    )
    return [
        MonthFlow(month=month, received=received[month], resolved=resolved[month])
        for month in _months(window)
    ]


def normalise_address(address: str) -> str:
    """How an address is compared, and names sorted: no case, accents, punctuation or
    repeated spaces."""
    decomposed = unicodedata.normalize("NFKD", address.lower())
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return " ".join(re.sub(r"[^\w\s]", " ", plain).split())


def repeated_groups(cases: Sequence[Case], repeat_days: int) -> list[RepeatedGroup]:
    """Complaints of one type at one address, each within `repeat_days` of the previous one."""
    places: dict[tuple[uuid.UUID, str], list[Case]] = defaultdict(list)
    for case in cases:
        places[(case.complaint.type_id, normalise_address(case.complaint.address))].append(case)
    groups: list[list[Case]] = []
    for place in places.values():
        place.sort(key=lambda case: (case.complaint.received_at, case.complaint.number))
        run = [place[0]]
        for case in place[1:]:
            if (case.received_on - run[-1].received_on).days <= repeat_days:
                run.append(case)
            else:
                groups.append(run)
                run = [case]
        groups.append(run)
    rows = [
        RepeatedGroup(
            type=run[-1].complaint.type.name,
            address=run[-1].complaint.address,
            zone=run[-1].complaint.zone.name,
            count=len(run),
            first_received=run[0].received_on,
            last_received=run[-1].received_on,
            numbers=[case.complaint.number for case in run],
        )
        for run in groups
        if len(run) > 1
    ]
    rows.sort(key=lambda row: (-row.count, -row.last_received.toordinal(), row.address))
    return rows[:MAX_REPEATED_GROUPS]


def _top(names: Iterable[str]) -> list[NameCount]:
    counts = Counter(names)
    ranked = sorted(counts.items(), key=lambda item: (-item[1], normalise_address(item[0])))
    return [NameCount(name=name, count=count) for name, count in ranked[:TOP]]


def summary_of(
    cases: Sequence[Case], window: Window, today: date, repeat_days: int = DEFAULT_REPEAT_DAYS
) -> SummaryOut:
    period = received_in(cases, window)
    return SummaryOut(
        period=Period(date_from=window.start, date_to=window.end),
        repeat_days=repeat_days,
        backlog=_backlog(cases, today),
        totals=resolution_of(period),
        monthly=_monthly(cases, window),
        by_type=resolution_by(period, by_type),
        by_area=resolution_by(period, by_area),
        repeated=repeated_groups(period, repeat_days),
        top_zones=_top(case.complaint.zone.name for case in period),
        top_types=_top(case.complaint.type.name for case in period),
    )


@router.get("/summary")
def get_dashboard_summary(
    ctx: Viewer, today: Today, window: PeriodParams, repeat_days: RepeatDays = DEFAULT_REPEAT_DAYS
) -> SummaryOut:
    return summary_of(load_cases(ctx, today), window, today, repeat_days)


# None can be rebuilt for a past date: they depend on the state each case is in today.
INDICATORS = (
    IndicatorDefinition(
        "complaints.open", higher_is_better=False, name="Reclamos abiertos", aggregate=True
    ),
    IndicatorDefinition(
        "complaints.overdue", higher_is_better=False, name="Reclamos vencidos", aggregate=True
    ),
    IndicatorDefinition(
        "complaints.on_time_ratio", "ratio", name="Reclamos resueltos en plazo", aggregate=True
    ),
    IndicatorDefinition(
        "complaints.median_resolution_days",
        higher_is_better=False,
        name="Mediana de resolución (días hábiles)",
        aggregate=True,
    ),
)


def get_summary(ctx: RequestContext, today: date) -> list[SummaryIndicator]:
    """Indicators for the general overview: today's backlog and the last twelve months."""
    if not ctx.db.scalar(select(func.count()).select_from(Complaint)):
        return []
    summary = summary_of(load_cases(ctx, today), default_window(today), today)
    return [
        SummaryIndicator("complaints.open", summary.backlog.open),
        SummaryIndicator("complaints.overdue", summary.backlog.overdue),
        SummaryIndicator("complaints.on_time_ratio", summary.totals.on_time_ratio, "ratio"),
        SummaryIndicator("complaints.median_resolution_days", summary.totals.median_days),
    ]
