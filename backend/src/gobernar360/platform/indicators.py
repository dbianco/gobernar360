"""Headline indicators over time: their monthly history, the targets set for them, and the
indicators that combine two dashboards.

Dashboards are reached only through the registry: each declares its catalogue of
indicators and computes their values with `get_summary(ctx, date)`.
"""

import calendar
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from pydantic import BaseModel
from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from gobernar360.dashboards import registry
from gobernar360.dashboards.registry import DashboardModule, IndicatorDefinition
from gobernar360.platform.access import AccessLevel, RequestContext
from gobernar360.platform.models import IndicatorSnapshot, IndicatorTarget

type Number = int | float
type Month = tuple[int, int]

# The evolution shows the current month and the eleven before it.
SERIES_MONTHS = 12
DECIMALS = 4


def month_index(month: Month) -> int:
    """Months since year 0, so months can be compared and subtracted across years."""
    year, number = month
    return year * 12 + number - 1


def month_at(index: int) -> Month:
    return index // 12, index % 12 + 1


def shift(month: Month, months: int) -> Month:
    return month_at(month_index(month) + months)


def month_of(day: date) -> Month:
    return day.year, day.month


def last_day(month: Month) -> date:
    year, number = month
    return date(year, number, calendar.monthrange(year, number)[1])


def months_between(first: Month, last: Month) -> list[Month]:
    """Every month from `first` to `last`, both included; empty when `first` is later."""
    return [month_at(index) for index in range(month_index(first), month_index(last) + 1)]


def plain(value: Decimal | Number | None) -> Number | None:
    """A stored or computed value as JSON-friendly number: whole values become ints."""
    if value is None:
        return None
    rounded = round(float(value), DECIMALS)
    return int(rounded) if rounded.is_integer() else rounded


def deviation(value: Number | None, target: Number | None, higher_is_better: bool) -> float | None:
    """How far the value is on the good side of its target.

    Positive means better than the target and negative worse, whichever the direction:
    6 delayed projects against a target of 4 is -2.
    """
    if value is None or target is None:
        return None
    difference = value - target if higher_is_better else target - value
    return round(difference, DECIMALS)


def on_track(value: Number | None, target: Number | None, higher_is_better: bool) -> bool | None:
    gap = deviation(value, target, higher_is_better)
    return None if gap is None else gap >= 0


def _difference(value: Number | None, before: Number | None) -> Number | None:
    if value is None or before is None:
        return None
    return plain(value - before)


def history(
    db: Session, keys: Iterable[str], first: Month, last: Month
) -> dict[str, dict[Month, Number | None]]:
    """Snapshot values per indicator and month, between two months included.

    A month missing from an indicator's dict was never recorded; one present with None was
    recorded without a value.
    """
    keys = list(keys)
    result: dict[str, dict[Month, Number | None]] = {key: {} for key in keys}
    if not keys:
        return result
    month = tuple_(IndicatorSnapshot.year, IndicatorSnapshot.month)
    rows = db.execute(
        select(
            IndicatorSnapshot.indicator_key,
            IndicatorSnapshot.year,
            IndicatorSnapshot.month,
            IndicatorSnapshot.value,
        ).where(
            IndicatorSnapshot.indicator_key.in_(keys),
            month >= first,
            month <= last,
        )
    )
    for key, year, number, value in rows:
        result[key][(year, number)] = plain(value)
    return result


def targets(db: Session, keys: Iterable[str], years: Iterable[int]) -> dict[str, dict[int, Number]]:
    """Targets per indicator and year."""
    keys, years = list(keys), list(years)
    result: dict[str, dict[int, Number]] = {key: {} for key in keys}
    if not keys or not years:
        return result
    rows = db.execute(
        select(IndicatorTarget.indicator_key, IndicatorTarget.year, IndicatorTarget.value).where(
            IndicatorTarget.indicator_key.in_(keys), IndicatorTarget.year.in_(years)
        )
    )
    for key, year, value in rows:
        result[key][year] = plain(value)
    return result


@dataclass(frozen=True)
class CombinedIndicator:
    """An indicator that relates two dashboards: one catalogue value over another."""

    key: str
    numerator: str
    denominator: str
    higher_is_better: bool | None = None
    unit: str | None = None

    @property
    def reconstructible(self) -> bool:
        parts = [registry.find_indicator(key) for key in (self.numerator, self.denominator)]
        return all(part is not None and part[1].reconstructible for part in parts)

    def dashboards(self) -> list[DashboardModule] | None:
        """The installed modules behind both parts, or None when one is not installed."""
        parts = [registry.find_indicator(key) for key in (self.numerator, self.denominator)]
        if any(part is None for part in parts):
            return None
        return [module for module, _ in parts]

    def compute(self, numerator: Number | None, denominator: Number | None) -> Number | None:
        if numerator is None or not denominator:
            return None
        return plain(numerator / denominator)


class SeriesPoint(BaseModel):
    year: int
    month: int
    value: Number | None
    # The target of the month's year, drawn as the target line.
    target: Number | None


