"""Relay for frontend Sentry envelopes, so ad-blockers that drop `*.sentry.io` don't hide errors.

The browser SDK (`tunnel: { basePath: "/api" }`) posts to `/api/<hash of its DSN>`; Traefik
strips `/api`, so the route lives at `/<hash>`. Only envelopes for SENTRY_FRONTEND_DSN are
forwarded. Abuse can only spend the Sentry project quota, which Sentry rate-limits.
"""

from __future__ import annotations

import json
import logging
import os

import httpx
from fastapi import APIRouter, Request, Response

from app.core.observability import canonical_dsn, envelope_url, tunnel_path

log = logging.getLogger(__name__)

FORWARD_TIMEOUT_S = 30.0
# Not forwarded: cookies, Referer (same-origin, it holds the page query string), client IP.
_FORWARDED_REQUEST_HEADERS = ("content-type", "user-agent", "origin")
_FORWARDED_RESPONSE_HEADERS = ("content-type", "retry-after", "x-sentry-rate-limits")


def build_tunnel_router() -> APIRouter | None:
    """Router serving the relay for SENTRY_FRONTEND_DSN, or None when it is unset."""
    dsn = os.environ.get("SENTRY_FRONTEND_DSN", "").strip()
    if not dsn:
        return None

    allowed_dsn = canonical_dsn(dsn)
    ingest_url = envelope_url(dsn)
    router = APIRouter()

    @router.post(f"/{tunnel_path(dsn)}", include_in_schema=False)
    async def relay_sentry_envelope(request: Request) -> Response:
        body = await request.body()
        try:
            envelope_dsn = json.loads(body.split(b"\n", 1)[0]).get("dsn")
        except ValueError, AttributeError:
            return Response("Invalid envelope", status_code=400)
        if envelope_dsn != allowed_dsn:
            return Response("DSN not allowed", status_code=403)

        headers = {k: v for k in _FORWARDED_REQUEST_HEADERS if (v := request.headers.get(k))}
        try:
            async with httpx.AsyncClient(timeout=FORWARD_TIMEOUT_S) as client:
                upstream = await client.post(ingest_url, content=body, headers=headers)
        except httpx.HTTPError as exc:
            log.warning("Sentry relay: forward failed (%s)", type(exc).__name__)
            return Response(status_code=502)

        return Response(
            upstream.content,
            status_code=upstream.status_code,
            headers={k: v for k in _FORWARDED_RESPONSE_HEADERS if (v := upstream.headers.get(k))},
        )

    return router
