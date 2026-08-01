"""Tests for Logging configuration (unit tests - no DB required)."""

import json
import logging
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from app.core.logging_config import (
    CustomJSONEncoder,
    DataLogger,
    cleanup_old_logs,
    extract_user_data,
    get_loggers,
    get_security_logger,
    setup_logging,
)

_STREAM_HANDLER_PATCH = patch(
    "logging.handlers.TimedRotatingFileHandler",
    side_effect=lambda filename, **kwargs: logging.StreamHandler(),
)


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_creates_loggers(self):
        """Test that setup_logging creates three loggers."""
        with _STREAM_HANDLER_PATCH:
            generic_logger, error_logger, data_logger = setup_logging()

        assert generic_logger is not None
        assert error_logger is not None
        assert data_logger is not None

    def test_setup_logging_generic_logger_name(self):
        """Test generic logger has correct name."""
        with _STREAM_HANDLER_PATCH:
            generic_logger, _, _ = setup_logging()

        assert generic_logger.name == "geocaching.generic"

    def test_setup_logging_error_logger_name(self):
        """Test error logger has correct name."""
        with _STREAM_HANDLER_PATCH:
            _, error_logger, _ = setup_logging()

        assert error_logger.name == "geocaching.errors"

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test that setup_logging creates logs directory."""
        with _STREAM_HANDLER_PATCH, patch("app.core.logging_config.Path", return_value=tmp_path):
            setup_logging()

        assert tmp_path.exists()


class TestGetLoggers:
    """Test get_loggers singleton function."""

    def test_get_loggers_returns_tuple(self):
        """Test get_loggers returns a tuple of three elements."""
        # Reset the singleton first
        from app.core import logging_config

        logging_config._loggers = None

        result = get_loggers()

        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_get_loggers_returns_same_instance(self):
        """Test get_loggers returns same instance (singleton)."""
        from app.core import logging_config

        logging_config._loggers = None

        result1 = get_loggers()
        result2 = get_loggers()

        assert result1 is result2


class TestGetSecurityLogger:
    """Test get_security_logger singleton function."""

    def test_returns_a_logger_with_the_expected_name(self):
        from app.core import logging_config

        logging_config._security_logger = None

        with _STREAM_HANDLER_PATCH:
            logger = get_security_logger()

        assert logger.name == "geocaching.security"

    def test_returns_same_instance(self):
        from app.core import logging_config

        logging_config._security_logger = None

        with _STREAM_HANDLER_PATCH:
            logger1 = get_security_logger()
            logger2 = get_security_logger()

        assert logger1 is logger2

    def test_independent_from_get_loggers_singleton(self):
        """get_security_logger() must not be affected by resetting the other singleton."""
        from app.core import logging_config

        logging_config._loggers = None
        logging_config._security_logger = None

        with _STREAM_HANDLER_PATCH:
            security_logger = get_security_logger()
            generic_logger, _, _ = get_loggers()

        assert security_logger.name != generic_logger.name


class TestDataLogger:
    """Test DataLogger class."""

    def test_data_logger_initialization(self, tmp_path):
        """Test DataLogger initializes with logs directory."""
        data_logger = DataLogger(str(tmp_path))

        assert data_logger.logs_dir == tmp_path

    def test_data_logger_creates_directory(self, tmp_path):
        """Test DataLogger creates directory if not exists."""
        new_dir = tmp_path / "new_logs"
        data_logger = DataLogger(str(new_dir))

        # Directory should be created during log_data call
        data_logger.log_data("test", {"key": "value"})

        assert new_dir.exists()

    def test_data_logger_log_data(self, tmp_path):
        """Test DataLogger.log_data creates JSON file."""
        data_logger = DataLogger(str(tmp_path))

        data_logger.log_data("test_context", {"data": "test"})

        # Check that a JSON file was created
        json_files = list(tmp_path.glob("*-data.json"))
        assert len(json_files) > 0


class TestCleanupOldLogs:
    """Test cleanup_old_logs function."""

    def test_cleanup_old_logs_with_empty_directory(self, tmp_path):
        """Test cleanup_old_logs does nothing with empty directory."""
        cleanup_old_logs(tmp_path, retention_days=30)

        # Should not raise any error
        assert tmp_path.exists()

    def test_cleanup_old_logs_retains_recent(self, tmp_path):
        """Test cleanup_old_logs retains recent log files."""
        # Create a log file genuinely within the retention window (was previously
        # hardcoded to a fixed calendar date, which only "passed" because the
        # function under test never actually deleted anything - see below).
        recent_date = (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        recent_file = tmp_path / f"{recent_date}-generic.log"
        recent_file.write_text("test content")

        cleanup_old_logs(tmp_path, retention_days=30)

        # Recent file should still exist
        assert recent_file.exists()

    def test_cleanup_old_logs_runs_without_error_with_old_files(self, tmp_path):
        """cleanup_old_logs actually removes old files, and doesn't raise."""
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"{old_date}-data.json"
        old_file.write_text("[]")

        cleanup_old_logs(tmp_path, retention_days=30)

        assert not old_file.exists()

    def test_cleanup_old_logs_removes_old_security_log(self, tmp_path):
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"{old_date}-security.log"
        old_file.write_text("old security log")

        cleanup_old_logs(tmp_path, retention_days=30)

        assert not old_file.exists()

    def test_cleanup_old_logs_removes_timed_rotating_suffix_form(self, tmp_path):
        """TimedRotatingFileHandler rotates as `<name>.log.<date>` (suffix), not
        `<date>-<name>.log` (prefix) - both forms must be handled."""
        old_date = (datetime.now() - timedelta(days=40)).strftime("%Y-%m-%d")
        old_file = tmp_path / f"security.log.{old_date}"
        old_file.write_text("old security log")

        cleanup_old_logs(tmp_path, retention_days=30)

        assert not old_file.exists()


