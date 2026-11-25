"""The commands as an operator types them: what they do and what they say."""

import re
from datetime import date

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from gobernar360 import cli, seed
from gobernar360.core.db import platform_session
from gobernar360.core.security import verify_password
from gobernar360.dashboards import registry
from gobernar360.platform import clock, notifications, outbox
from gobernar360.platform.models import EmailOutbox, User
from gobernar360.platform.notifications import NotifyReport
from gobernar360.platform.outbox import DeliveryReport
from tests.factories import admin_session, make_user

PASSWORD = "long-password-1"


def _run(*args: str, **options):
    return CliRunner().invoke(cli.app, list(args), **options)


def _plain(output: str) -> str:
    """Without the frame and the line breaks errors are drawn with."""
    return re.sub(r"[│╭╮╰╯─\s]+", " ", output)


def test_without_a_command_the_help_is_shown():
    result = _run()

    assert "gobernar360 administration commands." in result.output
    for command in ("create-operator", "seed-demo", "send-email", "notify", "assign-zones"):
        assert command in result.output


# create-operator


def test_create_operator_saves_what_was_typed_and_says_so():
    result = _run(
        "create-operator", "--email", " Op@Example.TEST ", "--full-name", "Olga Operadora",
        input=f"{PASSWORD}\n{PASSWORD}\n",
    )  # fmt: skip

    assert result.output.splitlines()[-1] == "Operator op@example.test created."
    with platform_session() as db:
        user = db.scalars(select(User)).one()
    assert (user.email, user.full_name) == ("op@example.test", "Olga Operadora")
    assert verify_password(PASSWORD, user.password_hash)
    assert PASSWORD not in result.output


def test_create_operator_refuses_an_email_already_in_use():
    make_user("op@example.test")

    result = _run(
        "create-operator", "--email", "OP@example.test", "--full-name", "Olga",
        input=f"{PASSWORD}\n{PASSWORD}\n",
    )  # fmt: skip

    assert result.exit_code == 2
    assert "A user with email op@example.test already exists." in _plain(result.output)
    with platform_session() as db:
        assert [user.is_platform_operator for user in db.scalars(select(User))] == [False]


@pytest.mark.parametrize(("password", "code"), [("a" * 9, 2), ("a" * 10, 0)])
def test_create_operator_needs_a_long_password(password, code):
    result = _run(
        "create-operator", "--email", "op@example.test", "--full-name", "Olga",
        input=f"{password}\n{password}\n",
    )  # fmt: skip

    assert result.exit_code == code
    if code:
        assert "Password must have at least 10 characters." in _plain(result.output)


# seed-demo


def test_seed_demo_says_whether_it_loaded_anything(monkeypatch):
    asked = []

    def load(reset):
        asked.append(reset)
        return reset

    monkeypatch.setattr(seed, "seed_demo", load)

    assert _run("seed-demo").output == "Demo data already present; nothing changed.\n"
    assert _run("seed-demo", "--reset").output == (
        "Demo data loaded. Every demo account uses the password: gobernar360-demo\n"
    )
    assert asked == [False, True]


# send-email


@pytest.fixture
def deliveries(monkeypatch):
    """What each delivery finds, and how it was asked for."""
    reports: list[DeliveryReport] = []
    asked: list[dict] = []

    def deliver(transport, sender, due_only):
        asked.append({"transport": type(transport), "sender": sender, "due_only": due_only})
        return reports.pop(0)

    monkeypatch.setattr(outbox, "deliver", deliver)
    return reports, asked


