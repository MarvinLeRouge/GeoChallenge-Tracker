"""Tests for app.core.observability.configure_logging and the request logging middleware."""

import json
import logging
from collections.abc import MutableMapping
from typing import Any

import pytest
import structlog
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from structlog.testing import capture_logs

from app.core.observability import configure_logging
from app.core.request_logging import log_requests


@pytest.fixture
def restore_logging():
    """Undo configure_logging's global changes after each test."""
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    access = logging.getLogger("uvicorn.access")
    saved_access = (access.handlers[:], access.propagate)
    yield
    root.handlers, root.level = saved[0], saved[1]
    access.handlers, access.propagate = saved_access
    structlog.reset_defaults()


def _json_lines(err: str) -> list[dict]:
    return [json.loads(line) for line in err.splitlines() if line.strip()]


@pytest.mark.usefixtures("restore_logging")
class TestConfigureLogging:
    def test_structlog_logger_writes_json_line(self, capsys, monkeypatch):
        monkeypatch.delenv("LOG_FORMAT", raising=False)
        configure_logging(is_terminal=False)

        structlog.get_logger("app.test").info("cache_imported", count=3)

        [line] = _json_lines(capsys.readouterr().err)
        assert line["event"] == "cache_imported"
        assert line["count"] == 3
        assert line["level"] == "info"
        assert line["logger"] == "app.test"
        assert "timestamp" in line

    def test_stdlib_logger_is_rendered_as_json_with_traceback(self, capsys):
        configure_logging(is_terminal=False)

        try:
            raise ValueError("boom")
        except ValueError:
            logging.getLogger("app.legacy").exception("Import failed for %s", "GC123")

        [line] = _json_lines(capsys.readouterr().err)
        assert line["event"] == "Import failed for GC123"
        assert line["level"] == "error"
        assert "ValueError: boom" in line["exception"]

    def test_console_format_is_not_json(self, capsys, monkeypatch):
        monkeypatch.setenv("LOG_FORMAT", "console")
        configure_logging(is_terminal=False)

        logging.getLogger("app.test").warning("readable")

        err = capsys.readouterr().err
        assert "readable" in err
        assert not err.lstrip().startswith("{")

    def test_log_level_filters_lower_records(self, capsys, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "warning")
        configure_logging(is_terminal=False)

        logging.getLogger("app.test").info("hidden")
        logging.getLogger("app.test").warning("shown")

        assert [line["event"] for line in _json_lines(capsys.readouterr().err)] == ["shown"]

    def test_second_call_does_not_double_lines(self, capsys):
        configure_logging(is_terminal=False)
        configure_logging(is_terminal=False)

        logging.getLogger("app.test").warning("once")

        assert len(_json_lines(capsys.readouterr().err)) == 1

    def test_uvicorn_access_log_is_silenced(self, capsys):
        configure_logging(is_terminal=False)

        logging.getLogger("uvicorn.access").info(
            '"GET /auth/verify-email?code=secret HTTP/1.1" 200'
        )

        assert "secret" not in capsys.readouterr().err


def _app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(log_requests)

    @app.get("/ok")
    async def ok() -> dict:
        return {}

    @app.get("/boom")
    async def boom() -> dict:
        raise RuntimeError("boom")

    return app


class TestLogRequests:
    async def _get(self, url: str) -> list[MutableMapping[str, Any]]:
        transport = ASGITransport(app=_app(), raise_app_exceptions=False)
        with capture_logs() as logs:
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get(url)
        return logs

    async def test_logs_path_without_query_string(self):
        [entry] = await self._get("/ok?code=secret")

        assert entry["event"] == "request_handled"
        assert entry["log_level"] == "info"
        assert entry["method"] == "GET"
        assert entry["path"] == "/ok"
        assert entry["status"] == 200
        assert isinstance(entry["duration_ms"], int)
        assert "secret" not in repr(entry)

    async def test_logs_unhandled_exception_as_error_500(self):
        [entry] = await self._get("/boom")

        assert entry["log_level"] == "error"
        assert entry["status"] == 500
