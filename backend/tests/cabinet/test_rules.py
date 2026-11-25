from datetime import date

from gobernar360.dashboards.cabinet.rules import (
    CommitmentState,
    effective_state,
    light_to_discuss,
    on_time_share,
)

TODAY = date(2026, 3, 10)
DUE = date(2026, 3, 9)


def light(year: int, month: int, color: str):
    return (year, month, color, f"{year}-{month}")


def test_an_open_commitment_is_overdue_the_day_after_its_due_date():
    assert effective_state("open", date(2026, 3, 10), TODAY) == "open"
    assert effective_state("open", date(2026, 3, 9), TODAY) == "overdue"
    assert effective_state("done", date(2026, 3, 9), TODAY) == "done"
    assert effective_state("dropped", date(2026, 3, 9), TODAY) == "dropped"


def test_the_share_on_time_counts_delivered_and_overdue_only():
    commitments = [
        CommitmentState("done", DUE, DUE),
        CommitmentState("done", DUE, date(2026, 3, 8)),
        CommitmentState("done", DUE, date(2026, 3, 10)),  # late
        CommitmentState("open", DUE, None),  # overdue
        CommitmentState("open", TODAY, None),  # still in time
        CommitmentState("dropped", DUE, None),
    ]

    assert on_time_share(commitments, TODAY) == 0.5


def test_the_share_on_time_is_unknown_while_nothing_was_due():
    assert on_time_share([], TODAY) is None
    assert on_time_share([CommitmentState("open", TODAY, None)], TODAY) is None
    assert on_time_share([CommitmentState("dropped", DUE, None)], TODAY) is None
    assert on_time_share([CommitmentState("open", DUE, None)], TODAY) == 0.0


def test_the_latest_light_is_discussed_when_yellow_or_red():
    assert light_to_discuss([light(2026, 3, "yellow"), light(2026, 2, "red")], TODAY) == "2026-3"
    assert light_to_discuss([light(2026, 3, "red")], TODAY) == "2026-3"
    # However old it is, while there is none later.
    assert light_to_discuss([light(2025, 11, "yellow")], TODAY) == "2025-11"


def test_a_green_latest_light_is_not_discussed():
    assert light_to_discuss([], TODAY) is None
    assert light_to_discuss([light(2026, 3, "green")], TODAY) is None
    assert light_to_discuss([light(2026, 2, "green"), light(2026, 1, "red")], TODAY) is None


def test_a_month_that_just_ended_in_red_is_discussed_even_if_the_current_one_is_green():
    assert light_to_discuss([light(2026, 3, "green"), light(2026, 2, "red")], TODAY) == "2026-2"
    january = date(2026, 1, 5)
    assert light_to_discuss([light(2026, 1, "green"), light(2025, 12, "red")], january) == "2025-12"


def test_only_red_and_only_the_month_just_ended_outlive_a_green_current_month():
    assert light_to_discuss([light(2026, 3, "green"), light(2026, 2, "yellow")], TODAY) is None
    assert light_to_discuss([light(2026, 3, "green"), light(2026, 1, "red")], TODAY) is None
