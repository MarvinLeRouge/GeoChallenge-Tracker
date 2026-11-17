"""Error tracking (Sentry), enabled only when SENTRY_DSN is set."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import sentry_sdk

if TYPE_CHECKING:
    from sentry_sdk._types import DataCollectionUserOptions

# Stack traces only: requests carry emails, passwords, JWTs and GPX positions.
SENTRY_DATA_COLLECTION: DataCollectionUserOptions = {
    "user_info": False,
    "cookies": {"mode": "off"},
    "http_headers": {"request": {"mode": "off"}},
    "http_bodies": [],
    "url_query_params": {"mode": "off"},
    "graphql": {"document": False, "variables": False},
    "gen_ai": {"inputs": False, "outputs": False},
    "database_query_data": False,
    "queues": False,
    "stack_frame_variables": False,
    "frame_context_lines": 0,
}


def init_error_tracking() -> bool:
    """Initialize Sentry when a DSN is configured.

    Reads SENTRY_DSN and SENTRY_ENVIRONMENT (default "development") from the
    environment directly, before the application settings load.

    Returns:
        True if Sentry was initialized, False if it is disabled.
    """
    dsn = os.environ.get("SENTRY_DSN", "").strip()

    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=os.environ.get("SENTRY_ENVIRONMENT", "").strip() or "development",
        data_collection=SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
    )

    return True
