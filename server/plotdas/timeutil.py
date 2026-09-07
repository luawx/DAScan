from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

DEFAULT_TIMEZONE = "Asia/Shanghai"


def parse_datetime(value: str | datetime, timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """Parse a user time and normalize it to the configured wall-clock zone."""
    zone = ZoneInfo(timezone)
    if isinstance(value, datetime):
        parsed = value
    else:
        text = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError(f"Invalid datetime {value!r}; use YYYY-MM-DD HH:MM:SS") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=zone)
    return parsed.astimezone(zone)


def reinterpret_wall_clock(value: datetime, timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """Keep clock fields but replace a misleading embedded source offset."""
    return value.replace(tzinfo=ZoneInfo(timezone))

