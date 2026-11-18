"""Tests for app.core.observability and the error reporting of the exception handlers."""

import logging
from unittest.mock import ANY, patch

import pytest
import sentry_sdk
from fastapi import FastAPI, Request, Response
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel
from sentry_sdk.transport import Transport
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exception_handlers import register_exception_handlers
from app.core.observability import (
    SENTRY_DATA_COLLECTION,
    canonical_dsn,
    envelope_url,
    init_error_tracking,
    scrub_event,
    tunnel_path,
)
from app.core.rate_limit import limiter, rate_limited

FAKE_DSN = "https://public@o0.ingest.de.sentry.io/0"


class TestInitErrorTracking:
    @pytest.mark.parametrize("dsn", [None, "", "   "])
    def test_disabled_without_dsn(self, monkeypatch, dsn):
        monkeypatch.delenv("SENTRY_FRONTEND_DSN", raising=False)
        if dsn is None:
            monkeypatch.delenv("SENTRY_BACKEND_DSN", raising=False)
        else:
            monkeypatch.setenv("SENTRY_BACKEND_DSN", dsn)

        with patch("app.core.observability.sentry_sdk.init") as init:
            assert init_error_tracking() is False

        init.assert_not_called()

    def test_initializes_with_privacy_options(self, monkeypatch):
        monkeypatch.setenv("SENTRY_BACKEND_DSN", f" {FAKE_DSN} ")
        monkeypatch.setenv("SENTRY_ENVIRONMENT", "production")

        with patch("app.core.observability.sentry_sdk.init") as init:
            assert init_error_tracking() is True

        init.assert_called_once_with(
            dsn=FAKE_DSN,
            environment="production",
            data_collection=SENTRY_DATA_COLLECTION,
            traces_sample_rate=0.0,
            before_send=scrub_event,
            before_breadcrumb=ANY,
        )
        assert init.call_args.kwargs["before_breadcrumb"]({"message": "secret"}, {}) is None

    def test_environment_defaults_to_development(self, monkeypatch):
        monkeypatch.setenv("SENTRY_BACKEND_DSN", FAKE_DSN)
        monkeypatch.setenv("SENTRY_ENVIRONMENT", " ")

        with patch("app.core.observability.sentry_sdk.init") as init:
            init_error_tracking()

        assert init.call_args.kwargs["environment"] == "development"

    def test_no_request_data_collected(self):
        assert SENTRY_DATA_COLLECTION == {
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

    @pytest.mark.parametrize(
        ("backend", "frontend", "warned"),
        [(FAKE_DSN, "", True), ("", FAKE_DSN, True), (FAKE_DSN, FAKE_DSN, False), ("", "", False)],
    )
    def test_warns_when_only_one_dsn_is_set(self, monkeypatch, caplog, backend, frontend, warned):
        monkeypatch.setenv("SENTRY_BACKEND_DSN", backend)
        monkeypatch.setenv("SENTRY_FRONTEND_DSN", frontend)

        with patch("app.core.observability.sentry_sdk.init"):
            init_error_tracking()

        assert ("Only one of" in caplog.text) is warned


class TestScrubEvent:
    def test_drops_request_data_and_breadcrumbs(self):
        event = {
            "request": {
                "url": "https://gct.test/verify-email?token=secret#frag",
                "method": "POST",
                "data": {"password": "secret"},
                "headers": {"Authorization": "Bearer secret"},
                "cookies": {"session": "secret"},
                "query_string": "token=secret",
                "env": {"REMOTE_ADDR": "203.0.113.7"},
            },
            "breadcrumbs": {"values": [{"message": "secret"}]},
            "exception": {"values": [{"type": "RuntimeError"}]},
        }

        scrubbed = scrub_event(event, {})

        assert scrubbed["request"] == {"url": "https://gct.test/verify-email", "method": "POST"}
        assert "breadcrumbs" not in scrubbed
        assert scrubbed["exception"] == {"values": [{"type": "RuntimeError"}]}

    def test_event_without_request_is_kept(self):
        assert scrub_event({"message": "boom"}, {}) == {"message": "boom"}


class TestTunnelHelpers:
    # Expected paths computed with `fnv1a32(dsnToString(makeDsn(dsn)))` from @sentry/core 11.14.
    @pytest.mark.parametrize(
        ("dsn", "path"),
        [
            ("https://public@o0.ingest.de.sentry.io/0", "ag8fdb"),
            ("https://abc123@o42.ingest.de.sentry.io/4242", "x7x6bw"),
        ],
    )
    def test_tunnel_path_matches_the_browser_sdk(self, dsn, path):
        assert tunnel_path(dsn) == path

    def test_canonical_dsn_drops_the_secret_and_default_port(self):
        assert (
            canonical_dsn("https://key:secret@o1.ingest.de.sentry.io:443/9")
            == "https://key@o1.ingest.de.sentry.io/9"
        )

    def test_envelope_url(self):
        assert envelope_url(FAKE_DSN) == (
            "https://o0.ingest.de.sentry.io/api/0/envelope/?sentry_version=7&sentry_key=public"
        )


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
def sentry_events(monkeypatch):
    transport = _CapturingTransport()
    real_init = sentry_sdk.init
    monkeypatch.setenv("SENTRY_BACKEND_DSN", FAKE_DSN)
    monkeypatch.setenv("SENTRY_FRONTEND_DSN", FAKE_DSN)
    with patch(
        "app.core.observability.sentry_sdk.init",
        side_effect=lambda **options: real_init(**options, transport=transport),
    ):
        assert init_error_tracking() is True
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
        assert "breadcrumbs" not in sentry_events[0]
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
