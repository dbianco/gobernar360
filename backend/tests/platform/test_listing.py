"""Searching: what a word typed in a search box matches."""

import pytest
from sqlalchemy import literal, select

from gobernar360.core.db import get_admin_engine
from gobernar360.platform.listing import contains, every_word


def _matches(value: str, word: str) -> bool:
    with get_admin_engine().connect() as connection:
        return connection.scalar(select(contains(literal(value), word)))


@pytest.mark.parametrize(
    ("value", "word"),
    [
        ("Pérez, Juana", "perez"),
        ("PEREZ", "pérez"),
        ("Ñandú", "nandu"),
        ("Juana Pérez", "ana p"),
    ],
)
def test_a_word_matches_inside_ignoring_case_and_accents(value, word):
    assert _matches(value, word)


@pytest.mark.parametrize(
    ("value", "word", "expected"),
    [
        ("50% off", "50%", True),
        ("500 off", "50%", False),
        ("plan_b", "n_b", True),
        ("plan-b", "n_b", False),
        ("C:\\datos", "c:\\d", True),
        ("C:datos", "c:\\d", False),
        ("C:\\\\datos", "\\\\", True),
        ("C:\\datos", "\\\\", False),
    ],
)
def test_wildcards_and_backslashes_typed_are_taken_literally(value, word, expected):
    assert _matches(value, word) is expected


def test_every_word_must_appear_in_one_of_the_columns():
    name, dni = literal("Pérez, Juana"), literal("20123456")

    def found(text: str | None) -> bool:
        conditions = every_word(text, name, document=dni)
        with get_admin_engine().connect() as connection:
            return all(connection.scalar(select(condition)) for condition in conditions)

    assert every_word(None, name) == []
    assert every_word("   ", name) == []
    assert found("juana perez")
    assert found("20.123.456")
    assert found("perez 20123")
    assert not found("juana gomez")
    assert not found("99")
    # Without a document column, digits are searched in the other columns only.
    assert len(every_word("20123456", name)) == 1
