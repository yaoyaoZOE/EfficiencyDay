from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def local_today(timezone_name: str, *, now: datetime | None = None) -> date:
    instant = now if now is not None else utc_now()
    if instant.tzinfo is None or instant.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    return instant.astimezone(ZoneInfo(timezone_name)).date()
