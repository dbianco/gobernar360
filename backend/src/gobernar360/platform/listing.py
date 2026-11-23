"""Paginated, searchable lists shared by dashboard modules."""

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Query
from pydantic import BaseModel
from sqlalchemy import ColumnElement, Select, func, or_, select

from gobernar360.platform.access import RequestContext

MAX_PAGE_SIZE = 200


@dataclass(frozen=True)
class Paging:
    limit: int
    offset: int


def get_paging(
    limit: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> Paging:
    return Paging(limit=limit, offset=offset)


PagingParams = Annotated[Paging, Depends(get_paging)]
# Free-text search typed by a person.
SearchText = Annotated[str | None, Query(max_length=100)]


class Page[T](BaseModel):
    items: list[T]
    # How many rows match in total, beyond the page returned.
    total: int


def page_of(ctx: RequestContext, query: Select[Any], paging: Paging) -> dict[str, Any]:
    """Run an ordered query for one page and count everything it matches."""
    total = ctx.db.scalar(select(func.count()).select_from(query.order_by(None).subquery()))
    items = ctx.db.scalars(query.limit(paging.limit).offset(paging.offset)).unique().all()
    return {"items": items, "total": total}


def contains(column: Any, text: str) -> ColumnElement[bool]:
    """ "Contains" ignoring case and accents, with the text's wildcards taken literally.

    People search "perez" for "Pérez"; missing them leads to loading the person twice.
    """
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return func.unaccent(column).ilike(func.unaccent(f"%{escaped}%"), escape="\\")


def every_word(text: str | None, *columns: Any, document: Any = None) -> list[ColumnElement[bool]]:
    """Conditions for a search box: every word typed appears in one of the columns.

    With `document`, a word made of digits (dots allowed, as in "20.123.456") also
    matches that column.
    """
    conditions = []
    for word in (text or "").split():
        options = [contains(column, word) for column in columns]
        digits = word.replace(".", "")
        if document is not None and digits.isdigit():
            options.append(contains(document, digits))
        conditions.append(or_(*options))
    return conditions
