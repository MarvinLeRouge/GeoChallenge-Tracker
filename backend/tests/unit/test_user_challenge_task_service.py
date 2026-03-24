"""Tests for UserChallengeTaskService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.user_challenge_tasks.user_challenge_task_service import (
    UserChallengeTaskService,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _AsyncIter:
    def __init__(self, items):
        self._iter = iter(items)

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration as err:
            raise StopAsyncIteration from err

    def sort(self, *args, **kwargs):
        return self


def _make_coll(docs=None):
    coll = AsyncMock()
    cursor = _AsyncIter(docs or [])
    coll.find = MagicMock(return_value=cursor)
    coll.delete_many = AsyncMock()
    coll.insert_many = AsyncMock()
    return coll


def _patch_coll(coll):
    return patch(
        "app.services.user_challenge_tasks.user_challenge_task_service.get_collection",
        return_value=coll,
    )


# Minimal valid leaf expression for testing (RulePlacedYear)
_LEAF_EXPR = {"kind": "placed_year", "year": 2020}


# ---------------------------------------------------------------------------
# list_tasks
# ---------------------------------------------------------------------------


class TestListTasks:
    @pytest.mark.asyncio
    async def test_empty_collection_returns_empty_list(self):
        coll = _make_coll([])
        with _patch_coll(coll):
            service = UserChallengeTaskService()
            result = await service.list_tasks(ObjectId(), ObjectId())
        assert result == []

    @pytest.mark.asyncio
    async def test_valid_expression_returned_as_is(self):
        task_id = ObjectId()
        doc = {
            "_id": task_id,
            "order": 0,
            "title": "My task",
            "expression": _LEAF_EXPR,
            "constraints": {},
        }
        coll = _make_coll([doc])
        with _patch_coll(coll):
            service = UserChallengeTaskService()
            result = await service.list_tasks(ObjectId(), ObjectId())

        assert len(result) == 1
        assert result[0]["id"] == task_id
        assert result[0]["title"] == "My task"

    @pytest.mark.asyncio
    async def test_missing_title_uses_fallback(self):
        doc = {
            "_id": ObjectId(),
            "order": 0,
            "expression": _LEAF_EXPR,
        }
        coll = _make_coll([doc])
        with _patch_coll(coll):
            service = UserChallengeTaskService()
            result = await service.list_tasks(ObjectId(), ObjectId())

        assert result[0]["title"] == "Untitled task"

    @pytest.mark.asyncio
    async def test_invalid_expression_triggers_legacy_fixup(self):
        """Expression that fails initial validation → normalizer.legacy_fixup_expression called."""
        doc = {
            "_id": ObjectId(),
            "order": 0,
            "title": "Task",
            "expression": {"op": "leaf", "field": "difficulty", "comparator": "eq", "value": 1.0},
        }
        coll = _make_coll([doc])

        service = UserChallengeTaskService()
        # Make the first TypeAdapter.validate_python raise, then succeed after fixup
        service.normalizer.legacy_fixup_expression = MagicMock(return_value=_LEAF_EXPR)

        call_count = [0]

        with _patch_coll(coll):
            # Patch TypeAdapter to fail on first call, succeed on second
            with patch(
                "app.services.user_challenge_tasks.user_challenge_task_service.TypeAdapter"
            ) as mock_ta_class:
                mock_ta = MagicMock()
                mock_ta_class.return_value = mock_ta

                first_model = MagicMock()
                first_model.model_dump = MagicMock(return_value=_LEAF_EXPR)

                def validate_side_effect(val):
                    call_count[0] += 1
                    if call_count[0] == 1:
                        raise ValueError("bad expression")
                    return first_model

                mock_ta.validate_python = MagicMock(side_effect=validate_side_effect)

                result = await service.list_tasks(ObjectId(), ObjectId())

        assert len(result) == 1


# ---------------------------------------------------------------------------
# validate_only
# ---------------------------------------------------------------------------


class TestValidateOnly:
    def test_delegates_to_validator(self):
        service = UserChallengeTaskService()
        service.validator = MagicMock()
        service.validator.validate_only_format_response = MagicMock(
            return_value={"ok": True, "errors": []}
        )

        result = service.validate_only(ObjectId(), ObjectId(), [])
        assert result == {"ok": True, "errors": []}
        service.validator.validate_only_format_response.assert_called_once()

    def test_compile_expression_to_cache_match_delegates(self):
        service = UserChallengeTaskService()
        service.compiler = MagicMock()
        service.compiler.compile_expression_to_cache_match = MagicMock(
            return_value={"difficulty": 1}
        )

        expr = MagicMock()
        result = service.compile_expression_to_cache_match(expr)
        assert result == {"difficulty": 1}

    def test_validate_task_expression_delegates(self):
        service = UserChallengeTaskService()
        service.validator = MagicMock()
        service.validator.validate_task_expression = MagicMock(return_value=[])

        expr = MagicMock()
        result = service.validate_task_expression(expr)
        assert result == []


# ---------------------------------------------------------------------------
# put_tasks
# ---------------------------------------------------------------------------


class TestPutTasks:
    @pytest.mark.asyncio
    async def test_empty_payload_clears_and_returns_empty(self):
        coll = _make_coll([])
        # find for readback returns empty
        coll.find = MagicMock(return_value=_AsyncIter([]))

        with _patch_coll(coll):
            service = UserChallengeTaskService()
            service.validator.validate_tasks_payload = MagicMock()

            result = await service.put_tasks(ObjectId(), ObjectId(), [])

        coll.delete_many.assert_called_once()
        assert result == []

    @pytest.mark.asyncio
    async def test_inserts_tasks_and_reads_back(self):
        inserted_id = ObjectId()
        uc_id = ObjectId()

        inserted_doc = {
            "_id": inserted_id,
            "order": 0,
            "title": "My Task",
            "expression": _LEAF_EXPR,
            "constraints": {},
            "status": "todo",
            "metrics": {},
            "progress": None,
            "last_evaluated_at": None,
            "updated_at": None,
            "created_at": None,
        }

        # First call (delete), then insert_many, then find for readback
        coll = AsyncMock()
        coll.delete_many = AsyncMock()
        coll.insert_many = AsyncMock()
        readback_iter = _AsyncIter([inserted_doc])
        coll.find = MagicMock(return_value=readback_iter)

        task_item = {
            "id": str(inserted_id),
            "order": 0,
            "title": "My Task",
            "expression": _LEAF_EXPR,
            "constraints": {},
        }

        with _patch_coll(coll):
            service = UserChallengeTaskService()
            service.validator.validate_tasks_payload = MagicMock()
            # normalizer.normalize_code_to_id returns the model unchanged
            from pydantic import TypeAdapter

            from app.domain.models.challenge_ast import TaskExpression

            expr_model = TypeAdapter(TaskExpression).validate_python(_LEAF_EXPR)
            service.normalizer.normalize_code_to_id = MagicMock(return_value=expr_model)

            result = await service.put_tasks(ObjectId(), uc_id, [task_item])

        coll.insert_many.assert_called_once()
        assert len(result) == 1
        assert result[0]["title"] == "My Task"

    @pytest.mark.asyncio
    async def test_generates_title_when_missing(self):
        """Item without title → 'Task #1'."""
        inserted_id = ObjectId()
        uc_id = ObjectId()

        inserted_doc = {
            "_id": inserted_id,
            "order": 0,
            "title": "Task #1",
            "expression": _LEAF_EXPR,
            "constraints": {},
            "status": "todo",
            "metrics": {},
            "progress": None,
            "last_evaluated_at": None,
            "updated_at": None,
            "created_at": None,
        }

        coll = AsyncMock()
        coll.delete_many = AsyncMock()
        coll.insert_many = AsyncMock()
        coll.find = MagicMock(return_value=_AsyncIter([inserted_doc]))

        task_item = {
            "order": 0,
            "expression": _LEAF_EXPR,
        }

        with _patch_coll(coll):
            service = UserChallengeTaskService()
            service.validator.validate_tasks_payload = MagicMock()
            from pydantic import TypeAdapter

            from app.domain.models.challenge_ast import TaskExpression

            expr_model = TypeAdapter(TaskExpression).validate_python(_LEAF_EXPR)
            service.normalizer.normalize_code_to_id = MagicMock(return_value=expr_model)

            await service.put_tasks(ObjectId(), uc_id, [task_item])

        # Verify title in inserted doc
        inserted_docs = coll.insert_many.call_args[0][0]
        assert inserted_docs[0]["title"] == "Task #1"
