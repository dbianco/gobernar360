"""Monthly management reports: what closing a month freezes, and reopening it.

A closed report is a copy. Its content is built once, when the month is closed, from the
status lights, the indicator snapshots and targets, and the tables each dashboard adds
through the registry; nothing later reads the live data again.
"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import func, select

from gobernar360.core.errors import conflict, month_not_over, validation_error
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule, IndicatorDefinition
from gobernar360.platform import indicators
from gobernar360.platform.access import RequestContext, enabled_dashboard_keys
from gobernar360.platform.audit import apply_audit_fields, record_change
from gobernar360.platform.indicators import Month, Number, last_day, months_between, shift
from gobernar360.platform.models import DashboardStatus, MonthlyReport, Municipality
from gobernar360.platform.tenant_crud import create_entity

COMMENT_MAX_LENGTH = 2000


def has_ended(year: int, month: int, today: date) -> bool:
    return (year, month) < indicators.month_of(today)


def installed_dashboards(ctx: RequestContext) -> list[DashboardModule]:
    """The municipality's enabled dashboards, in the order the application installs them."""
    enabled = enabled_dashboard_keys(ctx.db, ctx.municipality_id)
    return [module for module in registry.all_modules() if module.key in enabled]


def _indicator_content(
    ctx: RequestContext,
    module: DashboardModule,
    month: Month,
) -> list[dict[str, Any]]:
    """Each indicator at the close of the month, against the month before and its target."""
    first = shift(month, 1 - indicators.SERIES_MONTHS)
    keys = [definition.key for definition in module.indicators]
    past = indicators.history(ctx.db, keys, first, month)
    goals = indicators.targets(ctx.db, keys, {first[0], month[0]})
    # Months without a snapshot are rebuilt, for the indicators that can be, as the
    # snapshot command would; the others stay empty.
    rebuilt: dict[Month, dict[str, Number | None]] = {}

    def value_at(definition: IndicatorDefinition, at: Month) -> Number | None:
        if at in past[definition.key]:
            return past[definition.key][at]
        if not definition.reconstructible:
            return None
        if at not in rebuilt:
            rebuilt[at] = indicators.current_values(ctx, module, last_day(at))
        return indicators.plain(rebuilt[at].get(definition.key))

    entries = []
    for definition in module.indicators:
        value = value_at(definition, month)
        previous = value_at(definition, shift(month, -1))
        target = goals[definition.key].get(month[0])
        entries.append(
            {
                "key": definition.key,
                "name": definition.display_name,
                "unit": definition.unit,
                "higher_is_better": definition.higher_is_better,
                "aggregate": definition.aggregate,
                "value": value,
                "previous_value": previous,
                "change": None
                if value is None or previous is None
                else indicators.plain(value - previous),
                "target": target,
                "deviation": indicators.deviation(value, target, definition.higher_is_better),
                "on_track": indicators.on_track(value, target, definition.higher_is_better),
                "series": [
                    {
                        "year": at[0],
                        "month": at[1],
                        "value": value_at(definition, at),
                        "target": goals[definition.key].get(at[0]),
                    }
                    for at in months_between(first, month)
                ],
            }
        )
    return entries


def build_content(ctx: RequestContext, year: int, month: int) -> dict[str, Any]:
    """Everything a month's report shows, as plain JSON."""
    municipality = ctx.db.get(Municipality, ctx.municipality_id)
    lights = dict(
        ctx.db.execute(
            select(DashboardStatus.dashboard_key, DashboardStatus.color).where(
                DashboardStatus.year == year, DashboardStatus.month == month
            )
        ).all()
    )
    first, last = date(year, month, 1), last_day((year, month))
    dashboards = []
    for module in installed_dashboards(ctx):
        tables = module.report_tables(ctx, first, last) if module.report_tables else []
        dashboards.append(
            {
                "key": module.key,
                "name": module.name or module.key,
                "light": lights.get(module.key),
                "indicators": _indicator_content(ctx, module, (year, month)),
                "tables": [
                    {
                        "key": table.key,
                        "title": table.title,
                        "columns": [
                            {"title": column.title, "kind": column.kind} for column in table.columns
                        ],
                        "rows": [list(row) for row in table.rows],
                    }
                    for table in tables
                ],
            }
        )
    return {
        "municipality": {"name": municipality.name, "kind": municipality.kind},
        "year": year,
        "month": month,
        "dashboards": dashboards,
    }


def clean_comments(ctx: RequestContext, comments: dict[str, str]) -> dict[str, str]:
    """Comments of the municipality's dashboards, trimmed; empty ones are dropped."""
    known = {module.key for module in installed_dashboards(ctx)}
    unknown = sorted(set(comments) - known)
    if unknown:
        raise validation_error(f"No dashboard to comment on: {', '.join(unknown)}.")
    cleaned = {key: text.strip() for key, text in comments.items() if text.strip()}
    if any(len(text) > COMMENT_MAX_LENGTH for text in cleaned.values()):
        raise validation_error(f"A comment can have at most {COMMENT_MAX_LENGTH} characters.")
    return cleaned


def current_version(ctx: RequestContext, year: int, month: int) -> MonthlyReport | None:
    """The month's draft or closed version; superseded ones are history."""
    return ctx.db.scalar(
        select(MonthlyReport).where(
            MonthlyReport.year == year,
            MonthlyReport.month == month,
            MonthlyReport.status != "superseded",
        )
    )


def _now() -> datetime:
    # Whole seconds: the closing time is also the PDF's date, and stays stable.
    return datetime.now(UTC).replace(microsecond=0)


def close_month(
    ctx: RequestContext, year: int, month: int, comments: dict[str, str], today: date
) -> MonthlyReport:
    """Freeze the month's report: a new version, or the draft left by reopening it."""
    if not has_ended(year, month, today):
        raise month_not_over()
    comments = clean_comments(ctx, comments)
    report = current_version(ctx, year, month)
    if report is not None and report.status == "closed":
        raise conflict("The month is already closed; reopen it to close it again.")
    content = build_content(ctx, year, month)
    if report is None:
        version = (
            ctx.db.scalar(
                select(func.max(MonthlyReport.version)).where(
                    MonthlyReport.year == year, MonthlyReport.month == month
                )
            )
            or 0
        ) + 1
        report = MonthlyReport(year=year, month=month, version=version, status="draft")
        create_entity(ctx, report, {"year": year, "month": month, "version": version})
    report.status = "closed"
    report.content = content
    report.comments = comments
    report.closed_at = _now()
    apply_audit_fields(ctx, report, creating=False)
    ctx.db.flush()
    # The trail keeps what was decided, not the whole frozen content.
    record_change(ctx, "update", report, {"status": "closed", "comments": comments})
    return report


def reopen(ctx: RequestContext, report: MonthlyReport) -> MonthlyReport:
    """Supersede a closed report and start its next version as a draft with its comments.

    A published report stops being published: its public copy is removed at once.
    """
    from gobernar360.platform import publication

    if report.status != "closed":
        raise conflict("Only the closed version of a month can be reopened.")
    if report.published:
        publication.unpublish_report(ctx, report)
    report.status = "superseded"
    report.reopened_at = _now()
    apply_audit_fields(ctx, report, creating=False)
    ctx.db.flush()
    record_change(ctx, "update", report, {"status": "superseded", "reopened": True})
    draft = MonthlyReport(
        year=report.year,
        month=report.month,
        version=report.version + 1,
        status="draft",
        comments=dict(report.comments),
    )
    return create_entity(
        ctx,
        draft,
        {"year": report.year, "month": report.month, "version": draft.version, "reopened": True},
    )
