"""The email outbox: nothing is lost when SMTP fails, nothing is sent twice."""

import threading
import time
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from typer.testing import CliRunner

from gobernar360.cli import app as cli
from gobernar360.core.config import get_settings
from gobernar360.core.db import platform_session
from gobernar360.platform import outbox
from gobernar360.platform.models import EmailOutbox
from tests.factories import (
    admin_session,
    emails_to,
    login,
    make_membership,
    make_municipality,
    make_user,
)
from tests.fake_smtp import FakeSmtpServer, unused_port

SENDER = "gobernar360 <no-reply@gobernar360.test>"


class FakeTransport:
    """Records what it sends; fails while `failure` is set."""

    def __init__(self, failure: Exception | None = None, delay: float = 0) -> None:
        self.failure = failure
        self.delay = delay
        self.sent = []
        self.lock = threading.Lock()

    def send(self, message) -> None:
        time.sleep(self.delay)
        if self.failure is not None:
            raise self.failure
        with self.lock:
            self.sent.append(message)


def _queue(to: str = "ana@noetinger.test", subject: str = "Hola", body: str = "Texto") -> None:
    with platform_session() as db:
        outbox.enqueue(db, to, subject, body)


def _rows() -> list[EmailOutbox]:
    with admin_session() as session:
        return list(session.scalars(select(EmailOutbox).order_by(EmailOutbox.created_at)))


def _later(seconds: float):
    return lambda: datetime.now(UTC) + timedelta(seconds=seconds)


@pytest.fixture
def smtp_port(monkeypatch):
    """Point the settings at a port; returns a setter so a test can move it."""

    def point_at(port: int) -> None:
        monkeypatch.setattr(get_settings(), "smtp_port", port)
        monkeypatch.setattr(get_settings(), "smtp_host", "127.0.0.1")

    return point_at


def test_an_email_is_only_queued_if_its_change_commits():
    with pytest.raises(RuntimeError), platform_session() as db:
        outbox.enqueue(db, "ana@noetinger.test", "Hola", "Texto")
        raise RuntimeError("the change failed")

    assert _rows() == []


def test_an_email_survives_an_smtp_failure_and_is_delivered_on_retry():
    _queue()
    down = FakeTransport(failure=outbox.ServerUnavailable("Connection refused"))

    failed = outbox.deliver(down, SENDER)

    assert (failed.sent, failed.retrying) == (0, 1)
    [row] = _rows()
    assert (row.status, row.attempts) == ("pending", 1)
    assert "Connection refused" in row.last_error
    assert row.next_attempt_at > datetime.now(UTC) + timedelta(seconds=20)

    up = FakeTransport()
    too_early = outbox.deliver(up, SENDER)
    retried = outbox.deliver(up, SENDER, now=_later(31))
    afterwards = outbox.deliver(up, SENDER, now=_later(3600))

    assert (too_early.attempted, retried.sent, afterwards.attempted) == (0, 1, 0)
    assert len(up.sent) == 1
    [row] = _rows()
    assert (row.status, row.last_error) == ("sent", None)
    assert row.sent_at is not None


def test_retries_wait_longer_each_time_up_to_an_hour():
    delays = [outbox.retry_delay(attempt).total_seconds() for attempt in (1, 2, 3, 4, 8, 15)]

    assert delays == [30, 60, 120, 240, 3600, 3600]


def test_a_run_by_hand_does_not_wait_for_the_retry_delay():
    _queue()
    outbox.deliver(FakeTransport(failure=OSError("down")), SENDER)

    report = outbox.deliver(FakeTransport(), SENDER, due_only=False)

    assert report.sent == 1


def test_each_email_gets_one_attempt_per_run():
    _queue()
    transport = FakeTransport(failure=RuntimeError("temporary"))

    report = outbox.deliver(transport, SENDER, due_only=False)

    assert (report.retrying, _rows()[0].attempts) == (1, 1)


def test_an_unreachable_server_stops_the_run_and_keeps_the_rest_pending():
    for index in range(3):
        _queue(subject=f"Mensaje {index}")

    report = outbox.deliver(FakeTransport(failure=outbox.ServerUnavailable("down")), SENDER)

    assert report.attempted == 1
    assert [row.attempts for row in _rows()] == [1, 0, 0]
    assert {row.status for row in _rows()} == {"pending"}


def test_an_email_refused_for_good_is_marked_failed_and_can_be_queued_again():
    _queue()

    report = outbox.deliver(
        FakeTransport(failure=outbox.PermanentFailure("550 no such user")), SENDER
    )

    assert report.failed == 1
    assert _rows()[0].status == "failed"
    assert outbox.deliver(FakeTransport(), SENDER, due_only=False).attempted == 0
    assert outbox.requeue_failed() == 1
    assert outbox.deliver(FakeTransport(), SENDER).sent == 1


