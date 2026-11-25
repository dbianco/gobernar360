from datetime import UTC, date, datetime

import pytest

from gobernar360.platform import clock


@pytest.mark.parametrize(
    ("moment", "today"),
    [
        # 02:59 UTC is still the previous evening in Argentina (UTC-3).
        (datetime(2026, 3, 1, 2, 59, tzinfo=UTC), date(2026, 2, 28)),
        (datetime(2026, 3, 1, 3, 0, tzinfo=UTC), date(2026, 3, 1)),
    ],
)
def test_today_is_argentina_s_whatever_the_server_s_time_zone(monkeypatch, moment, today):
    class Frozen(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)

    monkeypatch.setattr(clock, "datetime", Frozen)

    assert clock.get_today() == today
