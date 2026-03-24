"""
Unit-test conftest.

Patches logging.handlers.TimedRotatingFileHandler for the entire test session
so that modules that create file-based log handlers at import time (e.g.
gpx_import_service.py) do not fail when the log file is not writable.
"""

from __future__ import annotations

import logging
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(scope="session", autouse=True)
def mock_rotating_log_handler():
    """Replace TimedRotatingFileHandler with a no-op mock for all unit tests."""
    mock_handler = MagicMock(spec=logging.Handler)
    mock_handler.level = logging.NOTSET
    mock_handler.filters = []
    with patch("logging.handlers.TimedRotatingFileHandler", return_value=mock_handler):
        yield
