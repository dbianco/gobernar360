"""What a municipality publishes, copied to the tables the public page reads.

Publishing is opt-in at three levels: the page itself (`public_settings`), each dashboard
and each indicator. The copies (`public_*`) are written here, in the municipality's own
transaction, whenever the selection changes and on every snapshot run; the public routes
read nothing else. Removing the site row removes everything published under it.
"""

import re
import unicodedata
from datetime import date
from typing import Any

from sqlalchemy import delete, select

from gobernar360.core.errors import personal_data
from gobernar360.dashboards import registry
from gobernar360.platform import indicators
from gobernar360.platform.access import RequestContext, enabled_dashboard_keys
from gobernar360.platform.indicators import IndicatorEvolution, month_of, months_between, shift
from gobernar360.platform.masking import masked
from gobernar360.platform.models import (
    DashboardStatus,
    MonthlyReport,
    Municipality,
    Person,
    PublicDashboard,
    PublicIndicator,
    PublicReport,
    PublicSettings,
    PublicSite,
    PublishedDashboard,
    PublishedIndicator,
)
from gobernar360.platform.report_pdf import ReportDocument, render_report

LIGHT_MONTHS = 12


def settings_of(ctx: RequestContext) -> PublicSettings | None:
    return ctx.db.scalar(select(PublicSettings))


def _site(ctx: RequestContext) -> PublicSite | None:
    return ctx.db.get(PublicSite, ctx.municipality_id)


def public_report(
    document: MonthlyReport, threshold: int, selection: dict[str, frozenset[str]] | None = None
) -> bytes:
    """The rendition of a closed report that can be handed to anyone: with `selection`, only
    the dashboards and indicators the municipality publishes."""
    return render_report(
        ReportDocument(
            content=document.content,
            comments=document.comments,
            version=document.version,
            closed_at=document.closed_at,
            public_threshold=threshold,
            public_selection=selection,
        )
    )


def public_evolution(evolution: IndicatorEvolution, threshold: int) -> dict[str, Any]:
    """An indicator's evolution as the public sees it: small counts hidden, and whatever
    would let them be worked out (changes, deviation, whether the target is met) with them."""
    unit = evolution.unit
    value, value_below = masked(evolution.value, unit, threshold)
    previous, previous_below = masked(evolution.previous_value, unit, threshold)
    last_year, last_year_below = masked(evolution.last_year_value, unit, threshold)
    series = []
    for point in evolution.series:
        shown, below = masked(point.value, unit, threshold)
        series.append(
            {
                "year": point.year,
                "month": point.month,
                "value": shown,
                "below": below,
                "target": point.target,
            }
        )
    return {
        "key": evolution.key,
        "unit": unit,
        "higher_is_better": evolution.higher_is_better,
        "value": value,
        "value_below": value_below,
        "previous_value": previous,
        "previous_below": previous_below,
        "change_previous_month": None
        if value_below or previous_below
        else evolution.change_previous_month,
        "last_year_value": last_year,
        "last_year_below": last_year_below,
        "change_last_year": None if value_below or last_year_below else evolution.change_last_year,
        "target": evolution.target,
        "on_track": None if value_below else evolution.on_track,
        "series": series,
    }


def _published_modules(ctx: RequestContext) -> list[registry.DashboardModule]:
    """Published dashboards that are still enabled and installed, in install order."""
    published = set(ctx.db.scalars(select(PublishedDashboard.dashboard_key)))
    enabled = enabled_dashboard_keys(ctx.db, ctx.municipality_id)
    return [m for m in registry.all_modules() if m.key in published and m.key in enabled]


def _copy_dashboards(ctx: RequestContext, settings: PublicSettings, today: date) -> None:
    db = ctx.db
    db.execute(
        delete(PublicIndicator).where(PublicIndicator.municipality_id == ctx.municipality_id)
    )
    db.execute(
        delete(PublicDashboard).where(PublicDashboard.municipality_id == ctx.municipality_id)
    )
    chosen = set(db.scalars(select(PublishedIndicator.indicator_key)))
    first = shift(month_of(today), 1 - LIGHT_MONTHS)
    position = 0
    for order, module in enumerate(_published_modules(ctx)):
        lights = {
            (row.year, row.month): row.color
            for row in db.scalars(
                select(DashboardStatus).where(DashboardStatus.dashboard_key == module.key)
            )
        }
        db.add(
            PublicDashboard(
                municipality_id=ctx.municipality_id,
                dashboard_key=module.key,
                name=module.name or module.key,
                position=order,
                lights=[
                    {"year": year, "month": month, "color": lights[(year, month)]}
                    for year, month in months_between(first, month_of(today))
                    if (year, month) in lights
                ],
            )
        )
        keys = [d.key for d in module.indicators if d.aggregate and d.key in chosen]
        if not keys:
            continue
        values = indicators.current_values(ctx, module, today)
        for evolution in indicators.dashboard_evolution(ctx, module, today, values, keys=keys):
            data = public_evolution(evolution, settings.small_count_threshold)
            data |= {"name": module.indicator(evolution.key).display_name}
            data |= {"dashboard_key": module.key}
            db.add(
                PublicIndicator(
                    municipality_id=ctx.municipality_id,
                    dashboard_key=module.key,
                    indicator_key=evolution.key,
                    position=position,
                    data=data,
                )
            )
            position += 1


