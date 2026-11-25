"""CSV download of the commitments."""

import uuid

from fastapi import APIRouter, Response

from gobernar360.dashboards.cabinet.access import Viewer
from gobernar360.dashboards.cabinet.commitments_router import query_taken
from gobernar360.dashboards.cabinet.minutes import subject_line
from gobernar360.dashboards.cabinet.present import present_commitments
from gobernar360.platform.clock import Today
from gobernar360.platform.commitment_schemas import StateFilter
from gobernar360.platform.csv_export import csv_response, safe_text
from gobernar360.platform.listing import SearchText

router = APIRouter()

COLUMNS = (
    "meeting_date",
    "description",
    "owner",
    "due_date",
    "state",
    "completed_on",
    "times_postponed",
    "subject_dashboard",
    "subject",
)


@router.get("/export/commitments.csv")
def export_commitments(
    ctx: Viewer,
    today: Today,
    q: SearchText = None,
    state: StateFilter | None = None,
    owner_id: uuid.UUID | None = None,
) -> Response:
    query = query_taken(today, q, state, owner_id)
    commitments = present_commitments(ctx, list(ctx.db.scalars(query).unique()), today)
    rows = (
        (
            c.meeting.date,
            safe_text(c.description),
            safe_text(c.owner.full_name),
            c.due_date,
            c.state,
            c.completed_on or "",
            c.times_postponed,
            (c.subject and c.subject.dashboard_key) or "",
            safe_text(subject_line(ctx, c.subject)),
        )
        for c in commitments
    )
    return csv_response("commitments.csv", COLUMNS, rows)
