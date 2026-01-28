"""Timezone utilities for Bio Dashboard.

Uses timezone-aware datetime with Thailand timezone (Asia/Bangkok, UTC+7).
"""
from datetime import datetime, timezone, timedelta

# Thailand timezone (UTC+7)
TH_TIMEZONE = timezone(timedelta(hours=7))


def now_th() -> datetime:
    """Get current datetime in Thailand timezone (timezone-aware)."""
    return datetime.now(TH_TIMEZONE)


def now_utc() -> datetime:
    """Get current datetime in UTC (timezone-aware)."""
    return datetime.now(timezone.utc)


def utc_to_th(dt: datetime) -> datetime:
    """Convert UTC datetime to Thailand timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetime is UTC
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TH_TIMEZONE)


def th_to_utc(dt: datetime) -> datetime:
    """Convert Thailand timezone datetime to UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Assume naive datetime is Thailand time
        dt = dt.replace(tzinfo=TH_TIMEZONE)
    return dt.astimezone(timezone.utc)


def format_th(dt: datetime, fmt: str = '%Y-%m-%d %H:%M:%S') -> str:
    """Format datetime as Thailand time string."""
    if dt is None:
        return '-'
    th_dt = utc_to_th(dt) if dt.tzinfo == timezone.utc else dt
    return th_dt.strftime(fmt)
