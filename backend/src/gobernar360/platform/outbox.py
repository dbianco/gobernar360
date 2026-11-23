"""Outgoing email through an outbox table.

An email is written to `email_outbox` in the same transaction as the change that caused
it: if the change rolls back nothing is sent, and once it commits the email cannot be
lost. `deliver` (the `gobernar360 send-email` command) sends what is pending. Each row is
sent while its row lock is held and marked sent in that same transaction, so two workers
never send the same message; a failed attempt stays pending and is retried later, with
a delay that doubles each time.

One gap no outbox can close: if the process dies after the SMTP server accepted a message
but before the row is marked sent, the message is sent again. Its Message-ID header is the
same on every attempt, which lets mail systems recognise the duplicate.
"""

import logging
import smtplib
import ssl
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime, parseaddr
from typing import Protocol

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from gobernar360.core.config import Settings
from gobernar360.core.db import platform_session
from gobernar360.platform.models import EmailOutbox

logger = logging.getLogger(__name__)

FIRST_RETRY_DELAY = timedelta(seconds=30)
MAX_RETRY_DELAY = timedelta(hours=1)
# After this many failed attempts a message is marked failed; `send-email --retry-failed`
# puts it back in the queue.
MAX_ATTEMPTS = 20


class ServerUnavailable(Exception):
    """The SMTP server could not be reached: no point trying the next message now."""


class PermanentFailure(Exception):
    """The SMTP server refused the message for good, e.g. a recipient that does not exist."""


class Transport(Protocol):
    def send(self, message: EmailMessage) -> None: ...


def enqueue(
    db: Session, to: str, subject: str, body: str, body_html: str | None = None
) -> EmailOutbox:
    """Queue an email in the caller's transaction: plain text, and HTML if given."""
    row = EmailOutbox(
        to_address=to,
        # Header values cannot span lines, and subjects may include names people typed.
        subject=" ".join(subject.split())[:300],
        body=body,
        body_html=body_html,
    )
    db.add(row)
    return row


def retry_delay(attempts: int) -> timedelta:
    return min(FIRST_RETRY_DELAY * 2 ** (attempts - 1), MAX_RETRY_DELAY)


def build_message(row: EmailOutbox, sender: str) -> EmailMessage:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = row.to_address
    message["Subject"] = row.subject
    message["Date"] = format_datetime(row.created_at)
    domain = parseaddr(sender)[1].rpartition("@")[2] or "gobernar360"
    message["Message-ID"] = f"<{row.id}@{domain}>"
    message.set_content(row.body)
    if row.body_html:
        message.add_alternative(row.body_html, subtype="html")
    return message


@dataclass
class DeliveryReport:
    sent: int = 0
    retrying: int = 0
    failed: int = 0

    @property
    def attempted(self) -> int:
        return self.sent + self.retrying + self.failed


def _describe(error: Exception) -> str:
    return f"{type(error).__name__}: {error}"[:2000]


def deliver(
    transport: Transport,
    sender: str,
    *,
    due_only: bool = True,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> DeliveryReport:
    """Send pending messages, one transaction per message, until none is left.

    `due_only=False` also sends messages still waiting for their next retry, for when
    someone runs the command by hand after fixing the mail server.
    """
    report = DeliveryReport()
    tried: set = set()
    while True:
        with platform_session() as db:
            query = select(EmailOutbox).where(EmailOutbox.status == "pending")
            if due_only:
                query = query.where(EmailOutbox.next_attempt_at <= now())
            if tried:
                # Each message gets one attempt per run.
                query = query.where(EmailOutbox.id.not_in(tried))
            # Rows another worker is sending are skipped, not waited for.
            row = db.scalar(
                query.order_by(EmailOutbox.created_at).limit(1).with_for_update(skip_locked=True)
            )
            if row is None:
                return report
            tried.add(row.id)
            unavailable = False
            try:
                transport.send(build_message(row, sender))
            except PermanentFailure as error:
                row.attempts += 1
                row.status = "failed"
                row.last_error = _describe(error)
                report.failed += 1
                logger.warning("Email %s to %s refused: %s", row.id, row.to_address, error)
            except Exception as error:
                row.attempts += 1
                row.last_error = _describe(error)
                if row.attempts >= MAX_ATTEMPTS:
                    row.status = "failed"
                    report.failed += 1
                else:
                    row.next_attempt_at = now() + retry_delay(row.attempts)
                    report.retrying += 1
                unavailable = isinstance(error, ServerUnavailable)
                logger.warning("Email %s not sent (attempt %s): %s", row.id, row.attempts, error)
            else:
                row.status = "sent"
                row.sent_at = now()
                row.last_error = None
                report.sent += 1
        if unavailable:
            # The rest would fail the same way; they stay pending for the next run.
            return report


def requeue_failed() -> int:
    """Give messages marked failed a new round of attempts."""
    with platform_session() as db:
        result = db.execute(
            update(EmailOutbox)
            .where(EmailOutbox.status == "failed")
            .values(status="pending", attempts=0, next_attempt_at=datetime.now(UTC))
        )
        return result.rowcount


def pending_count() -> int:
    with platform_session() as db:
        return db.scalar(
            select(func.count()).select_from(EmailOutbox).where(EmailOutbox.status == "pending")
        )


class SmtpTransport:
    """Sends through the SMTP server in the settings, one connection per message."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def _connect(self) -> smtplib.SMTP:
        s = self.settings
        if s.smtp_security == "tls":
            return smtplib.SMTP_SSL(
                s.smtp_host,
                s.smtp_port,
                timeout=s.smtp_timeout_seconds,
                context=ssl.create_default_context(),
            )
        smtp = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=s.smtp_timeout_seconds)
        if s.smtp_security == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        return smtp

    def send(self, message: EmailMessage) -> None:
        try:
            with self._connect() as smtp:
                if self.settings.smtp_username:
                    smtp.login(self.settings.smtp_username, self.settings.smtp_password)
                smtp.send_message(message)
        except smtplib.SMTPRecipientsRefused as error:
            codes = [code for code, _ in error.recipients.values()]
            if codes and all(code >= 500 for code in codes):
                raise PermanentFailure(str(error.recipients)) from error
            raise
        except smtplib.SMTPConnectError as error:
            raise ServerUnavailable(str(error)) from error
        except smtplib.SMTPResponseException:
            # The server answered with an error; worth trying again later.
            raise
        except OSError as error:
            # Refused connection, timeout, lost connection: the server is not there.
            raise ServerUnavailable(str(error) or type(error).__name__) from error
