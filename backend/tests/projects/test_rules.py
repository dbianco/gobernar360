from datetime import date

from gobernar360.dashboards.projects.rules import (
    MilestoneState,
    effective_status,
    milestone_in_alert,
    progress_percent,
)

TODAY = date(2025, 6, 15)
PAST = date(2025, 6, 14)
FUTURE = date(2025, 7, 1)

DONE = MilestoneState(due_date=PAST, completed_on=PAST)
OVERDUE = MilestoneState(due_date=PAST, completed_on=None)
PENDING = MilestoneState(due_date=FUTURE, completed_on=None)


def test_unfinished_milestone_past_due_is_in_alert():
    assert milestone_in_alert(OVERDUE, TODAY) is True


def test_milestone_due_today_is_not_in_alert():
    assert milestone_in_alert(MilestoneState(due_date=TODAY, completed_on=None), TODAY) is False


def test_completed_milestone_is_never_in_alert():
    assert milestone_in_alert(DONE, TODAY) is False


def test_project_past_end_date_is_delayed():
    assert effective_status("in_progress", PAST, [], TODAY) == "delayed"


def test_project_ending_today_is_not_delayed():
    assert effective_status("in_progress", TODAY, [], TODAY) == "in_progress"


def test_project_with_a_milestone_in_alert_is_delayed():
    assert effective_status("in_progress", FUTURE, [DONE, OVERDUE], TODAY) == "delayed"


def test_not_started_project_past_end_date_is_delayed():
    assert effective_status("not_started", PAST, [], TODAY) == "delayed"


def test_finished_project_is_never_delayed():
    assert effective_status("finished", PAST, [OVERDUE], TODAY) == "finished"


def test_not_started_project_within_dates_keeps_its_status():
    assert effective_status("not_started", FUTURE, [PENDING], TODAY) == "not_started"


def test_project_without_end_date_or_milestones_keeps_its_status():
    assert effective_status("in_progress", None, [], TODAY) == "in_progress"


def test_progress_is_share_of_completed_milestones():
    assert progress_percent("in_progress", [DONE, PENDING, OVERDUE], None) == 33


def test_progress_from_milestones_ignores_manual_value():
    assert progress_percent("in_progress", [DONE, PENDING], 90) == 50


def test_progress_without_milestones_uses_manual_value():
    assert progress_percent("in_progress", [], 40) == 40


def test_progress_without_milestones_or_manual_value_is_zero():
    assert progress_percent("not_started", [], None) == 0


def test_finished_project_progress_is_100():
    assert progress_percent("finished", [PENDING], 10) == 100
