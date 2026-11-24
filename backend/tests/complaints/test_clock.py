"""The service clock on its own, over pinned dates.

March 2026: Monday 2, 9, 16, 23 and 30. Tuesday 24 is a holiday in these tests.
"""

from datetime import date

import pytest

from gobernar360.dashboards.complaints.clock import (
    AT_RISK,
    ON_TIME,
    OVERDUE,
    Calendar,
    Step,
    read_clock,
    risk_margin,
)

HOLIDAY = date(2026, 3, 24)
CALENDAR = Calendar(holidays=frozenset({HOLIDAY}))


def d(day: int, month: int = 3) -> date:
    return date(2026, month, day)


MONDAY_2 = date(2026, 3, 2)


def read(steps=(), target=5, today=MONDAY_2, received=MONDAY_2, calendar=CALENDAR):
    return read_clock(received, [Step(on, state) for on, state in steps], target, today, calendar)


def test_business_days_skip_weekends_and_holidays():
    # After Friday 20 up to Wednesday 25: Monday 23 and Wednesday 25; Tuesday 24 is a holiday.
    assert CALENDAR.business_days_between(d(20), d(25)) == 2
    assert CALENDAR.business_days_between(d(2), d(2)) == 0
    assert CALENDAR.business_days_between(d(2), d(30)) == 19
    assert CALENDAR.business_days_between(d(9), d(2)) == 0


def test_business_days_count_every_day_over_long_spans():
    # A year and a bit, compared with walking day by day.
    start, end = date(2025, 12, 29), date(2027, 2, 3)
    walked = sum(
        CALENDAR.is_business_day(date.fromordinal(ordinal))
        for ordinal in range(start.toordinal() + 1, end.toordinal() + 1)
    )
    assert CALENDAR.business_days_between(start, end) == walked


def test_adding_business_days_skips_weekends_and_holidays():
    assert CALENDAR.add_business_days(d(20), 1) == d(23)
    assert CALENDAR.add_business_days(d(20), 2) == d(25)
    assert CALENDAR.add_business_days(d(6), 1) == d(9)
    assert CALENDAR.add_business_days(d(6), 0) == d(6)


def test_a_municipality_can_work_on_saturdays():
    calendar = Calendar(working_weekdays=frozenset({1, 2, 3, 4, 5, 6}))

    assert calendar.business_days_between(d(2), d(9)) == 6
    assert calendar.add_business_days(d(6), 1) == d(7)


def test_a_calendar_needs_a_working_day():
    with pytest.raises(ValueError):
        Calendar(working_weekdays=frozenset())


def test_the_day_of_reception_is_not_counted():
    reading = read(today=d(2))

    assert (reading.used_days, reading.left_days) == (0, 5)
    assert reading.deadline == d(9)
    assert reading.status == ON_TIME


def test_the_clock_runs_over_business_days_only():
    # Received Friday 20; by Wednesday 25 only Monday 23 and Wednesday 25 have counted.
    reading = read(received=d(20), today=d(25))

    assert (reading.used_days, reading.left_days) == (2, 3)
    assert reading.deadline == d(30)


def test_the_clock_stops_while_waiting_for_the_resident():
    steps = [(d(2), "assigned"), (d(3), "waiting")]

    on_thursday = read(steps, today=d(5))
    a_week_later = read(steps, today=d(12))

    # Only Tuesday 3 counted before the wait began.
    assert on_thursday.used_days == a_week_later.used_days == 1
    assert on_thursday.paused and a_week_later.paused
    # While paused, the deadline is where it would fall if work resumed today.
    assert a_week_later.deadline == CALENDAR.add_business_days(d(12), 4)


def test_the_clock_resumes_the_day_after_the_wait_ends():
    steps = [(d(2), "assigned"), (d(3), "waiting"), (d(10), "in_progress")]

    reading = read(steps, today=d(12))

    # Tuesday 3, then Wednesday 11 and Thursday 12; Wednesday 4 to Tuesday 10 were waiting.
    assert reading.used_days == 3
    assert not reading.paused
    assert reading.deadline == d(16)


def test_waiting_and_resuming_the_same_day_costs_nothing():
    before = read([(d(2), "assigned")], received=d(2), today=d(4))
    after = read(
        [(d(2), "assigned"), (d(4), "waiting"), (d(4), "in_progress")], received=d(2), today=d(4)
    )

    assert before.left_days == after.left_days == 3
    assert before.deadline == after.deadline


def test_weekends_holidays_and_waiting_together():
    # Received Thursday 19, waits from Friday 20 to Wednesday 25, resolved Friday 27.
    steps = [
        (d(19), "assigned"),
        (d(20), "waiting"),
        (d(25), "in_progress"),
        (d(27), "resolved"),
    ]

    reading = read(steps, received=d(19), target=3, today=d(31))

    # Friday 20, then Thursday 26 and Friday 27: three days, exactly the target.
    assert reading.used_days == 3
    assert reading.resolved_on == d(27)
    assert reading.status == ON_TIME
    assert reading.deadline == d(27)


def test_a_resolved_complaint_stops_the_clock():
    steps = [(d(2), "assigned"), (d(4), "resolved")]

    reading = read(steps, today=d(30))

    assert (reading.used_days, reading.resolved_on, reading.status) == (2, d(4), ON_TIME)
    assert not reading.paused


def test_a_complaint_resolved_after_its_target_was_late():
    steps = [(d(2), "assigned"), (d(16), "resolved"), (d(17), "closed")]

    reading = read(steps, target=5)

    assert reading.used_days == 10
    assert reading.status == OVERDUE
    assert reading.deadline == d(9)
    assert reading.resolved_on == d(16)


def test_reopening_counts_the_days_it_was_wrongly_resolved():
    steps = [(d(2), "assigned"), (d(3), "resolved"), (d(6), "reopened"), (d(10), "resolved")]

    reading = read(steps, target=5, today=d(12))

    # Tuesday 3 to Tuesday 10 without a break: 6 business days, not 1 + 2.
    assert reading.used_days == 6
    assert reading.status == OVERDUE
    assert reading.resolved_on == d(10)


def test_a_reopened_complaint_runs_on_from_its_resolution():
    steps = [(d(2), "assigned"), (d(3), "resolved"), (d(5), "reopened")]

    reading = read(steps, target=5, today=d(6))

    assert reading.used_days == 4
    assert reading.resolved_on is None
    assert reading.status == AT_RISK


def test_a_rejected_complaint_has_no_outcome():
    reading = read([(d(3), "rejected")], today=d(30))

    assert reading.used_days == 1
    assert reading.status is None
    assert reading.resolved_on is None


@pytest.mark.parametrize(
    ("today", "left", "status"),
    [
        (d(9), 15, ON_TIME),
        (d(20), 6, ON_TIME),
        (d(23), 5, AT_RISK),
        (d(31), 0, AT_RISK),
        (d(1, 4), -1, OVERDUE),
    ],
)
def test_open_complaints_are_on_time_at_risk_or_overdue(today, left, status):
    # A 20-day target is at risk with 5 days or fewer left. Tuesday 24 is a holiday.
    reading = read(target=20, received=d(2), today=today)

    assert (reading.left_days, reading.status) == (left, status)


def test_the_risk_margin_is_a_quarter_of_the_target_and_at_least_a_day():
    assert [risk_margin(target) for target in (1, 2, 4, 5, 20, 30)] == [1, 1, 1, 2, 5, 8]