def test_an_email_is_given_up_after_too_many_attempts():
    _queue()
    with admin_session() as session, session.begin():
        session.scalars(select(EmailOutbox)).one().attempts = outbox.MAX_ATTEMPTS - 1

    outbox.deliver(FakeTransport(failure=RuntimeError("still failing")), SENDER)

    assert _rows()[0].status == "failed"


def test_two_workers_never_send_the_same_email():
    for index in range(6):
        _queue(subject=f"Mensaje {index}")
    transport = FakeTransport(delay=0.05)
    workers = [threading.Thread(target=outbox.deliver, args=(transport, SENDER)) for _ in range(3)]

    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()

    subjects = sorted(message["Subject"] for message in transport.sent)
    assert subjects == [f"Mensaje {index}" for index in range(6)]


def test_the_message_has_a_stable_id_and_plain_utf8_text():
    _queue(subject="Año de gestión\nsegunda línea", body="Señora Pérez: hola.")
    first = FakeTransport(failure=RuntimeError("temporary"))
    outbox.deliver(first, SENDER)
    transport = FakeTransport()
    outbox.deliver(transport, SENDER, due_only=False)

    [message] = transport.sent
    row = _rows()[0]
    assert message["Message-ID"] == f"<{row.id}@gobernar360.test>"
    assert message["From"] == SENDER
    assert message["To"] == "ana@noetinger.test"
    # Names people type cannot break the header into two lines.
    assert message["Subject"] == "Año de gestión segunda línea"
    assert message.get_content_type() == "text/plain"
    assert message.get_content() == "Señora Pérez: hola.\n"


def test_smtp_transport_delivers_to_a_real_server(smtp_port):
    _queue()
    with FakeSmtpServer() as server:
        smtp_port(server.port)

        report = outbox.deliver(outbox.SmtpTransport(get_settings()), SENDER)

    assert report.sent == 1
    assert [message["To"] for message in server.received] == ["ana@noetinger.test"]


def test_smtp_transport_tells_an_unreachable_server_from_a_refused_recipient(smtp_port):
    smtp_port(unused_port())
    with pytest.raises(outbox.ServerUnavailable):
        outbox.SmtpTransport(get_settings()).send(outbox.build_message(_sample(), SENDER))

    with FakeSmtpServer() as server:
        smtp_port(server.port)
        server.rcpt_reply = "550 No such user"
        with pytest.raises(outbox.PermanentFailure):
            outbox.SmtpTransport(get_settings()).send(outbox.build_message(_sample(), SENDER))


def _sample() -> EmailOutbox:
    return EmailOutbox(
        id=None,
        to_address="ana@noetinger.test",
        subject="Hola",
        body="Texto",
        created_at=datetime.now(UTC),
    )


def test_send_email_command_keeps_the_email_while_smtp_is_down_and_sends_it_once_later(
    client, smtp_port
):
    # Stop the mail catcher, add a user, start it again and run send-email.
    noetinger = make_municipality("Noetinger")
    make_membership(make_user("admin@noetinger.test"), noetinger, admin=True)
    login(client, "admin@noetinger.test")
    client.post("/api/admin/users", json={"email": "carla@noetinger.test", "full_name": "Carla"})
    runner = CliRunner()

    smtp_port(unused_port())
    down = runner.invoke(cli, ["send-email"])
    with FakeSmtpServer() as server:
        smtp_port(server.port)
        up = runner.invoke(cli, ["send-email"])
        again = runner.invoke(cli, ["send-email"])

    assert down.exit_code == 1, down.output
    assert "Will be retried: 1" in down.output
    assert up.exit_code == 0, up.output
    assert "Sent: 1." in up.output
    assert "Sent: 0." in again.output
    assert [message["To"] for message in server.received] == ["carla@noetinger.test"]
    assert server.received[0]["From"] == get_settings().email_from
    assert [row.status for row in emails_to("carla@noetinger.test")] == ["sent"]


def test_an_html_email_also_carries_its_plain_text_version():
    with platform_session() as db:
        outbox.enqueue(db, "ana@noetinger.test", "Hola", "Hola, Ana.", "<p>Hola, <b>Ana</b>.</p>")
    transport = FakeTransport()

    outbox.deliver(transport, SENDER)

    [message] = transport.sent
    assert message.get_content_type() == "multipart/alternative"
    plain = message.get_body(preferencelist=("plain",))
    rich = message.get_body(preferencelist=("html",))
    assert plain.get_content() == "Hola, Ana.\n"
    assert rich.get_content() == "<p>Hola, <b>Ana</b>.</p>\n"
