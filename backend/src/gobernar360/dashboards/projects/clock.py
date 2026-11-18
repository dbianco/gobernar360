"""The current date, as a dependency so tests can pin it."""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends

# Deadlines are judged in Argentine local time, not the server's.
LOCAL_TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def get_today() -> date:
    return datetime.now(LOCAL_TIMEZONE).date()


Today = Annotated[date, Depends(get_today)]