def _selection(ctx: RequestContext) -> dict[str, frozenset[str]]:
    """The published indicators of each published dashboard."""
    chosen = set(ctx.db.scalars(select(PublishedIndicator.indicator_key)))
    return {
        module.key: frozenset(d.key for d in module.indicators if d.aggregate and d.key in chosen)
        for module in _published_modules(ctx)
    }


def _copy_report(ctx: RequestContext, settings: PublicSettings, report: MonthlyReport) -> None:
    ctx.db.add(
        PublicReport(
            municipality_id=ctx.municipality_id,
            year=report.year,
            month=report.month,
            version=report.version,
            closed_at=report.closed_at,
            pdf=public_report(report, settings.small_count_threshold, _selection(ctx)),
        )
    )


def forget_dashboards(ctx: RequestContext, keep: set[str]) -> None:
    """Drop what was chosen to publish of every dashboard not in `keep`: one the operator
    disables must not come back on the public page by itself when it is enabled again."""
    for model in (PublishedIndicator, PublishedDashboard):
        ctx.db.execute(delete(model).where(model.dashboard_key.not_in(keep)))
    ctx.db.flush()


def refresh_site(ctx: RequestContext, today: date) -> None:
    """Rewrite every copy of the municipality from its current selection."""
    db = ctx.db
    db.execute(delete(PublicSite).where(PublicSite.municipality_id == ctx.municipality_id))
    db.flush()
    settings = settings_of(ctx)
    if settings is None or not settings.enabled:
        return
    municipality = db.get(Municipality, ctx.municipality_id)
    db.add(
        PublicSite(
            municipality_id=ctx.municipality_id,
            slug=settings.slug,
            name=municipality.name,
            kind=municipality.kind,
            small_count_threshold=settings.small_count_threshold,
        )
    )
    db.flush()
    _copy_dashboards(ctx, settings, today)
    for report in db.scalars(
        select(MonthlyReport).where(
            MonthlyReport.published.is_(True), MonthlyReport.status == "closed"
        )
    ):
        _copy_report(ctx, settings, report)
    db.flush()


def refresh_indicators(ctx: RequestContext, today: date) -> None:
    """Rewrite the published lights and indicators after new snapshots. A change of what is
    published needs `refresh_site`, which also renders the published reports again."""
    settings = settings_of(ctx)
    if settings is None or not settings.enabled or _site(ctx) is None:
        return
    _copy_dashboards(ctx, settings, today)
    ctx.db.flush()


def _normalized(text: str) -> str:
    plain = unicodedata.normalize("NFKD", text.lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", plain).strip()


# A document number however it is written: 30222111, 30.222.111, 30 222 111, 30-222-111.
_DIGIT_RUNS = re.compile(r"\d+(?:[.\- ]\d+)*")


def _has_document(text: str, dni: str) -> bool:
    """Whether the digits of `dni` appear as whole groups of digits, one after another."""
    for run in _DIGIT_RUNS.findall(text):
        groups = re.split(r"[.\- ]", run)
        for start in range(len(groups)):
            joined = ""
            for group in groups[start:]:
                joined += group
                if joined == dni:
                    return True
                if len(joined) >= len(dni):
                    break
    return False


def names_a_person(ctx: RequestContext, text: str) -> bool:
    """Whether a text has a document number or the name of someone in the registry: their
    last name next to any of their first names, in either order."""
    if not text.strip():
        return False
    words = f" {_normalized(text)} "
    for first_name, last_name, dni, cuil in ctx.db.execute(
        select(Person.first_name, Person.last_name, Person.dni, Person.cuil)
    ):
        if any(document and _has_document(text, document) for document in (dni, cuil)):
            return True
        last = _normalized(last_name)
        for first in _normalized(first_name).split():
            if f" {first} {last} " in words or f" {last} {first} " in words:
                return True
    return False


def publish_report(ctx: RequestContext, report: MonthlyReport) -> None:
    """Mark a closed report published and copy its public rendition, if the page is on."""
    if any(names_a_person(ctx, text) for text in report.comments.values()):
        raise personal_data()
    report.published = True
    ctx.db.flush()
    settings = settings_of(ctx)
    if settings is not None and settings.enabled and _site(ctx) is not None:
        _delete_report_copy(ctx, report)
        _copy_report(ctx, settings, report)
        ctx.db.flush()


def _delete_report_copy(ctx: RequestContext, report: MonthlyReport) -> None:
    ctx.db.execute(
        delete(PublicReport).where(
            PublicReport.municipality_id == ctx.municipality_id,
            PublicReport.year == report.year,
            PublicReport.month == report.month,
        )
    )


def unpublish_report(ctx: RequestContext, report: MonthlyReport) -> None:
    report.published = False
    _delete_report_copy(ctx, report)
    ctx.db.flush()
