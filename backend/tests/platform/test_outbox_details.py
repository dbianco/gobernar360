"""The finer points of the outbox: the message it builds, what a run reports and logs,
and how the SMTP transport connects and reads the server's answers."""

import logging
import smtplib
import uuid
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

import pytest
from sqlalchemy import select

from gobernar360.core.config import get_settings
from gobernar360.core.db import platform_session
from gobernar360.platform import outbox
from gobernar360.platform.models import EmailOutbox
from tests.factories import admin_session

SENDER = "gobernar360 <no-reply@mail.gobernar360.test>"
CREATED = datetime(2026, 3, 2, 13, 45, 10, tzinfo=UTC)


def _row(**changes) -> EmailOutbox:
    values = {
        "id": uuid.UUID("00000000-0000-0000-0000-000000000007"),
        "to_address": "ana@noetinger.test",
        "subject": "Hola",
        "body": "Texto",
        "body_html": None,
        "created_at": CREATED,
    } | changes
    return EmailOutbox(**values)


# The message


def test_the_message_has_its_headers_in_order_and_with_their_usual_names():
    message = outbox.build_message(_row(), SENDER)

    assert list(message.keys()) == [
        "From",
        "To",
        "Subject",
        "Date",
        "Message-ID",
        "Content-Type",
        "Content-Transfer-Encoding",
        "MIME-Version",
    ]
    assert message["Date"] == "Mon, 02 Mar 2026 13:45:10 +0000"
    assert message["Message-ID"] == "<00000000-0000-0000-0000-000000000007@mail.gobernar360.test>"


def test_the_message_id_uses_the_domain_after_the_last_at_sign():
    message = outbox.build_message(_row(), '"a@b" <no-reply@last.test>')
    assert message["Message-ID"].endswith("@last.test>")


def test_the_message_id_has_a_domain_even_when_the_sender_has_none():
    message = outbox.build_message(_row(), "gobernar360")
    assert message["Message-ID"] == "<00000000-0000-0000-0000-000000000007@gobernar360>"


def test_the_html_version_is_an_html_alternative():
    message = outbox.build_message(_row(body_html="<p>Hola</p>"), SENDER)

    html = message.get_body(preferencelist=("html",))
    assert html.get_content_type() == "text/html"
    assert "Content-Type: text/html" in html.as_string()


# Queueing


def test_a_queued_subject_is_one_line_of_at_most_300_characters():
    with platform_session() as db:
        outbox.enqueue(db, "ana@noetinger.test", "  Hola\n\t" + "x" * 400, "Texto")

    with admin_session() as session:
        row = session.scalars(select(EmailOutbox)).one()
    assert row.subject == ("Hola " + "x" * 400)[:300]
    assert (row.status, row.attempts, row.body_html) == ("pending", 0, None)


# A run


class Transport:
    def __init__(self, *outcomes: Exception | None) -> None:
        self.outcomes = list(outcomes)
        self.sent: list[EmailMessage] = []

    def send(self, message: EmailMessage) -> None:
        outcome = self.outcomes.pop(0) if self.outcomes else None
        if outcome is not None:
            raise outcome
        self.sent.append(message)


def _queue(*subjects: str) -> None:
    for subject in subjects:
        with platform_session() as db:
            outbox.enqueue(db, "ana@noetinger.test", subject, "Texto")


def _rows() -> list[EmailOutbox]:
    with admin_session() as session:
        return list(session.scalars(select(EmailOutbox).order_by(EmailOutbox.created_at)))


