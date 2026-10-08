"""Tests for TargetService: evaluate_targets_for_user_challenge, ownership validation, scoring/persistence, and deletion."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from tests.unit._target_service_test_helpers import (
    _make_db,
    _make_service,
)


class TestEvaluateTargetsForUserChallenge:
    @pytest.mark.asyncio
    async def test_raises_permission_error_when_not_owner(self):
        db = _make_db()
        db.user_challenges.find_one = AsyncMock(return_value=None)

        service = _make_service(db)
        with pytest.raises(PermissionError):
            await service.evaluate_targets_for_user_challenge(ObjectId(), ObjectId())

    @pytest.mark.asyncio
    async def test_skips_when_enough_targets_and_not_forcing(self):
        db = _make_db()
        db.user_challenges.find_one = AsyncMock(return_value={"_id": ObjectId()})
        # count_documents is called for targets (first call)
        db.targets.count_documents = AsyncMock(return_value=9999)

        service = _make_service(db)
        result = await service.evaluate_targets_for_user_challenge(
            ObjectId(), ObjectId(), limit_per_task=200, hard_limit_total=2000
        )

        assert result["skipped"] is True
        assert result["ok"] is True

    @pytest.mark.asyncio
    async def test_forces_evaluation_even_with_enough_targets(self):
        db = _make_db()
        db.user_challenges.find_one = AsyncMock(return_value={"_id": ObjectId()})
        db.targets.count_documents = AsyncMock(return_value=0)
        db.targets.update_one = AsyncMock(
            return_value=MagicMock(upserted_id=None, modified_count=0)
        )
        db.users.find_one = AsyncMock(return_value={"username": "alice"})

        # tasks cursor
        tasks_cursor = AsyncMock()
        tasks_cursor.to_list = AsyncMock(return_value=[])
        db.user_challenge_tasks.find = MagicMock(return_value=tasks_cursor)

        # progress
        db.progress.find_one = AsyncMock(return_value=None)

        service = _make_service(db)
        result = await service.evaluate_targets_for_user_challenge(
            ObjectId(), ObjectId(), force=True
        )

        assert result["ok"] is True
        assert "skipped" not in result

    @pytest.mark.asyncio
    async def test_scores_and_persists_candidates(self):
        user_id = ObjectId()
        uc_id = ObjectId()
        cache_id = ObjectId()

        db = _make_db()
        db.user_challenges.find_one = AsyncMock(return_value={"_id": uc_id})
        db.targets.count_documents = AsyncMock(return_value=0)
        db.users.find_one = AsyncMock(return_value={"username": "alice"})
        db.progress.find_one = AsyncMock(return_value=None)

        task_id = ObjectId()
        tasks_cursor = AsyncMock()
        tasks_cursor.to_list = AsyncMock(
            return_value=[{"_id": task_id, "expression": {"kind": "and"}}]
        )
        db.user_challenge_tasks.find = MagicMock(return_value=tasks_cursor)

        # Caches aggregate returns one candidate
        cache_row = {"_id": cache_id, "title": "Cache A"}
        agg_cursor = AsyncMock()
        agg_cursor.to_list = AsyncMock(return_value=[cache_row])
        db.caches.aggregate = MagicMock(return_value=agg_cursor)

        # Target upsert
        upsert_result = MagicMock()
        upsert_result.upserted_id = ObjectId()
        upsert_result.modified_count = 0
        db.targets.update_one = AsyncMock(return_value=upsert_result)

        service = _make_service(db)
        result = await service.evaluate_targets_for_user_challenge(user_id, uc_id, force=True)

        assert result["ok"] is True
        assert result["inserted"] == 1


class TestDeleteTargetsForUserChallenge:
    @pytest.mark.asyncio
    async def test_deletes_and_returns_count(self):
        db = _make_db()
        db.targets.delete_many = AsyncMock(return_value=MagicMock(deleted_count=3))

        service = _make_service(db)
        result = await service.delete_targets_for_user_challenge(ObjectId(), ObjectId())

        assert result["ok"] is True
        assert result["deleted"] == 3


class TestValidateUserChallengeOwnership:
    @pytest.mark.asyncio
    async def test_raises_if_uc_not_found(self):
        db = _make_db()
        db.user_challenges.find_one = AsyncMock(return_value=None)

        service = _make_service(db)
        with pytest.raises(PermissionError):
            await service._validate_user_challenge_ownership(ObjectId(), ObjectId())

    @pytest.mark.asyncio
    async def test_passes_silently_when_owner(self):
        db = _make_db()
        db.user_challenges.find_one = AsyncMock(return_value={"_id": ObjectId()})

        service = _make_service(db)
        await service._validate_user_challenge_ownership(ObjectId(), ObjectId())


class TestScoreAndPersistTargets:
    @pytest.mark.asyncio
    async def test_tracks_updated_count(self):
        user_id = ObjectId()
        uc_id = ObjectId()
        cache_id = ObjectId()

        db = _make_db()
        db.targets.count_documents = AsyncMock(return_value=1)

        # update_one returns modified_count=1 (update, not insert)
        update_result = MagicMock()
        update_result.upserted_id = None
        update_result.modified_count = 1
        db.targets.update_one = AsyncMock(return_value=update_result)

        service = _make_service(db)

        candidates = {
            cache_id: {
                "cache": {"_id": cache_id},
                "matched_tasks": [],
            }
        }

        result = await service._score_and_persist_targets(
            candidates=candidates,
            user_id=user_id,
            uc_id=uc_id,
            tasks=[],
            progress_map={},
            geo_ctx=None,
            evaluated_at=dt.datetime.utcnow(),
        )

        assert result["updated"] == 1
        assert result["inserted"] == 0

    @pytest.mark.asyncio
    async def test_adds_distance_m_when_available(self):
        user_id = ObjectId()
        uc_id = ObjectId()
        cache_id = ObjectId()

        db = _make_db()
        db.targets.count_documents = AsyncMock(return_value=1)

        update_result = MagicMock()
        update_result.upserted_id = ObjectId()
        update_result.modified_count = 0
        db.targets.update_one = AsyncMock(return_value=update_result)

        service = _make_service(db)

        candidates = {
            cache_id: {
                "cache": {"_id": cache_id, "distance_m": 1500.0},
                "matched_tasks": [],
            }
        }

        await service._score_and_persist_targets(
            candidates=candidates,
            user_id=user_id,
            uc_id=uc_id,
            tasks=[],
            progress_map={},
            geo_ctx={"radius_km": 5},
            evaluated_at=dt.datetime.utcnow(),
        )

        call_update = db.targets.update_one.call_args[0][1]["$set"]
        assert "distance_m" in call_update
        assert call_update["distance_m"] == 1500.0

    @pytest.mark.asyncio
    async def test_persists_loc_field_not_cache_loc(self):
        """Regression: 2dsphere index is on 'loc', not 'cache_loc'."""
        user_id = ObjectId()
        uc_id = ObjectId()
        cache_id = ObjectId()
        geo_point = {"type": "Point", "coordinates": [2.35, 48.85]}

        db = _make_db()
        db.targets.count_documents = AsyncMock(return_value=0)
        update_result = MagicMock()
        update_result.upserted_id = ObjectId()
        update_result.modified_count = 0
        db.targets.update_one = AsyncMock(return_value=update_result)

        service = _make_service(db)

        candidates = {
            cache_id: {
                "cache": {"_id": cache_id, "loc": geo_point},
                "matched_tasks": [],
            }
        }

        await service._score_and_persist_targets(
            candidates=candidates,
            user_id=user_id,
            uc_id=uc_id,
            tasks=[],
            progress_map={},
            geo_ctx=None,
            evaluated_at=dt.datetime.utcnow(),
        )

        doc_set = db.targets.update_one.call_args[0][1]["$set"]
        assert "loc" in doc_set
        assert "cache_loc" not in doc_set
        assert doc_set["loc"] == geo_point
