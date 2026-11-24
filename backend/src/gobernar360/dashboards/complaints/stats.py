"""Summary statistics computed the way a spreadsheet does, so exported data can be checked."""

import math
from collections.abc import Sequence


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Linear interpolation between closest ranks, like PERCENTILE.INC; None without values."""
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * fraction
    lower = math.floor(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (position - lower) * (ordered[upper] - ordered[lower])


def median(values: Sequence[float]) -> float | None:
    return percentile(values, 0.5)


def ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None