def test_a_run_reports_each_outcome_and_sends_the_oldest_first(caplog):
    _queue("uno", "dos", "tres", "cuatro")
    now = datetime.now(UTC)
    transport = Transport(
        None, outbox.PermanentFailure("550 no such user"), RuntimeError("421 busy"), None
    )

    with caplog.at_level(logging.WARNING, logger="gobernar360.platform.outbox"):
        report = outbox.deliver(transport, SENDER, now=lambda: now)

    assert (report.sent, report.failed, report.retrying, report.attempted) == (2, 1, 1, 4)
    assert [message["Subject"] for message in transport.sent] == ["uno", "cuatro"]
    sent, refused, retrying, last = _rows()
    assert (sent.status, sent.attempts, sent.sent_at, sent.last_error) == ("sent", 0, now, None)
    assert (refused.status, refused.attempts) == ("failed", 1)
    assert refused.last_error == "PermanentFailure: 550 no such user"
    assert (retrying.status, retrying.attempts) == ("pending", 1)
    assert retrying.last_error == "RuntimeError: 421 busy"
    assert retrying.next_attempt_at == now + timedelta(seconds=30)
    assert last.status == "sent"
    assert [record.getMessage() for record in caplog.records] == [
        f"Email {refused.id} to ana@noetinger.test refused: 550 no such user",
        f"Email {retrying.id} not sent (attempt 1): 421 busy",
    ]


def test_a_message_due_right_now_is_sent():
    _queue("uno")
    [row] = _rows()

    report = outbox.deliver(Transport(), SENDER, now=lambda: row.next_attempt_at)

    assert report.sent == 1


def test_the_error_kept_is_cut_at_2000_characters():
    _queue("uno")

    outbox.deliver(Transport(RuntimeError("x" * 3000)), SENDER)

    assert _rows()[0].last_error == ("RuntimeError: " + "x" * 3000)[:2000]


def test_a_message_given_up_counts_as_failed_with_its_last_error():
    _queue("uno")
    with admin_session() as session, session.begin():
        session.scalars(select(EmailOutbox)).one().attempts = outbox.MAX_ATTEMPTS - 2
    transport = Transport(RuntimeError("still"))

    first = outbox.deliver(transport, SENDER, due_only=False)
    second = outbox.deliver(Transport(RuntimeError("again")), SENDER, due_only=False)

    assert (first.retrying, first.failed) == (1, 0)
    assert (second.retrying, second.failed) == (0, 1)
    [row] = _rows()
    assert (row.status, row.attempts, row.last_error) == (
        "failed",
        outbox.MAX_ATTEMPTS,
        "RuntimeError: again",
    )


def test_failures_other_than_an_unreachable_server_do_not_stop_the_run():
    _queue("uno", "dos")

    report = outbox.deliver(Transport(RuntimeError("421 busy"), None), SENDER)

    assert (report.retrying, report.sent) == (1, 1)


def test_requeueing_gives_failed_messages_a_fresh_start_and_counts_them():
    _queue("uno", "dos", "tres")
    outbox.deliver(
        Transport(outbox.PermanentFailure("550"), outbox.PermanentFailure("550"), None), SENDER
    )

    assert outbox.pending_count() == 0
    assert outbox.requeue_failed() == 2
    assert outbox.pending_count() == 2
    assert [(row.status, row.attempts) for row in _rows()] == [
        ("pending", 0),
        ("pending", 0),
        ("sent", 0),
    ]
    assert outbox.requeue_failed() == 0


# The SMTP transport


class FakeSmtp:
    """Stands in for smtplib.SMTP and SMTP_SSL, recording how it was used."""

    instances: list["FakeSmtp"] = []
    failure: Exception | None = None

    def __init__(self, host, port, timeout=None, context=None) -> None:
        self.connection = (host, port, timeout)
        self.context = context
        self.calls: list[tuple] = []
        FakeSmtp.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append(("quit",))

    def starttls(self, context=None):
        self.calls.append(("starttls", context is not None))

    def login(self, user, password):
        self.calls.append(("login", user, password))

    def send_message(self, message):
        if FakeSmtp.failure is not None:
            raise FakeSmtp.failure
        self.calls.append(("send", message["To"]))


class FakeSmtpSsl(FakeSmtp):
    pass


@pytest.fixture
def smtp(monkeypatch):
    FakeSmtp.instances = []
    FakeSmtp.failure = None
    monkeypatch.setattr(outbox.smtplib, "SMTP", FakeSmtp)
    monkeypatch.setattr(outbox.smtplib, "SMTP_SSL", FakeSmtpSsl)
    settings = get_settings().model_copy(
        update={
            "smtp_host": "mail.test",
            "smtp_port": 2525,
            "smtp_timeout_seconds": 7,
            "smtp_username": "",
            "smtp_password": "",
            "smtp_security": "none",
        }
    )
    return settings


