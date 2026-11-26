"""Telling a resident that something happened to what they asked for.

A dashboard asks for it with `queue`, in the transaction of the change it tells about, and
declares the kinds it uses in `DashboardModule.notice_kinds`. Nothing is sent from a
request: emails go to the outbox, and `gobernar360 send-notices` (`notice_delivery`) hands
the rest over to CiDi.

What a notice says is built from the municipality's template and the few fields it is
given. The only free text that reaches the resident is the message written for them.
"""

import html
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gobernar360.platform import cidi, email_templates, municipality_settings
from gobernar360.platform.access import RequestContext
from gobernar360.platform.audit import record_change
from gobernar360.platform.email_templates import Html, Rendered, Template
from gobernar360.platform.models import (
    CIDI_ONLY,
    CIDI_THEN_EMAIL,
    EMAIL_ONLY,
    Municipality,
    Person,
)
from gobernar360.platform.resident_notice_models import (
    CIDI,
    EMAIL,
    HANDED_OVER,
    NO_CHANNEL,
    QUEUED,
    ResidentNotice,
)
from gobernar360.platform.schemas import valid_email
from gobernar360.platform.subjects import Subject
from gobernar360.platform.tenant_crud import resolve

MAX_MESSAGE = 500
MESSAGE = "message"


def policy(db: Session, municipality_id: uuid.UUID) -> str:
    """The channels the municipality chose."""
    row = municipality_settings.find(db, municipality_id)
    return row.resident_notice_channel if row else EMAIL_ONLY


def email_of(person: Person) -> str | None:
    """Where the person can be written to. What was typed may be anything."""
    try:
        return valid_email(person.email)
    except ValueError:
        return None


def _channel(chosen: str, person: Person) -> tuple[str, str]:
    """Channel and first state of a notice to the person."""
    if chosen in (CIDI_THEN_EMAIL, CIDI_ONLY) and person.cuil and cidi.is_available():
        return CIDI, QUEUED
    if chosen in (CIDI_THEN_EMAIL, EMAIL_ONLY) and email_of(person):
        return EMAIL, HANDED_OVER
    return (CIDI if chosen == CIDI_ONLY else EMAIL), NO_CHANNEL


def _render(ctx: RequestContext, kind: str, message: str, params: dict[str, object]) -> Rendered:
    template = email_templates.load(ctx.db, ctx.municipality_id, email_templates.notice_key(kind))
    if message and MESSAGE not in email_templates.placeholders(template.html):
        # A text without a place for it must not lose what was written for the resident.
        body = f"{template.html}<p>{{{{{MESSAGE}}}}}</p>"
        template = Template(template.key, template.subject, body, template.customized)
    shown = Html(html.escape(message).replace("\n", "<br>"))
    return email_templates.render(template, params | {MESSAGE: shown})


def _lock_event(db: Session, event_key: str) -> None:
    """Makes two that tell the same event wait for each other, until the transaction ends."""
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 0))"),
        {"key": f"resident-notice:{event_key}"},
    )


def _insert(ctx: RequestContext, **fields: object) -> ResidentNotice | None:
    """Add a notice, unless the person already has it by that channel."""
    author = ctx.user.id if ctx.user else None
    notice_id = ctx.db.scalar(
        insert(ResidentNotice)
        .values(municipality_id=ctx.municipality_id, created_by=author, updated_by=author, **fields)
        .on_conflict_do_nothing(index_elements=["event_key", "person_id", "channel"])
        .returning(ResidentNotice.id)
    )
    if notice_id is None:
        return None
    notice = ctx.db.get(ResidentNotice, notice_id)
    # What it says stays in the notice: the audit trail only tells that there was one.
    record_change(
        ctx,
        "create",
        notice,
        {"kind": notice.kind, "channel": notice.channel, "state": notice.state},
    )
    return notice


def queue(
    ctx: RequestContext,
    person: Person,
    kind: str,
    event_key: str,
    subject: Subject,
    message: str | None = None,
    **params: object,
) -> ResidentNotice | None:
    """Tell a person of the registry about one event, once, by the best channel they have.

    `params` fill the template of the kind, besides `name` and `municipality`. Returns the
    notice, or None when the event had already been told.
    """
    person = resolve(ctx, Person, person.id, "person_id")
    _lock_event(ctx.db, event_key)
    told = select(ResidentNotice.id).where(
        ResidentNotice.event_key == event_key, ResidentNotice.person_id == person.id
    )
    if ctx.db.scalar(told.limit(1)) is not None:
        return None
    rendered = _render(
        ctx,
        kind,
        message or "",
        {
            "name": f"{person.first_name} {person.last_name}",
            "municipality": ctx.db.get(Municipality, ctx.municipality_id).name,
        }
        | params,
    )
    channel, state = _channel(policy(ctx.db, ctx.municipality_id), person)
    notice = _insert(
        ctx,
        person_id=person.id,
        kind=kind,
        subject_dashboard=subject.dashboard_key,
        subject_kind=subject.kind,
        subject_ref=subject.ref,
        event_key=event_key,
        channel=channel,
        state=state,
        title=email_templates.one_line(rendered.subject),
        body=rendered.text,
        handed_over_at=datetime.now(UTC) if state == HANDED_OVER else None,
    )
    if notice is not None and state == HANDED_OVER:
        email_templates.send_rendered(ctx.db, email_of(person), rendered)
    return notice


def fall_back(ctx: RequestContext, notice: ResidentNotice, person: Person) -> bool:
    """Email what could not be handed over to CiDi, word for word, if the municipality wants
    that and the person has an address. A second notice: the first keeps what happened."""
    address = email_of(person)
    if policy(ctx.db, ctx.municipality_id) != CIDI_THEN_EMAIL or address is None:
        return False
    second = _insert(
        ctx,
        person_id=notice.person_id,
        kind=notice.kind,
        subject_dashboard=notice.subject_dashboard,
        subject_kind=notice.subject_kind,
        subject_ref=notice.subject_ref,
        event_key=notice.event_key,
        channel=EMAIL,
        state=HANDED_OVER,
        title=notice.title,
        body=notice.body,
        handed_over_at=datetime.now(UTC),
    )
    if second is None:
        return False
    email_templates.send_rendered(ctx.db, address, email_templates.plain(notice.title, notice.body))
    return True


def about(db: Session, subject: Subject) -> list[ResidentNotice]:
    """The notices about something, the oldest first."""
    return list(
        db.scalars(
            select(ResidentNotice)
            .where(
                ResidentNotice.subject_dashboard == subject.dashboard_key,
                ResidentNotice.subject_kind == subject.kind,
                ResidentNotice.subject_ref == subject.ref,
            )
            .order_by(ResidentNotice.created_at, ResidentNotice.channel, ResidentNotice.id)
        )
    )
