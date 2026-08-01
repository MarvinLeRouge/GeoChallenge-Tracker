# backend/app/core/utils.py
# Basic time utilities (naive UTC and timezone-aware UTC).

import datetime as dt


def now():
    """UTC date/time (naive).

    Description:
        Returns the current UTC instant as a naive datetime (no tzinfo attached).
        Historically returned `datetime.now()` (naive *local* time), which is silently
        mistreated as UTC by both `python-jose` (JWT `exp`/`iat` encoding) and Motor/PyMongo
        (naive datetimes are stored as-is, without conversion) - correct only by coincidence
        when the process happens to run on a host whose local timezone is UTC. Kept naive
        (rather than switching to `utcnow()`'s aware datetime) so every existing call site,
        and every value already read back from MongoDB (also naive, since the driver isn't
        configured with `tz_aware=True`), stays comparable without raising
        `TypeError: can't compare offset-naive and offset-aware datetimes`.

    Returns:
        datetime.datetime: UTC timestamp (naive).
    """
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)


def utcnow():
    """UTC date/time (timezone-aware).

    Description:
        Returns `datetime.now(timezone.utc)` with the UTC timezone attached. Recommended
        for persisted timestamps and comparisons.

    Returns:
        datetime.datetime: UTC timestamp (aware).
    """
    return dt.datetime.now(dt.timezone.utc)
