"""Shared test helpers for the test_target_evaluator_* split test files."""

from unittest.mock import AsyncMock


def _make_db():
    class MockDB:
        def __init__(self):
            self.users = AsyncMock()
            self.progress = AsyncMock()
            self.user_challenge_tasks = AsyncMock()
            self.caches = AsyncMock()
            self.found_caches = AsyncMock()

    return MockDB()


def _make_cursor(rows):
    cursor = AsyncMock()
    cursor.to_list = AsyncMock(return_value=rows)
    return cursor