# ---------------------------------------------------------------------------
# CustomJSONEncoder — missing branches
# ---------------------------------------------------------------------------


class TestCustomJSONEncoder:
    def test_encodes_objectid_as_string(self):
        oid = ObjectId()
        result = json.dumps({"id": oid}, cls=CustomJSONEncoder)
        assert str(oid) in result

    def test_encodes_datetime_as_isoformat(self):
        dt = datetime(2024, 6, 1, 12, 0, 0)
        result = json.dumps({"ts": dt}, cls=CustomJSONEncoder)
        assert "2024-06-01" in result

    def test_raises_for_unknown_type(self):
        with pytest.raises(TypeError):
            json.dumps({"obj": object()}, cls=CustomJSONEncoder)


# ---------------------------------------------------------------------------
# DataLogger — append path (lines 50-67)
# ---------------------------------------------------------------------------


class TestDataLoggerAppend:
    def test_appends_to_existing_json_file(self, tmp_path):
        logger = DataLogger(logs_dir=str(tmp_path))
        logger.log_data("context1", {"x": 1})
        logger.log_data("context2", {"x": 2})

        today = datetime.now().strftime("%Y-%m-%d")
        json_file = tmp_path / f"{today}-data.json"
        content = json.loads(json_file.read_text())

        assert len(content) == 2
        assert content[1]["calling_context"] == "context2"

    def test_appends_when_file_ends_with_brace_not_bracket(self, tmp_path):
        """Covers the elif content.endswith('}') branch."""
        logger = DataLogger(logs_dir=str(tmp_path))
        today = datetime.now().strftime("%Y-%m-%d")
        json_file = tmp_path / f"{today}-data.json"
        # Write a file that ends with } (not ]) to trigger the elif branch
        json_file.write_text('{"calling_context": "x", "data": {}}')
        logger.log_data("appended", {"y": 2})
        raw = json_file.read_text()
        assert "appended" in raw


# ---------------------------------------------------------------------------
# extract_user_data — missing branches
# ---------------------------------------------------------------------------


class TestExtractUserData:
    def test_returns_empty_dict_with_no_args(self):
        result = extract_user_data()
        assert result == {}

    def test_includes_user_id_when_provided(self):
        oid = ObjectId()
        result = extract_user_data(user_id=oid)
        assert result["user_id"] == oid

    def test_includes_ip_from_request_client(self):
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers.get = MagicMock(return_value=None)

        result = extract_user_data(request=request)
        assert result["ip"] == "127.0.0.1"

    def test_includes_user_agent_when_present(self):
        request = MagicMock()
        request.client = None
        request.headers.get = MagicMock(return_value="Mozilla/5.0")

        result = extract_user_data(request=request)
        assert result.get("user_agent") == "Mozilla/5.0"

    def test_omits_ip_when_client_is_none(self):
        request = MagicMock()
        request.client = None
        request.headers.get = MagicMock(return_value=None)

        result = extract_user_data(request=request)
        assert "ip" not in result
