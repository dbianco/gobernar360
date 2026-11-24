"""Monthly snapshots of every headline indicator of every enabled dashboard.

Run once a day, or at least on the last day of each month: each run records the current
month as of that day, so the last run of a month leaves its value at the close. Closed
months can be rebuilt, but only for the indicators a dashboard declares reconstructible:
the others keep whatever was recorded at the time, or stay empty.
"""

import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import delete, func, select, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from gobernar360.core.db import platform_session, tenant_session
from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule, IndicatorDefinition
from gobernar360.platform import publication
from gobernar360.platform.access import enabled_dashboard_keys, system_context
from gobernar360.platform.indicators import Month, last_day, month_of, months_between, shift
from gobernar360.platform.models import IndicatorSnapshot, Municipality

logger = logging.getLogger(__name__)


@dataclass
class SnapshotReport:
    month: Month
    # Closed months rebuilt, oldest first; empty when none was asked for.
    rebuilt: list[Month] = field(default_factory=list)
    municipalities: int = 0
    # Rows inserted, changed or removed; zero when nothing changed since the last run.
    changed_rows: int = 0
    failed: list[str] = field(default_factory=list)


def _store(
    db: Session,
    municipality_id: uuid.UUID,
    module: DashboardModule,
    month: Month,
    definitions: Sequence[IndicatorDefinition],
    as_of: date,
) -> int:
    """Record the given indicators of a module for one month, as of a date."""
    values = {
        indicator.key: indicator.value
        for indicator in module.get_summary(system_context(db, municipality_id), as_of)
    }
    year, number = month
    rows = [
        {
            "municipality_id": municipality_id,
            "dashboard_key": module.key,
            "indicator_key": definition.key,
            "year": year,
            "month": number,
            "value": None
            if values[definition.key] is None
            else Decimal(str(values[definition.key])),
        }
        for definition in definitions
        if definition.key in values
    ]
    changed = 0
    if rows:
        statement = insert(IndicatorSnapshot).values(rows)
        statement = statement.on_conflict_do_update(
            index_elements=["municipality_id", "indicator_key", "year", "month"],
            set_={
                "value": statement.excluded.value,
                "dashboard_key": statement.excluded.dashboard_key,
                "taken_at": func.now(),
            },
            # A run that finds the same value leaves the row exactly as it was.
            where=IndicatorSnapshot.value.is_distinct_from(statement.excluded.value),
        )
        # Rows skipped by the condition above are not returned.
        changed += len(db.execute(statement.returning(IndicatorSnapshot.id)).all())
    # An indicator the dashboard no longer reports for that month has no value there.
    missing = [definition.key for definition in definitions if definition.key not in values]
    if missing:
        changed += db.execute(
            delete(IndicatorSnapshot).where(
                IndicatorSnapshot.indicator_key.in_(missing),
                tuple_(IndicatorSnapshot.year, IndicatorSnapshot.month) == month,
            )
        ).rowcount
    return changed


def snapshot_municipality(
    municipality_id: uuid.UUID, today: date, rebuild: Iterable[Month] = ()
) -> int:
    """Snapshot one municipality in its own tenant-scoped transaction.

    Returns the number of rows changed. Row-level security keeps every read and write
    inside the municipality.
    """
    changed = 0
    with tenant_session(municipality_id) as db:
        for key in sorted(enabled_dashboard_keys(db, municipality_id)):
            module = registry.get_module(key)
            if not module.indicators:
                continue
            changed += _store(
                db, municipality_id, module, month_of(today), module.indicators, today
            )
            reconstructible = [d for d in module.indicators if d.reconstructible]
            if not reconstructible:
                continue
            for month in rebuild:
                changed += _store(
                    db, municipality_id, module, month, reconstructible, last_day(month)
                )
        # Published indicators show the evolution just recorded.
        publication.refresh_indicators(system_context(db, municipality_id), today)
    return changed


def take_snapshots(today: date, since: Month | None = None) -> SnapshotReport:
    """Snapshot every municipality for the current month and, when `since` is given, rebuild
    the closed months from `since` on. A municipality that fails is rolled back alone."""
    report = SnapshotReport(month=month_of(today))
    if since is not None:
        report.rebuilt = months_between(since, shift(month_of(today), -1))
    with platform_session() as db:
        municipalities = db.execute(
            select(Municipality.id, Municipality.slug).order_by(Municipality.slug)
        ).all()
    for municipality_id, slug in municipalities:
        try:
            report.changed_rows += snapshot_municipality(municipality_id, today, report.rebuilt)
        except Exception:
            logger.exception("Snapshot of %s failed", slug)
            report.failed.append(slug)
        else:
            report.municipalities += 1
    return report
