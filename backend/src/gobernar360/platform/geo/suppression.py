"""Hiding small counts from members who may not see the records behind them."""


def hidden_cells(counts: list[int], threshold: int) -> set[int]:
    """Positions of the counts to hide so that none below `threshold` can be worked out.

    Hiding only the small counts is not enough: the total is known, so a single hidden
    count is the total minus the rest. When what is hidden adds up to less than
    `threshold`, the smallest count left is hidden too, which is always enough.
    """
    hidden = {index for index, count in enumerate(counts) if count < threshold}
    total = sum(counts[index] for index in hidden)
    rest = set(range(len(counts))) - hidden
    if 0 < total < threshold and rest:
        # Of several as small, the first: the answer does not change between requests.
        hidden.add(min(rest, key=lambda index: (counts[index], index)))
    return hidden
