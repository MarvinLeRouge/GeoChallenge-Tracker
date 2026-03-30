"""Tests for core utilities: backup_config, meta, email, exception_handlers, middleware."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# backup_config
# ---------------------------------------------------------------------------


class TestDefaultBackupRoot:
    def test_uses_env_var_when_set(self, monkeypatch):
        monkeypatch.setenv("BACKUP_DIR", "/custom/backup")
        # Re-import to re-run module-level code doesn't work, so call the function
        from app.core.backup_config import _default_backup_root

        result = _default_backup_root()
        assert result == Path("/custom/backup")
        monkeypatch.delenv("BACKUP_DIR", raising=False)

    def test_uses_repo_root_when_no_env_and_no_dockerenv(self, monkeypatch):
        monkeypatch.delenv("BACKUP_DIR", raising=False)

        # Ensure /.dockerenv does not appear to exist
        with patch("pathlib.Path.exists", return_value=False):
            from app.core.backup_config import _default_backup_root

            result = _default_backup_root()
            assert "backups" in str(result)

    def test_uses_docker_path_when_dockerenv_exists(self, monkeypatch):
        monkeypatch.delenv("BACKUP_DIR", raising=False)

        with patch("pathlib.Path.exists", return_value=True):
            from app.core.backup_config import _default_backup_root

            result = _default_backup_root()
            assert result == Path("/backups")


class TestEnsureBackupDirs:
    def test_creates_dirs(self, tmp_path):
        from app.core import backup_config

        # Temporarily patch the backup dirs to use tmp_path
        original_cleanup = backup_config.CLEANUP_BACKUP_DIR
        original_full = backup_config.FULL_BACKUP_DIR
        backup_config.CLEANUP_BACKUP_DIR = tmp_path / "cleanup"
        backup_config.FULL_BACKUP_DIR = tmp_path / "full"

        backup_config.ensure_backup_dirs()

        assert (tmp_path / "cleanup").is_dir()
        assert (tmp_path / "full").is_dir()

        backup_config.CLEANUP_BACKUP_DIR = original_cleanup
        backup_config.FULL_BACKUP_DIR = original_full

    def test_raises_permission_error_when_not_writable(self, tmp_path):
        from app.core import backup_config

        original_cleanup = backup_config.CLEANUP_BACKUP_DIR
        original_full = backup_config.FULL_BACKUP_DIR
        backup_config.CLEANUP_BACKUP_DIR = tmp_path / "cleanup"
        backup_config.FULL_BACKUP_DIR = tmp_path / "full"

        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError):
                backup_config.ensure_backup_dirs()

        backup_config.CLEANUP_BACKUP_DIR = original_cleanup
        backup_config.FULL_BACKUP_DIR = original_full


# ---------------------------------------------------------------------------
# meta (health checks)
# ---------------------------------------------------------------------------


class TestCheckMongodb:
    @pytest.mark.asyncio
    async def test_returns_ok_on_success(self):
        mock_db = AsyncMock()
        mock_db.command = AsyncMock(return_value={"ok": 1})

        with patch("app.db.mongodb.get_db", return_value=mock_db):
            from app.core.meta import check_mongodb

            result = await check_mongodb()

        assert result == "ok"

    @pytest.mark.asyncio
    async def test_returns_error_string_on_exception(self):
        with patch("app.db.mongodb.get_db", side_effect=ConnectionError("timeout")):
            from app.core.meta import check_mongodb

            result = await check_mongodb()

        assert "error" in result


class TestCheckEmail:
    @pytest.mark.asyncio
    async def test_returns_ok_on_success(self):
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)
        mock_smtp.noop = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp):
            from app.core.meta import check_email

            result = await check_email()

        assert result == "ok"

    @pytest.mark.asyncio
    async def test_uses_starttls_on_port_587(self):
        """Port 587 → use SMTP (not SSL) and call starttls."""
        mock_smtp = MagicMock()
        mock_smtp.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp.__exit__ = MagicMock(return_value=False)
        mock_smtp.noop = MagicMock()

        with (
            patch("app.core.meta.settings") as mock_settings,
            patch("smtplib.SMTP", return_value=mock_smtp),
        ):
            mock_settings.smtp_port = 587
            mock_settings.smtp_host = "localhost"
            from app.core.meta import check_email

            result = await check_email()

        mock_smtp.starttls.assert_called_once()
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_returns_error_string_on_exception(self):
        with patch("smtplib.SMTP", side_effect=ConnectionRefusedError("refused")):
            from app.core.meta import check_email

            result = await check_email()

        assert "error" in result


# ---------------------------------------------------------------------------
# email
# ---------------------------------------------------------------------------


class TestSendVerificationEmail:
    @pytest.mark.asyncio
    async def test_calls_send_with_correct_args(self):
        with patch("app.core.email.send", new_callable=AsyncMock) as mock_send:
            from app.core.email import send_verification_email

            await send_verification_email("user@example.com", "alice", "abc123")

        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert msg["To"] == "user@example.com"
        assert "abc123" in msg.get_content()

    @pytest.mark.asyncio
    async def test_uses_frontend_url_in_link(self):
        with (
            patch("app.core.email.send", new_callable=AsyncMock) as mock_send,
            patch("app.core.email.settings") as mock_settings,
        ):
            mock_settings.mail_from = "noreply@example.com"
            mock_settings.app_frontend_url = "https://my-app.example.com"
            mock_settings.smtp_host = "localhost"
            mock_settings.smtp_port = 25
            mock_settings.smtp_username = None
            mock_settings.smtp_password = None

            from app.core.email import send_verification_email

            await send_verification_email("user@example.com", "alice", "mycode")

        msg = mock_send.call_args[0][0]
        assert "https://my-app.example.com/verify-email?code=mycode" in msg.get_content()

    @pytest.mark.asyncio
    async def test_start_tls_on_port_587(self):
        with (
            patch("app.core.email.send", new_callable=AsyncMock) as mock_send,
            patch("app.core.email.settings") as mock_settings,
        ):
            mock_settings.mail_from = "noreply@example.com"
            mock_settings.app_frontend_url = "http://localhost:5173"
            mock_settings.smtp_host = "localhost"
            mock_settings.smtp_port = 587
            mock_settings.smtp_username = "user"
            mock_settings.smtp_password = "pass"

            from app.core.email import send_verification_email

            await send_verification_email("user@example.com", "alice", "code")

        kwargs = mock_send.call_args[1]
        assert kwargs["start_tls"] is True
        assert kwargs["use_tls"] is False

    @pytest.mark.asyncio
    async def test_use_tls_on_port_465(self):
        with (
            patch("app.core.email.send", new_callable=AsyncMock) as mock_send,
            patch("app.core.email.settings") as mock_settings,
        ):
            mock_settings.mail_from = "noreply@example.com"
            mock_settings.app_frontend_url = "http://localhost:5173"
            mock_settings.smtp_host = "localhost"
            mock_settings.smtp_port = 465
            mock_settings.smtp_username = "user"
            mock_settings.smtp_password = "pass"

            from app.core.email import send_verification_email

            await send_verification_email("user@example.com", "alice", "code")

        kwargs = mock_send.call_args[1]
        assert kwargs["use_tls"] is True
        assert kwargs["start_tls"] is False

    @pytest.mark.asyncio
    async def test_logs_exception_does_not_raise(self):
        with patch(
            "app.core.email.send", new_callable=AsyncMock, side_effect=Exception("SMTP down")
        ):
            from app.core.email import send_verification_email

            await send_verification_email("user@example.com", "alice", "code")


class TestSendTestEmail:
    @pytest.mark.asyncio
    async def test_sends_email_with_stats(self):
        with (
            patch("app.core.email.send", new_callable=AsyncMock) as mock_send,
            patch("app.core.email.settings") as mock_settings,
        ):
            mock_settings.mail_from = "noreply@example.com"
            mock_settings.smtp_host = "localhost"
            mock_settings.smtp_port = 25
            mock_settings.smtp_username = None
            mock_settings.smtp_password = None

            from app.core.email import send_test_email

            await send_test_email(
                "admin@example.com", user_count=42, cache_count=100, challenge_count=5
            )

        mock_send.assert_called_once()
        msg = mock_send.call_args[0][0]
        assert msg["To"] == "admin@example.com"
        content = msg.get_content()
        assert "42" in content
        assert "100" in content
        assert "5" in content

    @pytest.mark.asyncio
    async def test_start_tls_on_port_587(self):
        with (
            patch("app.core.email.send", new_callable=AsyncMock) as mock_send,
            patch("app.core.email.settings") as mock_settings,
        ):
            mock_settings.mail_from = "noreply@example.com"
            mock_settings.smtp_host = "smtp-relay.brevo.com"
            mock_settings.smtp_port = 587
            mock_settings.smtp_username = "user"
            mock_settings.smtp_password = "key"

            from app.core.email import send_test_email

            await send_test_email("admin@example.com", 1, 2, 3)

        kwargs = mock_send.call_args[1]
        assert kwargs["start_tls"] is True
        assert kwargs["use_tls"] is False

    @pytest.mark.asyncio
    async def test_raises_on_smtp_failure(self):
        with (
            patch(
                "app.core.email.send", new_callable=AsyncMock, side_effect=Exception("SMTP error")
            ),
            patch("app.core.email.settings") as mock_settings,
        ):
            mock_settings.mail_from = "noreply@example.com"
            mock_settings.smtp_host = "localhost"
            mock_settings.smtp_port = 25
            mock_settings.smtp_username = None
            mock_settings.smtp_password = None

            from app.core.email import send_test_email

            with pytest.raises(Exception, match="SMTP error"):
                await send_test_email("admin@example.com", 1, 2, 3)


# ---------------------------------------------------------------------------
# exception_handlers
# ---------------------------------------------------------------------------


class TestErrorResponseFromDetail:
    def test_from_detail_with_string(self):
        from app.api.dto.response_format import ErrorResponse

        result = ErrorResponse.from_detail("Something went wrong")
        assert result.error["message"] == "Something went wrong"

    def test_from_detail_with_dict(self):
        from app.api.dto.response_format import ErrorResponse

        result = ErrorResponse.from_detail({"code": "NOT_FOUND", "message": "Resource missing"})
        assert result.error["code"] == "NOT_FOUND"


class TestUserLocationOutCoords:
    def test_coords_computed_field_is_populated(self):
        from bson import ObjectId

        from app.api.dto.user_profile import UserLocationOut
        from app.core.bson_utils import PyObjectId

        out = UserLocationOut(id=PyObjectId(ObjectId()), lat=48.85, lon=2.35)
        assert out.coords is not None
        assert isinstance(out.coords, str)
        assert len(out.coords) > 0


class TestRegisterExceptionHandlers:
    @pytest.mark.asyncio
    async def test_http_exception_handler_returns_json(self):
        from fastapi import FastAPI
        from starlette.exceptions import HTTPException as StarletteHTTPException

        from app.core.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)

        # Call the HTTP handler directly
        handlers = app.exception_handlers
        http_handler = handlers.get(StarletteHTTPException)

        request = MagicMock()
        exc = StarletteHTTPException(status_code=404, detail="Not found")
        response = await http_handler(request, exc)

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_validation_exception_handler_returns_422(self):
        from fastapi import FastAPI
        from fastapi.exceptions import RequestValidationError

        from app.core.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)

        handlers = app.exception_handlers
        validation_handler = handlers.get(RequestValidationError)

        request = MagicMock()
        exc = RequestValidationError(
            errors=[{"loc": ["body", "field"], "msg": "required", "type": "missing", "input": None}]
        )
        response = await validation_handler(request, exc)
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_general_exception_handler_returns_500(self):
        from fastapi import FastAPI

        from app.core.exception_handlers import register_exception_handlers

        app = FastAPI()
        register_exception_handlers(app)

        handlers = app.exception_handlers
        general_handler = handlers.get(Exception)

        request = MagicMock()
        exc = ValueError("oops")
        response = await general_handler(request, exc)
        assert response.status_code == 500


# ---------------------------------------------------------------------------
# middleware
# ---------------------------------------------------------------------------


class TestMaxBodySizeMiddleware:
    @pytest.mark.asyncio
    async def test_allows_request_below_limit(self):
        from starlette.responses import PlainTextResponse

        from app.core.middleware import MaxBodySizeMiddleware

        call_next_called = []

        async def call_next(request):
            call_next_called.append(True)
            return PlainTextResponse("ok")

        middleware = MaxBodySizeMiddleware(app=None, max_body_size=1024 * 1024)

        request = MagicMock()
        request.url.path = "/api/test"
        request.headers = {"content-length": "100"}

        await middleware.dispatch(request, call_next)
        assert call_next_called

    @pytest.mark.asyncio
    async def test_blocks_request_exceeding_limit(self):
        from starlette.responses import PlainTextResponse

        from app.core.middleware import MaxBodySizeMiddleware

        async def call_next(request):
            return PlainTextResponse("ok")

        middleware = MaxBodySizeMiddleware(app=None, max_body_size=1024)

        request = MagicMock()
        request.url.path = "/api/upload"
        request.headers = {"content-length": "99999"}

        response = await middleware.dispatch(request, call_next)
        assert response.status_code == 413

    @pytest.mark.asyncio
    async def test_bypasses_excluded_path(self):
        from starlette.responses import PlainTextResponse

        from app.core.middleware import MaxBodySizeMiddleware

        call_next_called = []

        async def call_next(request):
            call_next_called.append(True)
            return PlainTextResponse("ok")

        middleware = MaxBodySizeMiddleware(app=None, max_body_size=1, exclude_paths=["/health"])

        request = MagicMock()
        request.url.path = "/health"
        request.headers = {"content-length": "999999"}

        await middleware.dispatch(request, call_next)
        assert call_next_called

    @pytest.mark.asyncio
    async def test_allows_invalid_content_length(self):
        from starlette.responses import PlainTextResponse

        from app.core.middleware import MaxBodySizeMiddleware

        call_next_called = []

        async def call_next(request):
            call_next_called.append(True)
            return PlainTextResponse("ok")

        middleware = MaxBodySizeMiddleware(app=None, max_body_size=1024)

        request = MagicMock()
        request.url.path = "/api/test"
        request.headers = {"content-length": "not-a-number"}

        await middleware.dispatch(request, call_next)
        assert call_next_called

    @pytest.mark.asyncio
    async def test_allows_request_without_content_length(self):
        from starlette.responses import PlainTextResponse

        from app.core.middleware import MaxBodySizeMiddleware

        call_next_called = []

        async def call_next(request):
            call_next_called.append(True)
            return PlainTextResponse("ok")

        middleware = MaxBodySizeMiddleware(app=None, max_body_size=1024)

        request = MagicMock()
        request.url.path = "/api/test"
        request.headers = {}  # No content-length

        await middleware.dispatch(request, call_next)
        assert call_next_called
