"""Monthly status lights: the colour a dashboard's administrator gives each month."""

from datetime import date

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from gobernar360.platform.models import DashboardStatus

PREVIOUS_MONTHS = 5


def _month_index(year: int, month: int) -> int:
    """Months since year 0, so months can be compared and subtracted across years."""
    return year * 12 + month - 1


def is_future(year: int, month: int, today: date) -> bool:
    return _month_index(year, month) > _month_index(today.year, today.month)


def for_year(db: Session, dashboard_key: str, year: int) -> list[DashboardStatus]:
    return list(
        db.scalars(
            select(DashboardStatus)
            .where(DashboardStatus.dashboard_key == dashboard_key, DashboardStatus.year == year)
            .order_by(DashboardStatus.month)
        )
    )


def find(db: Session, dashboard_key: str, year: int, month: int) -> DashboardStatus | None:
    return db.scalar(
        select(DashboardStatus).where(
            DashboardStatus.dashboard_key == dashboard_key,
            DashboardStatus.year == year,
            DashboardStatus.month == month,
        )
    )


def recent(
    db: Session, dashboard_key: str, today: date, previous: int = PREVIOUS_MONTHS
) -> list[DashboardStatus]:
    """The latest light up to today's month, then those set in the `previous`
    calendar months before it, newest first."""
    rows = db.scalars(
        select(DashboardStatus)
        .where(
            DashboardStatus.dashboard_key == dashboard_key,
            tuple_(DashboardStatus.year, DashboardStatus.month) <= (today.year, today.month),
        )
        .order_by(DashboardStatus.year.desc(), DashboardStatus.month.desc())
        .limit(previous + 1)
    ).all()
    if not rows:
        return []
    oldest = _month_index(rows[0].year, rows[0].month) - previous
    return [row for row in rows if _month_index(row.year, row.month) >= oldest]
