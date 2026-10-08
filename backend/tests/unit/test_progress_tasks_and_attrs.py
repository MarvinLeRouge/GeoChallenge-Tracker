"""Tests for progress.py: _get_tasks_for_uc and attribute-id resolution helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from tests.unit._progress_test_helpers import (
    _TASK_ID,
    _UC_ID,
)


class TestGetTasksForUc:
    @pytest.mark.asyncio
    async def test_returns_sorted_tasks(self):
        from app.services.progress import _get_tasks_for_uc

        tasks = [{"_id": _TASK_ID, "order": 1}]
        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.to_list = AsyncMock(return_value=tasks)
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)

        with patch("app.services.progress.get_collection", return_value=coll):
            result = await _get_tasks_for_uc(_UC_ID)

        assert result == tasks

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_tasks(self):
        from app.services.progress import _get_tasks_for_uc

        cursor = MagicMock()
        cursor.sort = MagicMock(return_value=cursor)
        cursor.to_list = AsyncMock(return_value=[])
        coll = AsyncMock()
        coll.find = MagicMock(return_value=cursor)

        with patch("app.services.progress.get_collection", return_value=coll):
            result = await _get_tasks_for_uc(_UC_ID)

        assert result == []


class TestAttrIdByCacheAttrId:
    @pytest.mark.asyncio
    async def test_returns_objectid_when_found(self):
        from app.services.progress import _attr_id_by_cache_attr_id

        oid = ObjectId()
        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value={"_id": oid})

        with patch("app.services.progress.get_collection", return_value=coll):
            result = await _attr_id_by_cache_attr_id(71)

        assert result == oid

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self):
        from app.services.progress import _attr_id_by_cache_attr_id

        coll = AsyncMock()
        coll.find_one = AsyncMock(return_value=None)

        with patch("app.services.progress.get_collection", return_value=coll):
            result = await _attr_id_by_cache_attr_id(999)

        assert result is None
