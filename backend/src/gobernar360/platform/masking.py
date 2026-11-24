"""Small counts shown outside the municipality as "fewer than N".

A count of 2 households in a rural area can point at a family; the municipality sets the
threshold below which counts are not shown. Ratios and percentages are not counts.
"""

from gobernar360.platform.indicators import Number


def is_masked(value: Number | None, unit: str | None, threshold: int) -> bool:
    """Whether a value must be hidden: a count from 1 up to the threshold minus one."""
    return unit is None and value is not None and 0 < value < threshold


def masked(
    value: Number | None, unit: str | None, threshold: int
) -> tuple[Number | None, int | None]:
    """The value to show and, when it is hidden, the number it is below."""
    if is_masked(value, unit, threshold):
        return None, threshold
    return value, None
