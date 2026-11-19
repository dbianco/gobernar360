"""How loaded values become a year's figure and how that figure compares with its target.
Pure functions: no database access."""

from collections.abc import Mapping
from decimal import Decimal

HIGHER_IS_BETTER = "higher_is_better"
LOWER_IS_BETTER = "lower_is_better"
MONTHLY = "monthly"


def expected_loads(frequency: str) -> int:
    """How many values a variable is expected to have in one year."""
    return 12 if frequency == MONTHLY else 1


def annual_value(aggregation: str, values_by_period: Mapping[int, Decimal]) -> Decimal | None:
    """The year's figure from the values loaded so far; None when nothing was loaded."""
    if not values_by_period:
        return None
    values = list(values_by_period.values())
    if aggregation == "average":
        return sum(values, Decimal("0")) / len(values)
    if aggregation == "last":
        return values_by_period[max(values_by_period)]
    return sum(values, Decimal("0"))


def achievement(direction: str, value: Decimal | None, target: Decimal | None) -> float | None:
    """Share of the target reached, where 1.0 means the target is met.

    A cap ("lower is better") never scores above 1.0: being further under it is not
    more compliant. A goal ("higher is better") can be exceeded.
    """
    if value is None or target is None:
        return None
    if direction == LOWER_IS_BETTER:
        if value <= target:
            return 1.0
        if target <= 0:
            return 0.0
        return round(float(target / value), 4)
    if target <= 0:
        return None
    return max(0.0, round(float(value / target), 4))


def target_met(direction: str, value: Decimal | None, target: Decimal | None) -> bool | None:
    if value is None or target is None:
        return None
    return value <= target if direction == LOWER_IS_BETTER else value >= target
