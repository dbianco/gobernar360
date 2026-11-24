"""The current date and time, as dependencies so tests can pin them."""

from datetime import date, datetime
from typing import Annotated
from zoneinfo import ZoneInfo

from fastapi import Depends

# Deadlines are judged in Argentine local time, not the server's.
LOCAL_TIMEZONE = ZoneInfo("America/Argentina/Buenos_Aires")


def get_today() -> date:
    return datetime.now(LOCAL_TIMEZONE).date()


def get_now() -> datetime:
    """The current moment, timezone-aware, for recording when something happened."""
    return datetime.now(LOCAL_TIMEZONE)


Today = Annotated[date, Depends(get_today)]
Now = Annotated[datetime, Depends(get_now)]
