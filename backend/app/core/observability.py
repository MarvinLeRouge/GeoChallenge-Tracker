"""Error tracking (Sentry), enabled only when SENTRY_BACKEND_DSN is set."""

from __future__ import annotations

import logging
import os
import re
from typing import TYPE_CHECKING

import sentry_sdk
from sentry_sdk.utils import Dsn

if TYPE_CHECKING:
    from sentry_sdk._types import DataCollectionUserOptions, Event, Hint

log = logging.getLogger(__name__)

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

_PRIVATE_REQUEST_KEYS = ("data", "headers", "cookies", "query_string", "env")


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def scrub_event(event: Event, hint: Hint) -> Event:
    """Safety net on top of SENTRY_DATA_COLLECTION: drops request data and breadcrumbs.

    Args:
        event: Event about to be sent.
        hint: Sentry hint (unused).

    Returns:
        The same event, without request body, headers, cookies, query string,
        environ, breadcrumbs, and with the URL reduced to its path.
    """
    request = event.get("request")
    if request:
        for key in _PRIVATE_REQUEST_KEYS:
            request.pop(key, None)  # type: ignore[misc]
        if isinstance(url := request.get("url"), str):
            request["url"] = re.split(r"[?#]", url)[0]
    event.pop("breadcrumbs", None)  # type: ignore[misc]
    return event


def init_error_tracking() -> bool:
    """Initialize Sentry when a DSN is configured.

    Reads SENTRY_BACKEND_DSN and SENTRY_ENVIRONMENT (default "development") from the
    environment directly, before the application settings load. Warns when only one of
    SENTRY_BACKEND_DSN / SENTRY_FRONTEND_DSN is set, a likely half-done configuration.

    Returns:
        True if Sentry was initialized, False if it is disabled.
    """
    dsn = os.environ.get("SENTRY_BACKEND_DSN", "").strip()

    if bool(dsn) != bool(_env("SENTRY_FRONTEND_DSN")):
        log.warning("Only one of SENTRY_BACKEND_DSN and SENTRY_FRONTEND_DSN is set")

    if not dsn:
        return False

    sentry_sdk.init(
        dsn=dsn,
        environment=_env("SENTRY_ENVIRONMENT") or "development",
        data_collection=SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
        before_send=scrub_event,
        before_breadcrumb=lambda crumb, hint: None,
    )

    return True


def canonical_dsn(dsn: str) -> str:
    """DSN in the form the browser SDK writes in envelope headers (`dsnToString`).

    Raises:
        sentry_sdk.utils.BadDsn: If the DSN is malformed.
    """
    parsed = Dsn(dsn)
    return f"{parsed.scheme}://{parsed.public_key}@{parsed.netloc}{parsed.path}{parsed.project_id}"


def tunnel_path(dsn: str) -> str:
    """Relay path the browser SDK derives from its DSN: base36 FNV-1a 32-bit hash.

    Mirrors `getTunnelPath` / `fnv1a32` from `@sentry/core`, so `tunnel: { basePath }`
    in the browser reaches this backend without sharing any path by hand.
    """
    value = 2166136261
    for char in canonical_dsn(dsn):
        value = ((value ^ ord(char)) * 16777619) & 0xFFFFFFFF
    digits = ""
    while True:
        value, remainder = divmod(value, 36)
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"[remainder] + digits
        if not value:
            return digits


def envelope_url(dsn: str) -> str:
    """Sentry ingest endpoint for envelopes sent with this DSN."""
    parsed = Dsn(dsn)
    return (
        f"{parsed.scheme}://{parsed.netloc}{parsed.path}api/{parsed.project_id}/envelope/"
        f"?sentry_version=7&sentry_key={parsed.public_key}"
    )
