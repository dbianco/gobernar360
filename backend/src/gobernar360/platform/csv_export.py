"""CSV downloads that spreadsheets open correctly and safely."""

import csv
import io
from collections.abc import Iterable
from decimal import Decimal
from typing import Any

from fastapi import Response

# Spreadsheets run cells starting with these characters as formulas.
FORMULA_PREFIXES = ("=", "+", "-", "@")


def safe_text(value: Any) -> str:
    """Free text typed by users: neutralise anything a spreadsheet would run as a formula."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_PREFIXES) else text


def plain_number(value: Decimal | None) -> str:
    if value is None:
        return ""
    return format(value.normalize(), "f")


def csv_response(filename: str, header: Iterable[str], rows: Iterable[Iterable[Any]]) -> Response:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    # The byte-order mark makes Excel read the file as UTF-8, keeping accents intact.
    return Response(
        content=("\ufeff" + buffer.getvalue()).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
