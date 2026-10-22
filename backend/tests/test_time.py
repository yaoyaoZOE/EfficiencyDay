from datetime import UTC, datetime, timedelta

import pytest

from app.core.time import local_today, utc_now


def test_utc_now_is_timezone_aware() -> None:
    assert utc_now().utcoffset() == timedelta(0)


def test_local_today_uses_account_timezone() -> None:
    instant = datetime(2026, 10, 21, 16, 30, tzinfo=UTC)

    assert local_today("Asia/Shanghai", now=instant).isoformat() == "2026-10-22"


def test_local_today_rejects_naive_datetime() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        local_today("Asia/Shanghai", now=datetime(2026, 10, 21, 16, 30))
