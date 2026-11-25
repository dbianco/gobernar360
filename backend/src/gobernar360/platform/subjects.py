"""Linkable subjects: what a module may point at in another one, without importing it.

A subject is a month of a dashboard (its status light) or a record of a kind the dashboard
declares in the registry (`DashboardModule.linkable`). It is identified by the dashboard's
key, the kind and a reference: `2026-10` for a month, the record's id otherwise.

Every rule about links lives here:

- On write, `resolve` accepts only subjects that exist in the municipality and that the
  member may see. There is no foreign key behind a link, and one would not be subject to
  row-level security anyway.
- On read, `present` shows a subject only to those who may see it. Anyone else learns that
  something of that kind is linked, and nothing about it: not its name, not its reference,
  not even whether it still exists.
"""

import re
import uuid
from collections.abc import Collection, Iterable
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import CheckConstraint, String, select, tuple_
from sqlalchemy.orm import Mapped, mapped_column

from gobernar360.core.errors import forbidden, invalid_reference
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import (
    MONTH,
    LinkableRecord,
    SubjectCommitment,
    SubjectRecord,
    SubjectsQuery,
)
from gobernar360.platform import status
from gobernar360.platform.access import AccessLevel, RequestContext, effective_levels
from gobernar360.platform.models import DashboardStatus
from gobernar360.platform.texts import dashboard_name, has_text, month_name, text

MONTH_REF = re.compile(r"((?:19|2[01])[0-9]{2})-(0[1-9]|1[0-2])")
# How far back the months offered to link go.
MONTHS_OFFERED = 24


@dataclass(frozen=True)
class Subject:
    dashboard_key: str
    kind: str
    ref: str


_Key = Annotated[str, StringConstraints(min_length=1, max_length=50)]


class SubjectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dashboard_key: _Key
    kind: _Key
    ref: _Key


class SubjectOut(BaseModel):
    """A subject as one reader sees it."""

    # `restricted`: the reader may not know what it is. `deleted`: it no longer exists.
    access: Literal["visible", "restricted", "deleted"]
    kind: str
    # Null when restricted, except for records, whose kind already tells their dashboard.
    dashboard_key: str | None
    ref: str | None = None
    label: str | None = None
    path: str | None = None
    # The light of a month, when it has one.
    color: str | None = None


class SubjectMixin:
    """Columns of a table whose rows may point at a subject. Add `subject_check()`."""

    subject_dashboard: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject_kind: Mapped[str | None] = mapped_column(String(50), nullable=True)
    subject_ref: Mapped[str | None] = mapped_column(String(50), nullable=True)

    @property
    def subject(self) -> Subject | None:
        if self.subject_dashboard is None:
            return None
        return Subject(self.subject_dashboard, self.subject_kind, self.subject_ref)

    @subject.setter
    def subject(self, value: Subject | None) -> None:
        self.subject_dashboard = value.dashboard_key if value else None
        self.subject_kind = value.kind if value else None
        self.subject_ref = value.ref if value else None


# Runs once, while the models are imported, where mutation testing cannot reach it;
# tests/cabinet/test_subject_links.py checks the constraint.
def subject_check() -> CheckConstraint:  # pragma: no mutate block
    return CheckConstraint(
        "num_nulls(subject_dashboard, subject_kind, subject_ref) IN (0, 3)",
        name="subject_complete",
    )


