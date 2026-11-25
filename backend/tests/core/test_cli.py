"""The commands an operator runs, by what they print, return and leave in the database."""

import logging

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from gobernar360 import cli, seed
from gobernar360.core.db import platform_session
from gobernar360.core.security import verify_password
from gobernar360.platform import notifications, outbox
from gobernar360.platform.models import Municipality, User
from gobernar360.platform.notifications import NotifyReport
from gobernar360.platform.outbox import DeliveryReport
from tests.factories import make_user


def run(*args: str, **options):
    return CliRunner().invoke(cli.app, list(args), **options)


def operators() -> list[User]:
    with platform_session() as db:
        return list(db.scalars(select(User)))


def create_operator(email: str, password: str = "long-password-1"):
    return run(
        "create-operator",
        "--email",
        email,
        "--full-name",
        "Operadora",
        input=f"{password}\n{password}\n",
    )


# create-operator


def test_create_operator_leaves_an_operator_who_can_sign_in():
    result = create_operator(" Op@Gobernar360.test ")

    assert result.exit_code == 0, result.output
    assert "Operator op@gobernar360.test created." in result.output
    [operator] = operators()
    assert (operator.email, operator.full_name) == ("op@gobernar360.test", "Operadora")
    assert operator.is_platform_operator is True
    assert verify_password("long-password-1", operator.password_hash)


def test_create_operator_refuses_an_email_that_already_has_an_account():
    make_user("op@gobernar360.test")

    result = create_operator("OP@gobernar360.test")

    assert result.exit_code == 2
    assert "A user with email op@gobernar360.test already exists." in result.output
    assert [user.is_platform_operator for user in operators()] == [False]


def test_create_operator_takes_passwords_of_ten_characters_and_not_of_nine():
    refused = create_operator("op@gobernar360.test", "123456789")

    assert refused.exit_code == 2
    assert "Password must have at least 10 characters." in refused.output
    assert operators() == []
    assert create_operator("op@gobernar360.test", "1234567890").exit_code == 0


def test_create_operator_asks_for_the_password_twice():
    result = run(
        "create-operator",
        "--email",
        "op@gobernar360.test",
        "--full-name",
        "Operadora",
        input="long-password-1\nanother-one-2\n",
    )

    assert result.exit_code != 0
    assert "do not match" in result.output
    assert "long-password-1" not in result.output
    assert operators() == []


# seed-demo


def test_seed_demo_says_which_password_every_account_has_and_then_that_nothing_changed():
    first, second = run("seed-demo"), run("seed-demo")

    assert (first.exit_code, second.exit_code) == (0, 0)
    assert first.output == (
        "Demo data loaded. Every demo account uses the password: gobernar360-demo\n"
    )
    assert second.output == "Demo data already present; nothing changed.\n"


@pytest.mark.parametrize(("options", "reset"), [([], False), (["--reset"], True)])
def test_seed_demo_deletes_everything_only_when_asked_to(monkeypatch, options, reset):
    asked = []
    monkeypatch.setattr(seed, "seed_demo", lambda reset: asked.append(reset) or True)

    assert run("seed-demo", *options).exit_code == 0

    assert asked == [reset]


def test_seed_demo_keeps_what_there_was_when_not_asked_to_reset():
    make_user("real@noetinger.test")

    run("seed-demo")

    assert "real@noetinger.test" in {user.email for user in operators()}
    with platform_session() as db:
        assert len(db.scalars(select(Municipality)).all()) == 2


# send-email


@pytest.fixture
def deliveries(monkeypatch):
    """Replaces delivery: gives the reports listed, one per call, and records how it was
    called."""

    class Deliveries:
        def __init__(self):
            self.reports: list[DeliveryReport | BaseException] = []
            self.calls: list[tuple[str, bool]] = []

    state = Deliveries()

    def deliver(transport, sender, due_only):
        state.calls.append((sender, due_only))
        report = state.reports.pop(0)
        if isinstance(report, BaseException):
            raise report
        return report

    monkeypatch.setattr(outbox, "deliver", deliver)
    return state


SENDER = "gobernar360 <no-reply@gobernar360.test>"


