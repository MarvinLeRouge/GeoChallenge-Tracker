"""Tests for app.core.rate_limit: the Limiter config and the rate_limited() wrapper."""

from typing import Annotated

import pytest
from fastapi import Depends, FastAPI, Request, Response
from httpx import ASGITransport, AsyncClient

from app.core.exception_handlers import register_exception_handlers
from app.core.rate_limit import (
    LOGIN_RATE_LIMIT,
    REGISTER_RATE_LIMIT,
    RESEND_VERIFICATION_RATE_LIMIT,
    limiter,
    rate_limited,
)


class TestRateLimitConstants:
    def test_limit_values(self):
        assert LOGIN_RATE_LIMIT == "10/minute"
        assert REGISTER_RATE_LIMIT == "5/minute"
        assert RESEND_VERIFICATION_RATE_LIMIT == "3/minute"


class TestRateLimited:
    @pytest.mark.asyncio
    async def test_preserves_depends_resolution_under_future_annotations(self):
        """Regression test: under `from __future__ import annotations` (used across this
        codebase), slowapi's `functools.wraps`-based wrapper used to break FastAPI's ability
        to resolve `Annotated[..., Depends(...)]` params, since it evaluates the string
        annotation against slowapi's own module globals instead of the route module's.
        `rate_limited()` restores `__signature__` from the original function to fix this.
        """

        async def get_marker() -> str:
            return "resolved"

        @rate_limited("1000/minute")
        async def sample_route(
            request: Request,
            response: Response,
            marker: Annotated[str, Depends(get_marker)],
        ):
            return {"marker": marker}

        app = FastAPI()
        app.state.limiter = limiter
        app.add_api_route("/test-rate-limit-sample", sample_route, methods=["GET"])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/test-rate-limit-sample")

        assert response.status_code == 200
        assert response.json() == {"marker": "resolved"}

    @pytest.mark.asyncio
    async def test_blocks_requests_beyond_the_limit(self):
        @rate_limited("1/minute")
        async def limited_route(request: Request, response: Response):
            return {"ok": True}

        app = FastAPI()
        app.state.limiter = limiter
        register_exception_handlers(app)
        app.add_api_route("/test-rate-limit-limited", limited_route, methods=["GET"])

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            first = await client.get("/test-rate-limit-limited")
            second = await client.get("/test-rate-limit-limited")

        assert first.status_code == 200
        assert second.status_code == 429
        assert second.headers.get("retry-after") is not None

        body = second.json()
        assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
