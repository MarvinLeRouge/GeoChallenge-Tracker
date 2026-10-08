"""Shared test helpers for the test_target_service_* split test files."""

from unittest.mock import AsyncMock, MagicMock

from app.services.targets.target_service import TargetService


def _make_db():
    class MockDB:
        def __init__(self):
            self.user_challenges = AsyncMock()
            self.targets = AsyncMock()
            self.users = AsyncMock()
            self.progress = AsyncMock()
            self.user_challenge_tasks = AsyncMock()
            self.caches = AsyncMock()

    return MockDB()


def _make_service(db=None):
    db = db or _make_db()
    return TargetService(db)


def _paginated_db(db, items=None, count=0):
    """Configure db.targets for find/count_documents pagination queries."""
    items = items or []
    db.targets.count_documents = AsyncMock(return_value=count)
    cursor = AsyncMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=items)
    db.targets.find = MagicMock(return_value=cursor)
    return db


def _geo_db(db, items=None, count=0):
    """Configure db.targets for $geoNear aggregate queries.

    The method calls aggregate twice in sequence:
    - first call: count pipeline → [{"total": count}]
    - second call: data pipeline → items
    """
    items = items or []

    count_cursor = AsyncMock()
    count_cursor.to_list = AsyncMock(return_value=[{"total": count}] if count else [])

    data_cursor = AsyncMock()
    data_cursor.to_list = AsyncMock(return_value=items)

    db.targets.aggregate = MagicMock(side_effect=[count_cursor, data_cursor])
    return db


def _uc_cursor(db, uc_docs=None):
    """Configure db.user_challenges.find for the two-step join in status filters."""
    uc_docs = uc_docs or []
    cursor = AsyncMock()
    cursor.to_list = AsyncMock(return_value=uc_docs)
    db.user_challenges.find = MagicMock(return_value=cursor)
    return db
