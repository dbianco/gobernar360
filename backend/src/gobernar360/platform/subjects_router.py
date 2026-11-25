"""Subjects to link to, and the open commitments about a subject."""

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from gobernar360.dashboards.registry import MONTH
from gobernar360.platform import subjects
from gobernar360.platform.access import Context
from gobernar360.platform.api_types import OrmModel, Year
from gobernar360.platform.clock import Today
from gobernar360.platform.listing import SearchText
from gobernar360.platform.subjects import SubjectOut

router = APIRouter(prefix="/subjects", tags=["subjects"])

Key = Annotated[str, Query(max_length=50)]


class KindOut(OrmModel):
    dashboard_key: str
    kind: str


class SubjectCommitmentOut(OrmModel):
    id: uuid.UUID
    ref: str
    description: str
    owner: str
    due_date: date
    overdue: bool
    times_postponed: int
    path: str


@router.get("/kinds")
def list_kinds(ctx: Context) -> list[KindOut]:
    """What the member may link to: their dashboards' months and declared records."""
    return [KindOut(dashboard_key=key, kind=kind) for key, kind in subjects.visible_kinds(ctx)]


@router.get("/search")
def search_subjects(
    ctx: Context,
    today: Today,
    dashboard_key: Key,
    kind: Key,
    q: SearchText = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[SubjectOut]:
    return subjects.search(ctx, dashboard_key, kind, q or "", today, limit)


@router.get("/{dashboard_key}/commitments")
def list_month_commitments(
    ctx: Context, today: Today, dashboard_key: str, year: Year
) -> list[SubjectCommitmentOut]:
    """Open commitments about any month of the year, for the dashboard's status strip."""
    refs = [subjects.month_ref(year, month) for month in range(1, 13)]
    found = subjects.commitments_about(ctx, dashboard_key, MONTH, refs, today)
    return [SubjectCommitmentOut.model_validate(commitment) for commitment in found]


@router.get("/{dashboard_key}/{kind}/{ref}/commitments")
def list_subject_commitments(
    ctx: Context, today: Today, dashboard_key: str, kind: str, ref: str
) -> list[SubjectCommitmentOut]:
    """Open commitments about one subject, for its own page."""
    found = subjects.commitments_about(ctx, dashboard_key, kind, [ref], today)
    return [SubjectCommitmentOut.model_validate(commitment) for commitment in found]
