"""Shared test helpers for the test_progress_* split test files."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from bson import ObjectId

_UID = ObjectId()
_UC_ID = ObjectId()
_TASK_ID = ObjectId()
_TASK_ID2 = ObjectId()


def _mock_collection(**kwargs) -> AsyncMock:
    """Build an AsyncMock that mimics a Motor collection."""
    coll = AsyncMock()
    for k, v in kwargs.items():
        setattr(coll, k, v)
    return coll


def _async_return(val):
    """Return an AsyncMock that resolves to val."""
    m = AsyncMock(return_value=val)
    return m


def _make_task(
    task_id=None,
    status="todo",
    min_count=10,
    expression=None,
    order=1,
    title="Task",
):
    return {
        "_id": task_id or _TASK_ID,
        "status": status,
        "constraints": {"min_count": min_count},
        "expression": expression or {"kind": "placed_year", "year": 2020},
        "order": order,
        "title": title,
        "updated_at": None,
        "created_at": None,
        "start_found_at": None,
        "completed_at": None,
    }


def _patch_evaluate_deps(
    *,
    tasks,
    uc_status=None,
    uc_computed_status=None,
    compile_result=None,
    current_count=5,
    aggregate_total=None,
    first_found_date=None,
    nth_found_date=None,
    last_snapshot=None,
):
    """Build a context-manager stack that patches all evaluate_progress dependencies."""
    if compile_result is None:
        compile_result = ("and:test", {}, True, [], None)

    # Mock collections used directly inside evaluate_progress
    uc_coll = AsyncMock()
    uc_coll.find_one = AsyncMock(
        return_value={"status": uc_status, "computed_status": uc_computed_status}
    )
    uc_coll.update_one = AsyncMock(return_value=None)

    tasks_coll = AsyncMock()
    tasks_coll.update_one = AsyncMock(return_value=None)

    progress_coll = AsyncMock()
    if last_snapshot:
        progress_coll.find_one = AsyncMock(return_value=last_snapshot)
    else:
        progress_coll.find_one = AsyncMock(return_value=None)
    progress_coll.insert_one = AsyncMock(return_value=None)

    async def _get_coll(name):
        if name == "user_challenges":
            return uc_coll
        if name == "user_challenge_tasks":
            return tasks_coll
        if name == "progress":
            return progress_coll
        return AsyncMock()

    patches = [
        patch(
            "app.services.progress._ensure_uc_owned",
            new=AsyncMock(return_value={"_id": _UC_ID}),
        ),
        patch(
            "app.services.progress._get_tasks_for_uc",
            new=AsyncMock(return_value=tasks),
        ),
        patch("app.services.progress.get_collection", side_effect=_get_coll),
        patch("app.services.progress.compile_and_only", return_value=compile_result),
        patch(
            "app.services.progress_aggregates._count_found_caches_matching",
            new=AsyncMock(return_value=current_count),
        ),
        patch(
            "app.services.progress_aggregates._aggregate_total",
            new=AsyncMock(return_value=aggregate_total or 0),
        ),
        patch(
            "app.services.progress_aggregates._first_found_date",
            new=AsyncMock(return_value=first_found_date),
        ),
        patch(
            "app.services.progress_aggregates._nth_found_date",
            new=AsyncMock(return_value=nth_found_date),
        ),
    ]
    return patches


def _make_cursor(items: list) -> MagicMock:
    """Build a synchronous-chain mock that behaves like a Motor cursor for find()."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=items)
    return cursor


def _make_async_iter(items: list) -> MagicMock:
    """Build a mock that supports 'async for' iteration (for progress.find())."""
    cursor = MagicMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=items)

    # support async for: __aiter__ and __anext__
    async def _aiter(self):
        for item in items:
            yield item

    cursor.__aiter__ = lambda self: _aiter(self).__aiter__()
    return cursor


class _apply_patches:
    """Context manager that applies a list of patch objects."""

    def __init__(self, patches):
        self._patches = patches
        self._mocks = []

    def __enter__(self):
        for p in self._patches:
            self._mocks.append(p.start())
        return self._mocks

    def __exit__(self, *args):
        for p in self._patches:
            p.stop()


def _mock_aggregate_coll(rows):
    cursor = AsyncMock()
    cursor.to_list = AsyncMock(return_value=rows)
    coll = AsyncMock()
    coll.aggregate = MagicMock(return_value=cursor)
    return coll