def _send(settings, **changes) -> FakeSmtp:
    transport = outbox.SmtpTransport(settings.model_copy(update=changes))
    transport.send(outbox.build_message(_row(), SENDER))
    return FakeSmtp.instances[-1]


def test_plain_smtp_connects_with_the_settings_and_sends(smtp):
    server = _send(smtp)

    assert type(server) is FakeSmtp
    assert server.connection == ("mail.test", 2525, 7)
    assert server.calls == [("send", "ana@noetinger.test"), ("quit",)]


def test_starttls_upgrades_the_connection_before_sending(smtp):
    server = _send(smtp, smtp_security="starttls")

    assert type(server) is FakeSmtp
    assert server.calls[0] == ("starttls", True)


def test_tls_connects_encrypted_from_the_start(smtp):
    server = _send(smtp, smtp_security="tls")

    assert type(server) is FakeSmtpSsl
    assert server.connection == ("mail.test", 2525, 7)
    assert server.context is not None
    assert ("starttls", True) not in server.calls


def test_the_transport_signs_in_when_it_has_a_user(smtp):
    server = _send(smtp, smtp_username="mailer", smtp_password="s3cret")

    assert server.calls[0] == ("login", "mailer", "s3cret")


def _refused(*codes: int) -> smtplib.SMTPRecipientsRefused:
    return smtplib.SMTPRecipientsRefused(
        {f"r{index}@x.test": (code, b"no") for index, code in enumerate(codes)}
    )


def test_recipients_all_refused_for_good_are_a_permanent_failure(smtp):
    FakeSmtp.failure = _refused(550, 553)

    with pytest.raises(outbox.PermanentFailure) as raised:
        _send(smtp)
    assert "550" in str(raised.value)


def test_a_refusal_with_code_500_is_permanent_too(smtp):
    FakeSmtp.failure = _refused(500)

    with pytest.raises(outbox.PermanentFailure):
        _send(smtp)


@pytest.mark.parametrize("codes", [(450,), (550, 451), (499,), ()])
def test_recipients_refused_for_now_are_tried_again(smtp, codes):
    FakeSmtp.failure = _refused(*codes)

    with pytest.raises(smtplib.SMTPRecipientsRefused):
        _send(smtp)


def test_a_server_that_refuses_the_connection_is_unavailable(smtp):
    FakeSmtp.failure = smtplib.SMTPConnectError(421, "closing")

    with pytest.raises(outbox.ServerUnavailable) as raised:
        _send(smtp)
    assert "closing" in str(raised.value)


def test_an_error_answer_is_passed_on_to_be_tried_again(smtp):
    FakeSmtp.failure = smtplib.SMTPDataError(451, "try later")

    with pytest.raises(smtplib.SMTPDataError):
        _send(smtp)


def test_a_lost_connection_is_unavailable_and_named_even_without_a_message(smtp):
    FakeSmtp.failure = TimeoutError()
    with pytest.raises(outbox.ServerUnavailable) as raised:
        _send(smtp)
    assert str(raised.value) == "TimeoutError"

    FakeSmtp.failure = ConnectionResetError("reset by peer")
    with pytest.raises(outbox.ServerUnavailable) as raised:
        _send(smtp)
    assert str(raised.value) == "reset by peer"


def test_every_outcome_of_a_run_is_counted(caplog):
    _queue("uno", "dos", "tres", "cuatro", "cinco")
    transport = Transport(
        outbox.PermanentFailure("550 a"),
        outbox.PermanentFailure("550 b"),
        RuntimeError("421 c"),
        RuntimeError("421 d"),
        None,
    )

    report = outbox.deliver(transport, SENDER)

    assert (report.failed, report.retrying, report.sent) == (2, 2, 1)


def test_a_message_refused_after_a_retry_keeps_counting_its_attempts():
    _queue("uno")
    outbox.deliver(Transport(RuntimeError("421 busy")), SENDER)

    outbox.deliver(Transport(outbox.PermanentFailure("550 gone")), SENDER, due_only=False)

    [row] = _rows()
    assert (row.status, row.attempts, row.last_error) == (
        "failed",
        2,
        "PermanentFailure: 550 gone",
    )
