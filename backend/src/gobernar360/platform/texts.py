"""Texts the API writes for people, such as emails, from the backend locale file.

Like the web app's, the file is Spanish (es-AR) and uses i18next-style `{{name}}`
placeholders, so the same conventions apply to both.
"""

import json
import re
from datetime import date, datetime
from functools import cache
from importlib import resources
from typing import Any

from gobernar360.platform.clock import LOCAL_TIMEZONE

PLACEHOLDER = re.compile(r"\{\{\s*(\w+)\s*\}\}")


@cache
def _catalog() -> dict[str, Any]:
    source = resources.files("gobernar360") / "locales" / "es-AR.json"
    return json.loads(source.read_text(encoding="utf-8"))


def has_text(key: str) -> bool:
    try:
        _lookup(key)
    except KeyError:
        return False
    return True


def _lookup(key: str) -> str:
    value: Any = _catalog()
    for part in key.split("."):
        if not isinstance(value, dict) or part not in value:
            raise KeyError(f"Missing text: {key}")
        value = value[part]
    if not isinstance(value, str):
        raise KeyError(f"Not a text: {key}")
    return value


def raw(key: str) -> str:
    """The text under `key` with its placeholders left in place."""
    return _lookup(key)


def text(key: str, **params: object) -> str:
    """The text under `key` with its placeholders filled. A missing one is an error."""

    def fill(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in params:
            raise KeyError(f"Text {key} needs {name}")
        return str(params[name])

    return PLACEHOLDER.sub(fill, _lookup(key))


def format_date(value: date) -> str:
    return value.strftime("%d/%m/%Y")


def format_datetime(value: datetime) -> str:
    local = value.astimezone(LOCAL_TIMEZONE)
    return text("dateTime", date=format_date(local.date()), time=local.strftime("%H:%M"))


def month_name(month: int) -> str:
    return text(f"months.{month}")


def dashboard_name(key: str) -> str:
    return text(f"dashboards.{key}")
