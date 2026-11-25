import pytest

from gobernar360.platform.geo.suppression import hidden_cells


@pytest.mark.parametrize(
    ("counts", "hidden"),
    [
        ([], set()),
        ([5, 6, 40], set()),
        # Small ones, and none else: what is hidden adds up to enough.
        ([4, 3, 40, 9], {0, 1}),
        # Alone, a small count is the total minus the rest, so the next smallest goes too.
        ([4, 40, 9], {0, 2}),
        ([1, 2, 40, 9], {0, 1, 3}),
        # Exactly the threshold is not small.
        ([4, 1, 5], {0, 1}),
        # Nothing to protect in what is empty.
        ([0, 0, 40], {0, 1}),
        ([0, 3, 5, 5], {0, 1, 2}),
        # Everything goes when there is not enough to hide it behind.
        ([2], {0}),
        ([2, 0], {0, 1}),
    ],
)
def test_small_counts_cannot_be_worked_out(counts, hidden):
    assert hidden_cells(counts, 5) == hidden


def test_the_threshold_decides_what_is_small():
    assert hidden_cells([1, 2, 3], 1) == set()
    assert hidden_cells([1, 2, 3], 2) == {0, 1}


def test_hiding_stops_as_soon_as_there_is_enough():
    # 1 alone is not enough; with the first 2 it is not either; with the second 2 it is.
    assert hidden_cells([1, 2, 2, 9, 9], 2) == {0, 1}
    assert hidden_cells([3, 5, 6, 7], 5) == {0, 1}
    # What was hidden before still counts when more is added.
    assert hidden_cells([1, 1, 5, 6], 5) == {0, 1, 2}
    assert hidden_cells([1, 1, 1, 10, 10], 10) == {0, 1, 2, 3}
