"""Tests for app.core.observability and the error reporting of the exception handlers."""

import logging
from unittest.mock import patch

import pytest
import sentry_sdk
from fastapi import FastAPI, Request, Response
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sentry_sdk.transport import Transport
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exception_handlers import register_exception_handlers
from app.core.observability import SENTRY_DATA_COLLECTION, init_error_tracking
from app.core.rate_limit import limiter, rate_limited

FAKE_DSN = "https://public@o0.ingest.de.sentry.io/0"


class TestInitErrorTracking:
    @pytest.mark.parametrize("dsn", [None, "", "   "])
    def test_disabled_without_dsn(self, monkeypatch, dsn):
        if dsn is None:
            monkeypatch.delenv("SENTRY_DSN", raising=False)
        else:
            monkeypatch.setenv("SENTRY_DSN", dsn)

        with patch("app.core.observability.sentry_sdk.init") as init:
            assert init_error_tracking() is False

        init.assert_not_called()

    def test_initializes_with_privacy_options(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", f" {FAKE_DSN} ")
        monkeypatch.setenv("SENTRY_ENVIRONMENT", "production")

        with patch("app.core.observability.sentry_sdk.init") as init:
            assert init_error_tracking() is True

        init.assert_called_once_with(
            dsn=FAKE_DSN,
            environment="production",
            data_collection=SENTRY_DATA_COLLECTION,
            traces_sample_rate=0.0,
        )

    def test_environment_defaults_to_development(self, monkeypatch):
        monkeypatch.setenv("SENTRY_DSN", FAKE_DSN)
        monkeypatch.setenv("SENTRY_ENVIRONMENT", " ")

        with patch("app.core.observability.sentry_sdk.init") as init:
            init_error_tracking()

        assert init.call_args.kwargs["environment"] == "development"

    def test_no_request_data_collected(self):
        assert SENTRY_DATA_COLLECTION["http_bodies"] == []
        assert SENTRY_DATA_COLLECTION["stack_frame_variables"] is False
        assert SENTRY_DATA_COLLECTION["frame_context_lines"] == 0
        assert SENTRY_DATA_COLLECTION["cookies"] == {"mode": "off"}
        assert SENTRY_DATA_COLLECTION["url_query_params"] == {"mode": "off"}


class _CapturingTransport(Transport):
    def __init__(self):
        super().__init__()
        self.events: list[dict] = []

    def capture_envelope(self, envelope):
        for item in envelope.items:
            if item.type == "event":
                self.events.append(item.payload.json)


class _Body(BaseModel):
    value: int


# Module level: each `rate_limited` call registers one more limit under the same key.
@rate_limited("1/minute")
async def _limited(request: Request, response: Response):
    return {"ok": True}


def _build_app() -> FastAPI:
    app = FastAPI()
    limiter.reset()
    app.state.limiter = limiter
    register_exception_handlers(app)

    @app.post("/boom")
    async def boom():
        raise RuntimeError("unexpected crash")

    @app.get("/missing")
    async def missing():
        raise StarletteHTTPException(status_code=404, detail="Not found")

    @app.get("/denied")
    async def denied():
        raise StarletteHTTPException(status_code=401, detail="Unauthorized")

    @app.post("/validated")
    async def validated(body: _Body):
        return body

    app.add_api_route("/limited", _limited, methods=["GET"])
    return app


@pytest.fixture
def sentry_events():
    transport = _CapturingTransport()
    sentry_sdk.init(
        dsn=FAKE_DSN,
        data_collection=SENTRY_DATA_COLLECTION,
        traces_sample_rate=0.0,
        transport=transport,
    )
    yield transport.events
    sentry_sdk.init()


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    return AsyncClient(transport=transport, base_url="http://test")


class TestErrorReporting:
    @pytest.mark.asyncio
    async def test_unhandled_error_is_reported_once_without_request_data(
        self, sentry_events, caplog
    ):
        async with await _client(_build_app()) as client:
            with caplog.at_level(logging.ERROR, logger="app.core.exception_handlers"):
                response = await client.post(
                    "/boom?token=secret",
                    json={"password": "hunter2"},
                    headers={"Authorization": "Bearer secret-jwt"},
                    cookies={"session": "secret-cookie"},
                )
        sentry_sdk.flush()

        assert response.status_code == 500
        assert response.json()["error"]["code"] == "INTERNAL_ERROR"
        assert any(r.exc_info for r in caplog.records)
        assert len(sentry_events) == 1
        assert sentry_events[0]["exception"]["values"][0]["type"] == "RuntimeError"
        payload = repr(sentry_events[0])
        for secret in ("hunter2", "secret-jwt", "secret-cookie", "token=secret"):
            assert secret not in payload

    @pytest.mark.asyncio
    async def test_client_errors_are_not_reported(self, sentry_events):
        async with await _client(_build_app()) as client:
            statuses = [
                (await client.get("/missing")).status_code,
                (await client.get("/denied")).status_code,
                (await client.post("/validated", json={"value": "nope"})).status_code,
                (await client.get("/limited")).status_code,
                (await client.get("/limited")).status_code,
            ]
        sentry_sdk.flush()

        assert statuses == [404, 401, 422, 200, 429]
        assert sentry_events == []
