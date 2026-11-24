"""Monthly reports: closed, reopened, downloaded and published by municipality admins."""

import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Response
from pydantic import BaseModel, Field
from sqlalchemy import select

from gobernar360.core.errors import conflict, month_not_over
from gobernar360.platform import publication, reports
from gobernar360.platform.access import RequestContext, require_municipality_admin
from gobernar360.platform.api_types import OrmModel, Year
from gobernar360.platform.audit import record_change
from gobernar360.platform.clock import Today
from gobernar360.platform.models import MonthlyReport, Municipality
from gobernar360.platform.report_pdf import ReportDocument, render_report
from gobernar360.platform.tenant_crud import get_or_404

router = APIRouter(prefix="/reports", tags=["reports"])

Admin = Annotated[RequestContext, Depends(require_municipality_admin)]
Month = Annotated[int, Path(ge=1, le=12)]


class ReportSummaryOut(OrmModel):
    id: uuid.UUID
    year: int
    month: int
    version: int
    status: str
    closed_at: datetime | None
    reopened_at: datetime | None
    published: bool


class ReportOut(ReportSummaryOut):
    content: dict[str, Any] | None
    comments: dict[str, str]


class PreviewOut(BaseModel):
    """What closing the month now would freeze, and the comments already written for it."""

    year: int
    month: int
    # The draft left by reopening the month, if any.
    version: int | None
    content: dict[str, Any]
    comments: dict[str, str]


class CloseIn(BaseModel):
    comments: dict[str, Annotated[str, Field(max_length=reports.COMMENT_MAX_LENGTH)]] = {}


class PublicationIn(BaseModel):
    published: bool


@router.get("")
def list_reports(ctx: Admin) -> list[ReportSummaryOut]:
    """Every version of every month, newest first."""
    rows = ctx.db.scalars(
        select(MonthlyReport).order_by(
            MonthlyReport.year.desc(), MonthlyReport.month.desc(), MonthlyReport.version.desc()
        )
    )
    return [ReportSummaryOut.model_validate(row) for row in rows]


@router.get("/preview/{year}/{month}")
def preview(ctx: Admin, today: Today, year: Annotated[Year, Path()], month: Month) -> PreviewOut:
    if not reports.has_ended(year, month, today):
        raise month_not_over()
    current = reports.current_version(ctx, year, month)
    if current is not None and current.status == "closed":
        raise conflict("The month is already closed.")
    return PreviewOut(
        year=year,
        month=month,
        version=current.version if current else None,
        content=reports.build_content(ctx, year, month),
        comments=reports.enabled_comments(ctx, current.comments) if current else {},
    )


@router.post("/{year}/{month}/close", status_code=201)
def close(
    ctx: Admin, today: Today, year: Annotated[Year, Path()], month: Month, body: CloseIn
) -> ReportOut:
    report = reports.close_month(ctx, year, month, body.comments, today)
    return ReportOut.model_validate(report)


@router.get("/{report_id}")
def get_report(ctx: Admin, report_id: uuid.UUID) -> ReportOut:
    return ReportOut.model_validate(get_or_404(ctx, MonthlyReport, report_id))


def _closed(ctx: RequestContext, report_id: uuid.UUID) -> MonthlyReport:
    report = get_or_404(ctx, MonthlyReport, report_id)
    if report.content is None:
        raise conflict("A draft has no document until the month is closed.")
    return report


@router.get("/{report_id}/pdf")
def download(ctx: Admin, report_id: uuid.UUID) -> Response:
    """The report as the municipality hands it out: every figure, as it was at closing."""
    report = _closed(ctx, report_id)
    slug = ctx.db.get(Municipality, ctx.municipality_id).slug
    document = render_report(
        ReportDocument(
            content=report.content,
            comments=report.comments,
            version=report.version,
            closed_at=report.closed_at,
        )
    )
    filename = f"informe-{slug}-{report.year}-{report.month:02d}-v{report.version}.pdf"
    return Response(
        document,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{report_id}/reopen", status_code=201)
def reopen(ctx: Admin, report_id: uuid.UUID) -> ReportSummaryOut:
    """Reopen a closed month: its version is kept as history and a new draft starts."""
    draft = reports.reopen(ctx, get_or_404(ctx, MonthlyReport, report_id))
    return ReportSummaryOut.model_validate(draft)


@router.put("/{report_id}/publication", status_code=204)
def set_publication(ctx: Admin, report_id: uuid.UUID, body: PublicationIn) -> Response:
    report = get_or_404(ctx, MonthlyReport, report_id)
    if body.published == report.published:
        return Response(status_code=204)
    if body.published:
        if report.status != "closed":
            raise conflict("Only the closed version of a month can be published.")
        publication.publish_report(ctx, report)
    else:
        publication.unpublish_report(ctx, report)
    record_change(ctx, "update", report, {"published": body.published})
    return Response(status_code=204)
