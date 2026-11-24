"""The public transparency page: what a municipality published, for anyone, without a session.

These routes connect as the public database role, which can read the published copies
(`public_*`) and nothing else: no tenant table, no account, no session. They never set a
municipality. An address that does not exist, a page that is off and anything not
published all answer the same 404.
"""

import hashlib
import json
import time
from collections import defaultdict, deque
from datetime import datetime
from threading import Lock
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Request, Response
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from gobernar360.core.config import get_settings
from gobernar360.core.db import get_public_db
from gobernar360.core.errors import not_found, rate_limited
from gobernar360.platform.api_types import Year
from gobernar360.platform.models import PublicDashboard, PublicIndicator, PublicReport, PublicSite

WINDOW_SECONDS = 60


class RateLimiter:
    """At most N requests per client address in any minute, kept in memory per process."""

    def __init__(self) -> None:
        self._seen: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, client: str, limit: int) -> None:
        now = time.monotonic()
        with self._lock:
            seen = self._seen[client]
            while seen and seen[0] <= now - WINDOW_SECONDS:
                seen.popleft()
            if len(seen) >= limit:
                raise rate_limited(int(seen[0] + WINDOW_SECONDS - now) + 1)
            seen.append(now)

    def reset(self) -> None:
        with self._lock:
            self._seen.clear()


limiter = RateLimiter()


def limit_rate(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    limiter.check(client, get_settings().public_rate_limit_per_minute)


router = APIRouter(prefix="/public", tags=["public"], dependencies=[Depends(limit_rate)])

PublicDb = Annotated[Session, Depends(get_public_db)]
Month = Annotated[int, Path(ge=1, le=12)]


class LightOut(BaseModel):
    year: int
    month: int
    color: str


class PublicDashboardOut(BaseModel):
    key: str
    name: str
    lights: list[LightOut]


class PublicReportOut(BaseModel):
    year: int
    month: int
    version: int
    closed_at: datetime


class PublicSiteOut(BaseModel):
    slug: str
    name: str
    kind: str
    # Counts below it are shown as "fewer than" it.
    small_count_threshold: int
    dashboards: list[PublicDashboardOut]
    indicators: list[dict[str, Any]]
    reports: list[PublicReportOut]


def _cached(request: Request, body: bytes, media_type: str, **headers: str) -> Response:
    """A response shared caches may keep, but must check again before every use: what is
    unpublished disappears on the next request."""
    tag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    cache = {"ETag": tag, "Cache-Control": "public, no-cache", **headers}
    if request.headers.get("if-none-match") == tag:
        return Response(status_code=304, headers=cache)
    return Response(body, media_type=media_type, headers=cache)


def _json(request: Request, payload: BaseModel | dict[str, Any]) -> Response:
    data = payload.model_dump(mode="json") if isinstance(payload, BaseModel) else payload
    body = json.dumps(jsonable_encoder(data), ensure_ascii=False, sort_keys=True).encode()
    return _cached(request, body, "application/json")


def _site(db: Session, slug: str) -> PublicSite:
    site = db.scalar(select(PublicSite).where(PublicSite.slug == slug))
    if site is None:
        raise not_found()
    return site


@router.get("/{slug}", response_model=PublicSiteOut)
def get_site(request: Request, db: PublicDb, slug: str) -> Response:
    site = _site(db, slug)
    dashboards = db.scalars(
        select(PublicDashboard)
        .where(PublicDashboard.municipality_id == site.municipality_id)
        .order_by(PublicDashboard.position)
    )
    indicators = db.scalars(
        select(PublicIndicator)
        .where(PublicIndicator.municipality_id == site.municipality_id)
        .order_by(PublicIndicator.position)
    )
    reports = db.scalars(
        select(PublicReport)
        .where(PublicReport.municipality_id == site.municipality_id)
        .order_by(PublicReport.year.desc(), PublicReport.month.desc())
    )
    return _json(
        request,
        PublicSiteOut(
            slug=site.slug,
            name=site.name,
            kind=site.kind,
            small_count_threshold=site.small_count_threshold,
            dashboards=[
                PublicDashboardOut(key=row.dashboard_key, name=row.name, lights=row.lights)
                for row in dashboards
            ],
            indicators=[row.data for row in indicators],
            reports=[
                PublicReportOut(
                    year=row.year, month=row.month, version=row.version, closed_at=row.closed_at
                )
                for row in reports
            ],
        ),
    )


@router.get("/{slug}/indicators/{indicator_key}")
def get_indicator(request: Request, db: PublicDb, slug: str, indicator_key: str) -> Response:
    site = _site(db, slug)
    row = db.scalar(
        select(PublicIndicator).where(
            PublicIndicator.municipality_id == site.municipality_id,
            PublicIndicator.indicator_key == indicator_key,
        )
    )
    if row is None:
        raise not_found()
    return _json(request, row.data)


@router.get("/{slug}/reports/{year}/{month}")
def get_report(
    request: Request, db: PublicDb, slug: str, year: Annotated[Year, Path()], month: Month
) -> Response:
    """The published rendition of the month's report, small counts masked."""
    site = _site(db, slug)
    row = db.scalar(
        select(PublicReport).where(
            PublicReport.municipality_id == site.municipality_id,
            PublicReport.year == year,
            PublicReport.month == month,
        )
    )
    if row is None:
        raise not_found()
    filename = f"informe-{site.slug}-{year}-{month:02d}.pdf"
    return _cached(
        request,
        row.pdf,
        "application/pdf",
        **{"Content-Disposition": f'inline; filename="{filename}"'},
    )
