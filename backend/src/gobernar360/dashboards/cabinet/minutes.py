"""A closed meeting's minutes: what is copied when it closes, and the document to download.

The copy holds the name of everything linked, so the minutes stay what they were after a
project is renamed or deleted. Who may read those names is still decided for each reader,
when the document is built.
"""

import uuid
from datetime import date
from html import escape
from typing import Any

from sqlalchemy import select

from gobernar360.dashboards.cabinet import agenda
from gobernar360.dashboards.cabinet.models import Attendee, Carryover, Meeting, Taken
from gobernar360.dashboards.cabinet.present import item_title, taken, times_postponed
from gobernar360.platform import subjects
from gobernar360.platform.access import RequestContext
from gobernar360.platform.commitment_models import Commitment
from gobernar360.platform.commitment_rules import effective_state
from gobernar360.platform.models import Municipality, User
from gobernar360.platform.subjects import Subject, SubjectOut
from gobernar360.platform.texts import format_date, format_datetime, has_text, text


def attendees_of(ctx: RequestContext, meeting: Meeting) -> list[User]:
    return list(
        ctx.db.scalars(
            select(User)
            .join(Attendee, Attendee.user_id == User.id)
            .where(Attendee.meeting_id == meeting.id)
            .order_by(User.full_name, User.email)
        )
    )


def commitments_of(ctx: RequestContext, meeting: Meeting) -> list[Commitment]:
    """Commitments taken in the meeting, in the order they were."""
    item_ids = [item.id for item in agenda.items_of(ctx, meeting)]
    return list(
        ctx.db.scalars(
            taken()
            .where(Taken.item_id.in_(item_ids))
            .order_by(Commitment.created_at, Commitment.id)
        ).unique()
    )


def items_taken_in(
    ctx: RequestContext, commitments: list[Commitment]
) -> dict[uuid.UUID, uuid.UUID]:
    """The agenda item each commitment was taken on."""
    return dict(
        ctx.db.execute(
            select(Taken.commitment_id, Taken.item_id).where(
                Taken.commitment_id.in_([c.id for c in commitments])
            )
        ).all()
    )


def carried_over_to(ctx: RequestContext, meeting: Meeting) -> list[Commitment]:
    return list(
        ctx.db.scalars(
            select(Commitment)
            .join(Carryover, Carryover.commitment_id == Commitment.id)
            .where(Carryover.meeting_id == meeting.id)
            .order_by(Commitment.due_date, Commitment.created_at, Commitment.id)
        ).unique()
    )


def snapshot(ctx: RequestContext, meeting: Meeting, today: date) -> dict[str, Any]:
    """Everything the minutes say, as plain data. Names what is linked whoever closes it."""
    items = agenda.items_of(ctx, meeting)
    agreed = commitments_of(ctx, meeting)
    item_of = items_taken_in(ctx, agreed)
    carried = carried_over_to(ctx, meeting)
    topics = {
        c.id: c
        for c in ctx.db.scalars(
            select(Commitment).where(
                Commitment.id.in_([i.commitment_id for i in items if i.commitment_id])
            )
        ).unique()
    }
    described = subjects.describe(ctx, [row.subject for row in (*items, *agreed, *carried)])
    postponed = times_postponed(ctx, [c.id for c in carried])

    def subject(value: Subject | None) -> dict[str, Any] | None:
        return described[value].model_dump() if value else None

    def commitment(row: Commitment) -> dict[str, Any]:
        return {
            "description": row.description,
            "owner": row.owner.full_name,
            "due_date": row.due_date.isoformat(),
            "subject": subject(row.subject),
        }

    return {
        "municipality": ctx.db.get(Municipality, ctx.municipality_id).name,
        "closed_by": ctx.user.full_name,
        "attendees": [user.full_name for user in attendees_of(ctx, meeting)],
        "items": [
            {
                "source": item.source,
                # Empty for lights: their name is the subject's, which not everyone may read.
                "title": ""
                if item.source == "light"
                else item_title(
                    item, None, topics[item.commitment_id].description if item.commitment_id else ""
                ),
                "notes": item.notes,
                "discussed": item.discussed,
                "subject": subject(item.subject),
                "commitments": [commitment(c) for c in agreed if item_of[c.id] == item.id],
            }
            for item in items
        ],
        "carried_over": [
            commitment(row)
            | {
                "state": effective_state(row.state, row.due_date, today),
                "times_postponed": postponed[row.id],
            }
            for row in carried
        ],
    }


_STYLE = """
body { font-family: Georgia, serif; color: #111; max-width: 46rem; margin: 2rem auto;
       padding: 0 1rem; line-height: 1.45; }
h1 { font-size: 1.5rem; margin-bottom: 0; }
h2 { font-size: 1.15rem; border-bottom: 1px solid #999; margin-top: 2rem; }
h3 { font-size: 1rem; margin-bottom: .25rem; }
p { margin: .35rem 0; white-space: pre-wrap; }
ul { margin: .35rem 0; }
li { margin-bottom: .35rem; }
.muted { color: #555; }
@media print { body { margin: 0; } h3, li { break-inside: avoid; } }
"""


