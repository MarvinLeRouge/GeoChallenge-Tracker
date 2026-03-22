# backend/app/core/utils.py
# Basic time utilities (naive local and timezone-aware UTC).

import datetime as dt


def now():
    """Local date/time (naive).

    Description:
        Returns `datetime.now()` with no timezone attached. Convenient for local use
        but should be avoided for cross-timezone comparisons (prefer `utcnow()`).

    Returns:
        datetime.datetime: Local timestamp (naive).
    """
    return dt.datetime.now()


def utcnow():
    """UTC date/time (timezone-aware).

    Description:
        Returns `datetime.now(timezone.utc)` with the UTC timezone attached. Recommended
        for persisted timestamps and comparisons.

    Returns:
        datetime.datetime: UTC timestamp (aware).
    """
    return dt.datetime.now(dt.timezone.utc)
