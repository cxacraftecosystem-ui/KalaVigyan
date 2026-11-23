from datetime import UTC, datetime, timedelta

from app.core.clock import INDIA_TZ, INDIA_TZ_NAME
from app.models import Craft, time_zone


def test_india_time_has_one_home_that_the_clock_and_the_craft_default_read() -> None:
    assert INDIA_TZ_NAME is time_zone.INDIA_TZ_NAME
    assert INDIA_TZ_NAME == "Asia/Kolkata"
    assert Craft.__table__.c.recordedTimezone.server_default.arg == INDIA_TZ_NAME


def test_india_keeps_one_offset_all_year() -> None:
    winter, summer = datetime(2026, 1, 15, tzinfo=UTC), datetime(2026, 7, 15, tzinfo=UTC)
    assert INDIA_TZ.utcoffset(winter) == INDIA_TZ.utcoffset(summer) == timedelta(hours=5, minutes=30)