@pytest.mark.parametrize(
    ("report", "code", "said"),
    [
        (DeliveryReport(sent=2), 0, "Sent: 2. Will be retried: 0. Failed: 0."),
        (DeliveryReport(retrying=1), 1, "Sent: 0. Will be retried: 1. Failed: 0."),
        (DeliveryReport(sent=1, failed=3), 1, "Sent: 1. Will be retried: 0. Failed: 3."),
        (DeliveryReport(), 0, "Sent: 0. Will be retried: 0. Failed: 0."),
    ],
)
def test_send_email_reports_and_fails_when_anything_is_left(deliveries, report, code, said):
    reports, asked = deliveries
    reports.append(report)

    result = _run("send-email")

    assert (result.exit_code, result.output) == (code, f"{said}\n")
    # Everything pending, also what waits for its turn to be retried.
    assert asked == [
        {
            "transport": outbox.SmtpTransport,
            "sender": "gobernar360 <no-reply@gobernar360.test>",
            "due_only": False,
        }
    ]


def test_send_email_can_try_failed_emails_again(deliveries):
    reports, _ = deliveries
    reports.append(DeliveryReport())
    with admin_session() as session, session.begin():
        for status in ("failed", "failed", "pending"):
            session.add(
                EmailOutbox(to_address="a@example.test", subject="s", body="b", status=status)
            )

    result = _run("send-email", "--retry-failed")

    assert result.output.splitlines()[0] == "2 failed emails queued again."
    with admin_session() as session:
        assert set(session.scalars(select(EmailOutbox.status))) == {"pending"}


def test_send_email_watches_until_it_is_stopped(deliveries, monkeypatch):
    reports, asked = deliveries
    reports += [DeliveryReport(), DeliveryReport(sent=1, retrying=2, failed=3)]
    slept = []

    def sleep(seconds):
        slept.append(seconds)
        if not reports:
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", sleep)

    result = _run("send-email", "--watch", "--interval", "2.5")

    assert result.exit_code == 0
    # A round without emails says nothing.
    assert result.output.splitlines() == [
        "Delivering emails every 2.5 s. Ctrl+C stops.",
        "Sent: 1. Will be retried: 2. Failed: 3.",
        "Stopped.",
    ]
    assert slept == [2.5, 2.5]
    assert [call["due_only"] for call in asked] == [True, True]


def test_send_email_waits_five_seconds_unless_told_otherwise(deliveries, monkeypatch):
    reports, _ = deliveries
    reports.append(DeliveryReport())

    def sleep(seconds):
        assert seconds == 5
        raise KeyboardInterrupt

    monkeypatch.setattr(cli.time, "sleep", sleep)

    assert _run("send-email", "--watch").output.splitlines()[0] == (
        "Delivering emails every 5 s. Ctrl+C stops."
    )


# notify


@pytest.fixture
def notified(monkeypatch):
    days = []

    def install(report: NotifyReport):
        def notify(today):
            days.append(today)
            return report

        monkeypatch.setattr(notifications, "notify", notify)

    monkeypatch.setattr(clock, "get_today", lambda: date(2026, 3, 4))
    return install, days


def test_notify_queues_emails_and_delivers_them(notified, deliveries):
    install, days = notified
    install(NotifyReport(emails=3, municipalities=2))
    reports, asked = deliveries
    reports.append(DeliveryReport(sent=2, retrying=1))
    # The command runs outside the API, which is what installs the dashboards.
    installed = registry.all_modules()
    for module in installed:
        registry.unregister(module.key)

    result = _run("notify")

    assert result.output.splitlines() == [
        "Notification emails queued: 3 (2 municipalities checked).",
        "Sent: 2. Will be retried: 1.",
    ]
    assert [call["due_only"] for call in asked] == [True]
    assert days == [date(2026, 3, 4)]
    assert {module.key for module in registry.all_modules()} == {
        "projects",
        "environment",
        "economic",
        "social",
        "procedures",
    }


@pytest.mark.parametrize(("emails", "args"), [(0, []), (3, ["--no-send"])])
def test_notify_delivers_nothing_when_there_is_nothing_or_it_is_told_not_to(
    notified, deliveries, emails, args
):
    install, _ = notified
    install(NotifyReport(emails=emails, municipalities=1))

    result = _run("notify", *args)

    assert result.exit_code == 0
    assert result.output == f"Notification emails queued: {emails} (1 municipalities checked).\n"
    assert deliveries[1] == []
