"""Handing the queued notices over to CiDi: `gobernar360 send-notices`.

Like the outbox: each notice is sent while its row is locked and marked in that same
transaction, so two workers never send the same one, and a failed attempt is retried with
growing delays. Its id goes along as the reference, for a CiDi that can recognise a repeat.
"""

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.db import platform_session, tenant_session
from gobernar360.core.secrets import SecretsUnavailable
from gobernar360.platform import cidi, resident_notices
from gobernar360.platform.access import system_context
from gobernar360.platform.cidi import connection
from gobernar360.platform.cidi.ports import (
    Communication,
    CommunicationsPort,
    RecipientUnknown,
    Unavailable,
)
from gobernar360.platform.models import Municipality, Person
from gobernar360.platform.outbox import MAX_ATTEMPTS, retry_delay
from gobernar360.platform.resident_notice_models import (
    CIDI,
    FAILED,
    HANDED_OVER,
    QUEUED,
    ResidentNotice,
)

logger = logging.getLogger(__name__)


@dataclass
class NoticeReport:
    handed_over: int = 0
    retrying: int = 0
    failed: int = 0
    # Of the failed ones, those that were emailed instead.
    emailed: int = 0
    # Municipalities whose connection cannot be decrypted.
    unreadable: int = 0

    @property
    def attempted(self) -> int:
        return self.handed_over + self.retrying + self.failed


def _next(db: Session, tried: set[uuid.UUID], due_by: datetime | None) -> ResidentNotice | None:
    query = select(ResidentNotice).where(
        ResidentNotice.channel == CIDI,
        ResidentNotice.state == QUEUED,
        # Each notice gets one attempt per run.
        ResidentNotice.id.not_in(tried),
    )
    if due_by is not None:
        query = query.where(ResidentNotice.next_attempt_at <= due_by)
    # Rows another worker is sending are skipped, not waited for.
    return db.scalar(
        query.order_by(ResidentNotice.created_at, ResidentNotice.id)
        .limit(1)
        .with_for_update(skip_locked=True)
    )


def _hand_over(port: CommunicationsPort, notice: ResidentNotice, person: Person) -> str:
    if person.cuil is None:
        raise RecipientUnknown("The person no longer has a CUIL.")
    receipt = port.send(
        Communication(
            recipient_cuil=person.cuil,
            subject=notice.title,
            body=notice.body,
            reference=str(notice.id),
        )
    )
    return receipt.external_id


def _retry(notice: ResidentNotice, error: Exception, now: datetime, report: NoticeReport) -> None:
    notice.attempts += 1
    # Only the kind of error nobody foresaw: its text might quote a credential.
    known = isinstance(error, Unavailable)
    notice.last_error = (f"Unavailable: {error}" if known else type(error).__name__)[:2000]
    if notice.attempts >= MAX_ATTEMPTS:
        notice.state = FAILED
        report.failed += 1
    else:
        notice.next_attempt_at = now + retry_delay(notice.attempts)
        report.retrying += 1
    logger.warning(
        "Notice %s not handed over (attempt %s): %s",
        notice.id,
        notice.attempts,
        notice.last_error,
    )


def _deliver_next(
    municipality_id: uuid.UUID,
    tried: set[uuid.UUID],
    due_only: bool,
    now: Callable[[], datetime],
    report: NoticeReport,
) -> bool:
    """Try one notice of the municipality. False when there is nothing else to try."""
    with tenant_session(municipality_id) as db:
        notice = _next(db, tried, now() if due_only else None)
        if notice is None:
            return False
        tried.add(notice.id)
        try:
            port = cidi.get_port(lambda: connection.load(db, municipality_id))
        except SecretsUnavailable as error:
            # Not the notices' fault: they wait until the installation's key is right.
            logger.error("The CiDi connection of %s cannot be read: %s", municipality_id, error)
            report.unreadable += 1
            return False
        person = db.get(Person, notice.person_id)
        try:
            external_id = _hand_over(port, notice, person)
        except RecipientUnknown as error:
            notice.attempts += 1
            notice.state = FAILED
            notice.last_error = f"RecipientUnknown: {error}"[:2000]
            report.failed += 1
            db.flush()
            report.emailed += resident_notices.fall_back(
                system_context(db, municipality_id), notice, person
            )
            logger.warning("Notice %s has no account to go to.", notice.id)
        except Exception as error:
            _retry(notice, error, now(), report)
            # The rest would find the same; they stay for the next run.
            return not isinstance(error, Unavailable)
        else:
            notice.attempts += 1
            notice.state = HANDED_OVER
            notice.handed_over_at = now()
            notice.external_id = external_id[:200]
            notice.last_error = None
            report.handed_over += 1
    return True


def deliver(
    *, due_only: bool = True, now: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> NoticeReport | None:
    """Hand over what is queued, one transaction per notice. None when CiDi is off.

    `due_only=False` also tries those waiting for their next retry, for when somebody runs
    the command by hand. Raises `CidiNotConfigured` before touching anything.
    """
    if not cidi.is_on():
        return None
    with platform_session() as db:
        # Nobody can work in a suspended municipality, so it tells nobody anything.
        municipalities = db.scalars(
            select(Municipality.id)
            .where(Municipality.suspended_at.is_(None))
            .order_by(Municipality.name)
        ).all()
    report = NoticeReport()
    for municipality_id in municipalities:
        tried: set[uuid.UUID] = set()
        while _deliver_next(municipality_id, tried, due_only, now, report):
            pass
    return report