class IndicatorEvolution(BaseModel):
    """An indicator today, against its past and against its target."""

    key: str
    unit: str | None
    # Null only for combined indicators where neither direction is better.
    higher_is_better: bool | None
    reconstructible: bool
    # Computed now, as of today.
    value: Number | None
    # At the close of the previous month, and of the same month a year ago.
    previous_value: Number | None
    change_previous_month: Number | None
    last_year_value: Number | None
    change_last_year: Number | None
    # This year's target; the deviation is positive when the value is better than it.
    target: Number | None
    deviation: Number | None
    deviation_ratio: float | None
    on_track: bool | None
    # The last twelve months, oldest first; the last one is the current month, as of today.
    series: list[SeriesPoint]


def evolution(
    definition: IndicatorDefinition | CombinedIndicator,
    value: Decimal | Number | None,
    past: Mapping[Month, Number | None],
    yearly_targets: Mapping[int, Number],
    today: date,
) -> IndicatorEvolution:
    """Put a value computed today next to its recorded past months and its targets."""
    value = plain(value)
    current = month_of(today)
    previous = past.get(shift(current, -1))
    last_year = past.get(shift(current, -12))
    target = yearly_targets.get(today.year)
    higher_is_better = definition.higher_is_better
    gap = deviation(value, target, higher_is_better) if higher_is_better is not None else None
    series = [
        SeriesPoint(
            year=month[0],
            month=month[1],
            value=value if month == current else past.get(month),
            target=yearly_targets.get(month[0]),
        )
        for month in months_between(shift(current, 1 - SERIES_MONTHS), current)
    ]
    return IndicatorEvolution(
        key=definition.key,
        unit=definition.unit,
        higher_is_better=higher_is_better,
        reconstructible=definition.reconstructible,
        value=value,
        previous_value=previous,
        change_previous_month=_difference(value, previous),
        last_year_value=last_year,
        change_last_year=_difference(value, last_year),
        target=target,
        deviation=plain(gap),
        deviation_ratio=round(gap / abs(target), DECIMALS) if gap is not None and target else None,
        on_track=on_track(value, target, higher_is_better)
        if higher_is_better is not None
        else None,
        series=series,
    )


def series_window(today: date) -> tuple[Month, Month]:
    """The recorded months an evolution needs: a year back from the previous month."""
    current = month_of(today)
    return shift(current, -12), shift(current, -1)


def current_values(ctx: RequestContext, module: DashboardModule, today: date) -> dict[str, Number]:
    """The module's indicators as of today, by key."""
    return {indicator.key: indicator.value for indicator in module.get_summary(ctx, today)}


def dashboard_evolution(
    ctx: RequestContext,
    module: DashboardModule,
    today: date,
    values: Mapping[str, Number | None],
    keys: Iterable[str] | None = None,
) -> list[IndicatorEvolution]:
    """Evolution of the given indicators of a dashboard; all of its catalogue by default."""
    keys = [definition.key for definition in module.indicators] if keys is None else list(keys)
    first, last = series_window(today)
    past = history(ctx.db, keys, first, last)
    goals = targets(ctx.db, keys, {first[0], today.year})
    return [
        evolution(
            module.indicator(key) or IndicatorDefinition(key),
            values.get(key),
            past[key],
            goals[key],
            today,
        )
        for key in keys
    ]


COMBINED_INDICATORS = (
    # How far the offer of online procedures reaches the local economy.
    CombinedIndicator(
        "combined.online_procedures_per_actor",
        "procedures.online",
        "economic.actors",
        higher_is_better=True,
    ),
    # How much direct social assistance there is for each project under way. Neither
    # direction is better in itself, so changes are shown without judging them.
    CombinedIndicator(
        "combined.deliveries_per_active_project", "social.deliveries_year", "projects.active"
    ),
)


def visible_combined(
    levels: Mapping[str, AccessLevel],
) -> list[tuple[CombinedIndicator, list[DashboardModule]]]:
    """Combined indicators whose dashboards are all installed, enabled and visible."""
    visible = []
    for combined in COMBINED_INDICATORS:
        modules = combined.dashboards()
        if modules is None:
            continue
        if all(
            levels.get(module.key, AccessLevel.NONE) >= AccessLevel.VIEWER for module in modules
        ):
            visible.append((combined, modules))
    return visible


class CombinedEvolution(IndicatorEvolution):
    # The dashboards it is built from, so a page can show it only next to them.
    dashboard_keys: list[str]


def combined_evolution(
    ctx: RequestContext,
    combined: CombinedIndicator,
    values: Mapping[str, Number | None],
    today: date,
) -> CombinedEvolution:
    """Evolution of a combined indicator from today's values and the history of its parts."""
    first, last = series_window(today)
    past = history(ctx.db, [combined.numerator, combined.denominator], first, last)
    months = past[combined.numerator].keys() & past[combined.denominator].keys()
    combined_past = {
        month: combined.compute(past[combined.numerator][month], past[combined.denominator][month])
        for month in months
    }
    value = combined.compute(values.get(combined.numerator), values.get(combined.denominator))
    result = evolution(combined, value, combined_past, {}, today)
    return CombinedEvolution(
        **result.model_dump(),
        dashboard_keys=[module.key for module in combined.dashboards() or []],
    )