def month_ref(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


def _parse_month(ref: str) -> tuple[int, int] | None:
    match = MONTH_REF.fullmatch(ref)
    return (int(match[1]), int(match[2])) if match else None


def _parse_id(ref: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(ref)
    except ValueError:
        return None


def _dashboard_label(key: str) -> str:
    return dashboard_name(key) if has_text(f"dashboards.{key}") else key


def _linkable(dashboard_key: str, kind: str) -> LinkableRecord | None:
    module = registry.get_module(dashboard_key)
    if module is None:
        return None
    return next((record for record in module.linkable if record.kind == kind), None)


def _sees(levels: dict[str, AccessLevel], dashboard_key: str, kind: str) -> bool:
    """Whether a member with these levels may know what subjects of this kind are."""
    level = levels.get(dashboard_key, AccessLevel.NONE)
    if kind == MONTH:
        return level >= AccessLevel.VIEWER
    record = _linkable(dashboard_key, kind)
    if record is None:
        return False
    # Never below viewer, whatever the dashboard declares.
    return level >= max(AccessLevel.VIEWER, AccessLevel[record.min_level.upper()])


def _levels(ctx: RequestContext) -> dict[str, AccessLevel]:
    return effective_levels(ctx.db, ctx.membership)


def visible_kinds(ctx: RequestContext) -> list[tuple[str, str]]:
    """Every (dashboard, kind) the member may link to; a dashboard's month comes first."""
    levels = _levels(ctx)
    return [
        (module.key, kind)
        for module in registry.all_modules()
        for kind in (MONTH, *(record.kind for record in module.linkable))
        if _sees(levels, module.key, kind)
    ]


def require_visible(ctx: RequestContext, dashboard_key: str, kind: str) -> None:
    # Unknown dashboards and kinds are refused the same way as forbidden ones.
    if not _sees(_levels(ctx), dashboard_key, kind):
        raise forbidden()


def _months_out(
    ctx: RequestContext, dashboard_key: str, refs: Iterable[str]
) -> dict[str, SubjectOut]:
    parsed = {ref: month for ref in refs if (month := _parse_month(ref)) is not None}
    lights = {
        (row.year, row.month): row.color
        for row in ctx.db.scalars(
            select(DashboardStatus).where(
                DashboardStatus.dashboard_key == dashboard_key,
                tuple_(DashboardStatus.year, DashboardStatus.month).in_(list(parsed.values())),
            )
        )
    }
    return {
        ref: SubjectOut(
            access="visible",
            kind=MONTH,
            dashboard_key=dashboard_key,
            ref=ref,
            label=text(
                "subjects.month",
                dashboard=_dashboard_label(dashboard_key),
                month=month_name(month),
                year=year,
            ),
            path=f"/d/{dashboard_key}",
            color=lights.get((year, month)),
        )
        for ref, (year, month) in parsed.items()
    }


def _record_out(dashboard_key: str, kind: str, record: SubjectRecord) -> SubjectOut:
    return SubjectOut(
        access="visible",
        kind=kind,
        dashboard_key=dashboard_key,
        ref=str(record.id),
        label=record.label,
        path=record.path,
    )


def _records_out(
    ctx: RequestContext, dashboard_key: str, kind: str, refs: Iterable[str]
) -> dict[str, SubjectOut]:
    record_kind = _linkable(dashboard_key, kind)
    ids = {record_id for ref in refs if (record_id := _parse_id(ref)) is not None}
    if record_kind is None or not ids:
        return {}
    return {
        str(record.id): _record_out(dashboard_key, kind, record)
        for record in record_kind.describe(ctx, ids)
    }


def describe(ctx: RequestContext, subjects: Iterable[Subject | None]) -> dict[Subject, SubjectOut]:
    """What each subject is, whoever is asking. Only for `redact`ing before it is shown."""
    wanted = {subject for subject in subjects if subject is not None}
    found: dict[Subject, SubjectOut] = {}
    by_kind: dict[tuple[str, str], list[Subject]] = {}
    for subject in wanted:
        by_kind.setdefault((subject.dashboard_key, subject.kind), []).append(subject)
    for (dashboard_key, kind), group in by_kind.items():
        refs = [subject.ref for subject in group]
        if kind == MONTH:
            described = _months_out(ctx, dashboard_key, refs)
        else:
            described = _records_out(ctx, dashboard_key, kind, refs)
        for subject in group:
            found[subject] = described.get(subject.ref) or SubjectOut(
                access="deleted",
                kind=kind,
                dashboard_key=dashboard_key,
                ref=subject.ref,
            )
    return found


def _redacted(levels: dict[str, AccessLevel], out: SubjectOut) -> SubjectOut:
    if out.dashboard_key is not None and _sees(levels, out.dashboard_key, out.kind):
        return out
    return SubjectOut(
        access="restricted",
        kind=out.kind,
        dashboard_key=None if out.kind == MONTH else out.dashboard_key,
    )


def redact(ctx: RequestContext, out: SubjectOut) -> SubjectOut:
    """The subject as this member may see it."""
    return _redacted(_levels(ctx), out)


def present(ctx: RequestContext, subjects: Iterable[Subject | None]) -> dict[Subject, SubjectOut]:
    """The subjects as this member may see them."""
    levels = _levels(ctx)
    return {subject: _redacted(levels, out) for subject, out in describe(ctx, subjects).items()}


def resolve(
    ctx: RequestContext, payload: SubjectIn, today: date, field: str = "subject"
) -> Subject:
    """The subject a request body points at, once checked.

    It must exist in the municipality and be visible to the member. Both failures get the
    same answer, so trying references reveals nothing.
    """
    error = invalid_reference(f"{field} does not reference an existing record.")
    if not _sees(_levels(ctx), payload.dashboard_key, payload.kind):
        raise error
    if payload.kind == MONTH:
        parsed = _parse_month(payload.ref)
        if parsed is None or status.is_future(*parsed, today):
            raise error
        return Subject(payload.dashboard_key, MONTH, payload.ref)
    records = _records_out(ctx, payload.dashboard_key, payload.kind, [payload.ref])
    if not records:
        raise error
    # The id as the record has it, whatever way the request wrote it.
    [ref] = records
    return Subject(payload.dashboard_key, payload.kind, ref)


def search(
    ctx: RequestContext, dashboard_key: str, kind: str, words: str, today: date, limit: int
) -> list[SubjectOut]:
    """Subjects of one kind to choose from. Months come newest first."""
    require_visible(ctx, dashboard_key, kind)
    if kind == MONTH:
        index = today.year * 12 + today.month - 1
        refs = [
            month_ref((index - ago) // 12, (index - ago) % 12 + 1) for ago in range(MONTHS_OFFERED)
        ]
        months = _months_out(ctx, dashboard_key, refs).values()
        wanted = words.lower().split()
        return [out for out in months if all(word in out.label.lower() for word in wanted)][:limit]
    records = _linkable(dashboard_key, kind).search(ctx, words, limit)
    return [_record_out(dashboard_key, kind, record) for record in records]


def commitments_about(
    ctx: RequestContext, dashboard_key: str, kind: str, refs: Collection[str], today: date
) -> list[SubjectCommitment]:
    """Open commitments about some subjects, soonest due first.

    The member must be able to see the subjects. They get the commitments kept by the
    dashboards they have access to: to anyone else there are none.
    """
    levels = _levels(ctx)
    if not _sees(levels, dashboard_key, kind):
        raise forbidden()
    if kind == MONTH:
        known = {ref for ref in refs if _parse_month(ref) is not None}
    else:
        known = {str(record_id) for ref in refs if (record_id := _parse_id(ref)) is not None}
    query = SubjectsQuery(dashboard_key, kind, frozenset(known))
    found = [
        commitment
        for module in registry.all_modules()
        if module.get_commitments is not None
        and levels.get(module.key, AccessLevel.NONE) >= AccessLevel.VIEWER
        for commitment in module.get_commitments(ctx, today, query)
    ]
    return sorted(found, key=lambda c: (c.due_date, c.description, str(c.id)))
