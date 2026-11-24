from datetime import timedelta

from gobernar360.platform.clock import LOCAL_TIMEZONE, get_now, get_today


def test_now_is_an_argentine_moment_on_todays_date():
    now = get_now()

    assert now.tzinfo is LOCAL_TIMEZONE
    assert now.utcoffset() == timedelta(hours=-3)
    assert now.date() in (get_today(), get_today() - timedelta(days=1))