def test_send_email_sends_everything_pending_once_and_says_how_it_went(deliveries):
    deliveries.reports = [DeliveryReport(sent=3)]

    result = run("send-email")

    assert result.exit_code == 0
    assert result.output == "Sent: 3. Will be retried: 0. Failed: 0.\n"
    # Not only those due: whoever runs it by hand has just mended the server.
    assert deliveries.calls == [(SENDER, False)]


@pytest.mark.parametrize(
    "report", [DeliveryReport(sent=1, retrying=1), DeliveryReport(sent=1, failed=1)]
)
def test_send_email_ends_in_error_when_something_was_not_sent(deliveries, report):
    deliveries.reports = [report]

    result = run("send-email")

    assert result.exit_code == 1
    assert result.output == (
        f"Sent: 1. Will be retried: {report.retrying}. Failed: {report.failed}.\n"
    )


def test_send_email_gives_those_that_failed_another_round_only_when_asked(deliveries, monkeypatch):
    monkeypatch.setattr(outbox, "requeue_failed", lambda: 4)
    deliveries.reports = [DeliveryReport(sent=4), DeliveryReport()]

    retried, plain = run("send-email", "--retry-failed"), run("send-email")

    assert retried.output == (
        "4 failed emails queued again.\nSent: 4. Will be retried: 0. Failed: 0.\n"
    )
    assert plain.output == "Sent: 0. Will be retried: 0. Failed: 0.\n"


@pytest.fixture
def naps(monkeypatch):
    taken = []
    monkeypatch.setattr(cli.time, "sleep", taken.append)
    return taken


def test_send_email_watching_delivers_what_is_due_until_it_is_stopped(deliveries, naps):
    deliveries.reports = [
        DeliveryReport(sent=1, retrying=1),
        DeliveryReport(),
        DeliveryReport(failed=2),
        KeyboardInterrupt(),
    ]

    result = run("send-email", "--watch", "--interval", "2.5")

    assert result.exit_code == 0
    # Nothing is said of a check that found nothing.
    assert result.output == (
        "Delivering emails every 2.5 s. Ctrl+C stops.\n"
        "Sent: 1. Will be retried: 1. Failed: 0.\n"
        "Sent: 0. Will be retried: 0. Failed: 2.\n"
        "Stopped.\n"
    )
    assert naps == [2.5, 2.5, 2.5]
    assert deliveries.calls == [(SENDER, True)] * 4


def test_send_email_watches_every_five_seconds_unless_told_otherwise(deliveries, naps):
    deliveries.reports = [DeliveryReport(), KeyboardInterrupt()]

    result = run("send-email", "--watch")

    assert result.output == "Delivering emails every 5 s. Ctrl+C stops.\nStopped.\n"
    assert naps == [5]


def test_send_email_logs_when_each_thing_happened(deliveries, monkeypatch):
    configured = []
    monkeypatch.setattr(logging, "basicConfig", lambda **options: configured.append(options))
    deliveries.reports = [DeliveryReport()]

    run("send-email")

    assert configured == [{"level": logging.INFO, "format": "%(asctime)s %(message)s"}]


# notify


@pytest.fixture
def notified(monkeypatch):
    """What `notify` will answer."""
    report = NotifyReport()
    monkeypatch.setattr(notifications, "notify", lambda today: report)
    return report


def test_notify_queues_and_sends_right_away(deliveries, notified):
    notified.municipalities, notified.emails = 2, 3
    deliveries.reports = [DeliveryReport(sent=2, retrying=1)]

    result = run("notify")

    assert result.exit_code == 0
    assert result.output == (
        "Notification emails queued: 3 (2 municipalities checked).\nSent: 2. Will be retried: 1.\n"
    )
    assert deliveries.calls == [(SENDER, True)]


def test_notify_sends_nothing_when_it_queued_nothing(deliveries, notified):
    notified.municipalities = 2

    result = run("notify")

    assert result.output == "Notification emails queued: 0 (2 municipalities checked).\n"
    assert deliveries.calls == []


def test_notify_leaves_the_sending_to_others_when_asked(deliveries, notified):
    notified.municipalities, notified.emails = 2, 3

    result = run("notify", "--no-send")

    assert result.output == "Notification emails queued: 3 (2 municipalities checked).\n"
    assert deliveries.calls == []


def test_without_a_command_it_lists_them_all():
    result = run()

    for command in ("create-operator", "seed-demo", "send-email", "notify"):
        assert command in result.output
