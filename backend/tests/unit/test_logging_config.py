"""Tests for Logging configuration (unit tests - no DB required)."""

from unittest.mock import patch

from app.core.logging_config import (
    DataLogger,
    cleanup_old_logs,
    get_loggers,
    setup_logging,
)


class TestSetupLogging:
    """Test setup_logging function."""

    def test_setup_logging_creates_loggers(self):
        """Test that setup_logging creates three loggers."""
        generic_logger, error_logger, data_logger = setup_logging()

        assert generic_logger is not None
        assert error_logger is not None
        assert data_logger is not None

    def test_setup_logging_generic_logger_name(self):
        """Test generic logger has correct name."""
        generic_logger, _, _ = setup_logging()

        assert generic_logger.name == "geocaching.generic"

    def test_setup_logging_error_logger_name(self):
        """Test error logger has correct name."""
        _, error_logger, _ = setup_logging()

        assert error_logger.name == "geocaching.errors"

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test that setup_logging creates logs directory."""
        test_logs_dir = tmp_path / "test_logs"

        with patch("app.core.logging_config.Path", return_value=test_logs_dir):
            setup_logging()

        assert test_logs_dir.exists()


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
        # Create a recent log file
        recent_file = tmp_path / "2026-02-27-generic.log"
        recent_file.write_text("test content")

        cleanup_old_logs(tmp_path, retention_days=30)

        # Recent file should still exist
        assert recent_file.exists()
