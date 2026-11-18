"""HTTP middleware writing one structured log line per request."""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

import structlog
from fastapi import Request, Response
from sentry_sdk.integrations.logging import ignore_logger

_LOGGER_NAME = "app.requests"
# 500s already reach Sentry as exceptions: an event per log line would duplicate them.
ignore_logger(_LOGGER_NAME)
log = structlog.get_logger(_LOGGER_NAME)


async def log_requests(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Log method, path, status and duration; never the query string, headers or body."""
    start = time.monotonic()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log.log(
            logging.ERROR if status >= 500 else logging.INFO,
            "request_handled",
            method=request.method,
            path=request.url.path,
            status=status,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
