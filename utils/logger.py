"""Logging utilities for Bio Dashboard.

Provides structured logging with performance timing.
All timestamps are in Thailand timezone (UTC+7).
"""
import logging
import time
from functools import wraps
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta

# Thailand timezone (UTC+7)
TH_TIMEZONE = timezone(timedelta(hours=7))


class ThailandFormatter(logging.Formatter):
    """Custom formatter that uses Thailand timezone."""

    def formatTime(self, record, datefmt=None):
        # Convert to Thailand timezone
        dt = datetime.fromtimestamp(record.created, tz=TH_TIMEZONE)
        if datefmt:
            return dt.strftime(datefmt)
        return dt.strftime('%Y-%m-%d %H:%M:%S')


# Configure logging with Thailand timezone
handler = logging.StreamHandler()
handler.setFormatter(ThailandFormatter('%(asctime)s | %(levelname)s | %(message)s'))

logger = logging.getLogger('bio_dashboard')
logger.setLevel(logging.INFO)
logger.handlers = [handler]  # Replace default handlers


def get_th_time():
    """Get current time in Thailand timezone."""
    return datetime.now(TH_TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')


def log_info(message: str):
    """Log info message with Thailand timestamp."""
    logger.info(f"[{get_th_time()}] {message}")


def log_error(message: str):
    """Log error message with Thailand timestamp."""
    logger.error(f"[{get_th_time()}] {message}")


def log_warning(message: str):
    """Log warning message with Thailand timestamp."""
    logger.warning(f"[{get_th_time()}] {message}")


def log_perf(operation: str, duration_ms: float):
    """Log performance metric."""
    if duration_ms > 1000:
        logger.warning(f"[SLOW] {operation}: {duration_ms:.0f}ms")
    else:
        logger.info(f"[PERF] {operation}: {duration_ms:.0f}ms")


@contextmanager
def log_duration(operation: str):
    """Context manager to log operation duration.

    Usage:
        with log_duration("Query cards"):
            results = session.query(Card).all()
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        duration_ms = (time.perf_counter() - start) * 1000
        log_perf(operation, duration_ms)


def timed(operation_name: str = None):
    """Decorator to log function execution time.

    Usage:
        @timed("Get overview stats")
        def get_overview_stats():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            op_name = operation_name or func.__name__
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.perf_counter() - start) * 1000
                log_perf(op_name, duration_ms)
                return result
            except Exception as e:
                duration_ms = (time.perf_counter() - start) * 1000
                log_error(f"{op_name} failed after {duration_ms:.0f}ms: {str(e)}")
                raise
        return wrapper
    return decorator
