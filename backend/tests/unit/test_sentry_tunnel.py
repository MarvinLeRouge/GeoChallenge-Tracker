"""Tests for the frontend Sentry envelope relay (app.api.routes.sentry_tunnel)."""

import json
from unittest.mock import patch

import httpx
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.sentry_tunnel import build_tunnel_router
from app.core.observability import tunnel_path

FRONTEND_DSN = "https://public@o0.ingest.de.sentry.io/0"
OTHER_DSN = "https://intruder@o9.ingest.de.sentry.io/9"
PATH = f"/{tunnel_path(FRONTEND_DSN)}"
# Captured before the tests patch `httpx.AsyncClient` in the route module.
_RealAsyncClient = httpx.AsyncClient


def _envelope(dsn: str) -> bytes:
    return json.dumps({"dsn": dsn}).encode() + b'\n{"type":"event"}\n{"message":"boom"}'


class _FakeSentry:
    """Stands in for httpx.AsyncClient: records the forwarded request, answers like Sentry."""

    def __init__(self, error: Exception | None = None):
        self.error = error
        self.calls: list[dict] = []

    def client(self, **kwargs):
        def handler(request: httpx.Request) -> httpx.Response:
            if self.error:
                raise self.error
            self.calls.append(
                {"url": str(request.url), "headers": request.headers, "body": request.content}
            )
            return httpx.Response(
                200,
                json={"id": "abc"},
                headers={"x-sentry-rate-limits": "60::organization", "set-cookie": "leak=1"},
            )

        return _RealAsyncClient(transport=httpx.MockTransport(handler), **kwargs)


@pytest.fixture
def relay(monkeypatch):
    monkeypatch.setenv("SENTRY_FRONTEND_DSN", f" {FRONTEND_DSN} ")
    router = build_tunnel_router()
    assert router is not None
    app = FastAPI()
    app.include_router(router)
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.parametrize("dsn", [None, "", "  "])
def test_no_router_without_frontend_dsn(monkeypatch, dsn):
    if dsn is None:
        monkeypatch.delenv("SENTRY_FRONTEND_DSN", raising=False)
    else:
        monkeypatch.setenv("SENTRY_FRONTEND_DSN", dsn)
    assert build_tunnel_router() is None


@pytest.mark.asyncio
async def test_forwards_allowed_envelope_without_private_headers(relay):
    sentry = _FakeSentry()
    body = _envelope(FRONTEND_DSN)
    with patch("app.api.routes.sentry_tunnel.httpx.AsyncClient", side_effect=sentry.client):
        async with relay as client:
            response = await client.post(
                PATH,
                content=body,
                headers={
                    "content-type": "text/plain;charset=UTF-8",
                    "user-agent": "Mozilla/5.0",
                    "origin": "https://gct.test",
                    "referer": "https://gct.test/verify-email?token=secret",
                    "cookie": "session=secret",
                    "x-forwarded-for": "203.0.113.7",
                },
            )

    assert response.status_code == 200
    assert response.headers["x-sentry-rate-limits"] == "60::organization"
    assert "set-cookie" not in response.headers
    [call] = sentry.calls
    assert call["url"] == (
        "https://o0.ingest.de.sentry.io/api/0/envelope/?sentry_version=7&sentry_key=public"
    )
    assert call["body"] == body
    assert call["headers"]["user-agent"] == "Mozilla/5.0"
    assert call["headers"]["origin"] == "https://gct.test"
    for private in ("referer", "cookie", "x-forwarded-for"):
        assert private not in call["headers"]


@pytest.mark.asyncio
async def test_rejects_foreign_dsn(relay):
    sentry = _FakeSentry()
    with patch("app.api.routes.sentry_tunnel.httpx.AsyncClient", side_effect=sentry.client):
        async with relay as client:
            response = await client.post(PATH, content=_envelope(OTHER_DSN))

    assert response.status_code == 403
    assert sentry.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("body", "status"),
    [(b"", 400), (b"not json\n{}", 400), (b"[1, 2]\n{}", 400), (b'{"no": "dsn"}\n{}', 403)],
)
async def test_rejects_malformed_envelope(relay, body, status):
    async with relay as client:
        response = await client.post(PATH, content=body)

    assert response.status_code == status


@pytest.mark.asyncio
async def test_answers_502_when_sentry_is_unreachable(relay):
    sentry = _FakeSentry(error=httpx.ConnectError("down"))
    with patch("app.api.routes.sentry_tunnel.httpx.AsyncClient", side_effect=sentry.client):
        async with relay as client:
            response = await client.post(PATH, content=_envelope(FRONTEND_DSN))

    assert response.status_code == 502


@pytest.mark.asyncio
async def test_other_paths_are_not_served(relay):
    async with relay as client:
        response = await client.post("/abcdef", content=_envelope(FRONTEND_DSN))

    assert response.status_code == 404