def _subject_line(ctx: RequestContext, data: dict[str, Any] | None) -> str | None:
    """The subject as this reader may see it, in words."""
    if data is None:
        return None
    seen = subjects.redact(ctx, SubjectOut.model_validate(data))
    if seen.access == "visible":
        if seen.color:
            return text(
                "subjects.withState", label=seen.label, state=text(f"subjects.states.{seen.color}")
            )
        return seen.label
    key = f"subjects.{seen.access}.{seen.dashboard_key}.{seen.kind}"
    if seen.dashboard_key is None or not has_text(key):
        key = f"subjects.{seen.access}.{'month' if seen.dashboard_key is None else 'record'}"
    return text(key)


def subject_line(ctx: RequestContext, seen: SubjectOut | None) -> str | None:
    return _subject_line(ctx, seen.model_dump() if seen else None)


def _paragraph(value: str, css: str = "") -> str:
    attribute = f' class="{css}"' if css else ""
    return f"<p{attribute}>{escape(value)}</p>" if value else ""


def _commitment_html(ctx: RequestContext, data: dict[str, Any], extra: str = "") -> str:
    line = text(
        "cabinet.minutes.commitment",
        owner=data["owner"],
        due_date=format_date(date.fromisoformat(data["due_date"])),
    )
    about = _subject_line(ctx, data["subject"])
    parts = [
        escape(data["description"]),
        f'<br><span class="muted">{escape(line)}{escape(extra)}</span>',
    ]
    if about:
        label = text("cabinet.minutes.about", subject=about)
        parts.append(f'<br><span class="muted">{escape(label)}</span>')
    return f"<li>{''.join(parts)}</li>"


def _item_html(ctx: RequestContext, number: int, item: dict[str, Any]) -> str:
    about = _subject_line(ctx, item["subject"])
    title = item["title"] or about
    parts = [f"<h3>{number}. {escape(title)}</h3>"]
    if item["title"] and about:
        parts.append(_paragraph(text("cabinet.minutes.about", subject=about), "muted"))
    if not item["discussed"]:
        parts.append(_paragraph(text("cabinet.minutes.notDiscussed"), "muted"))
    parts.append(_paragraph(item["notes"]))
    if item["commitments"]:
        rows = "".join(_commitment_html(ctx, row) for row in item["commitments"])
        parts.append(f"<p><strong>{text('cabinet.minutes.agreed')}</strong></p><ul>{rows}</ul>")
    return "".join(parts)


def _carried_html(ctx: RequestContext, row: dict[str, Any]) -> str:
    times = row["times_postponed"]
    extra = text(
        "cabinet.minutes.carriedOnce" if times == 1 else "cabinet.minutes.carriedTimes",
        state=text(f"cabinet.states.{row['state']}"),
        times=times,
    )
    return _commitment_html(ctx, row, f" · {extra}")


def document(ctx: RequestContext, meeting: Meeting) -> str:
    """The minutes as one self-contained HTML page, ready to print."""
    data = meeting.minutes
    title = text("cabinet.minutes.title", date=format_date(meeting.date))
    none = text("cabinet.minutes.none")
    section = [
        f"<h1>{escape(title)}</h1>",
        _paragraph(data["municipality"], "muted"),
        f"<h2>{text('cabinet.minutes.attendees')}</h2>",
        _paragraph(", ".join(data["attendees"]) or none),
    ]
    if meeting.guests:
        section.append(_paragraph(text("cabinet.minutes.guests", names=meeting.guests)))
    section.append(f"<h2>{text('cabinet.minutes.agenda')}</h2>")
    section.extend(_item_html(ctx, n, item) for n, item in enumerate(data["items"], start=1))
    if not data["items"]:
        section.append(_paragraph(none))
    if data["carried_over"]:
        rows = "".join(_carried_html(ctx, row) for row in data["carried_over"])
        section.append(f"<h2>{text('cabinet.minutes.carried')}</h2><ul>{rows}</ul>")
    if meeting.notes:
        section.append(f"<h2>{text('cabinet.minutes.notes')}</h2>{_paragraph(meeting.notes)}")
    closed = text(
        "cabinet.minutes.closed", name=data["closed_by"], when=format_datetime(meeting.closed_at)
    )
    section.append(f"<hr>{_paragraph(closed, 'muted')}")
    return (
        f'<!doctype html><html lang="es-AR"><head><meta charset="utf-8">'
        f"<title>{escape(title)}</title><style>{_STYLE}</style></head>"
        f"<body>{''.join(section)}</body></html>"
    )
