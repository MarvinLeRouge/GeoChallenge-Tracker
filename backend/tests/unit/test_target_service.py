"""Tests for TargetService."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

from app.services.targets.target_service import TargetService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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
    """Configure db.targets for pagination queries."""
    items = items or []
    db.targets.count_documents = AsyncMock(return_value=count)
    cursor = AsyncMock()
    cursor.sort = MagicMock(return_value=cursor)
    cursor.skip = MagicMock(return_value=cursor)
    cursor.limit = MagicMock(return_value=cursor)
    cursor.to_list = AsyncMock(return_value=items)
    db.targets.find = MagicMock(return_value=cursor)
    return db


# ---------------------------------------------------------------------------
# evaluate_targets_for_user_challenge
# ---------------------------------------------------------------------------


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
            return_value=[{"_id": task_id, "expression": {"type": "and"}}]
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


# ---------------------------------------------------------------------------
# list_targets_for_user_challenge
# ---------------------------------------------------------------------------


class TestListTargetsForUserChallenge:
    @pytest.mark.asyncio
    async def test_returns_paginated_result(self):
        user_id = ObjectId()
        uc_id = ObjectId()

        db = _paginated_db(_make_db(), items=[{"_id": ObjectId()}], count=1)
        service = _make_service(db)

        result = await service.list_targets_for_user_challenge(user_id, uc_id)
        assert result["nb_items"] == 1
        assert len(result["items"]) == 1

    @pytest.mark.asyncio
    async def test_sort_ascending(self):
        db = _paginated_db(_make_db())
        service = _make_service(db)

        result = await service.list_targets_for_user_challenge(ObjectId(), ObjectId(), sort="score")
        assert result["page"] == 1


# ---------------------------------------------------------------------------
# list_targets_nearby_for_user_challenge
# ---------------------------------------------------------------------------


class TestListTargetsNearbyForUserChallenge:
    @pytest.mark.asyncio
    async def test_delegates_to_pagination(self):
        db = _paginated_db(_make_db(), count=0)
        service = _make_service(db)

        result = await service.list_targets_nearby_for_user_challenge(
            ObjectId(), ObjectId(), lat=48.85, lon=2.35, radius_km=5
        )
        assert "items" in result


# ---------------------------------------------------------------------------
# list_targets_for_user
# ---------------------------------------------------------------------------


class TestListTargetsForUser:
    @pytest.mark.asyncio
    async def test_without_status_filter(self):
        db = _paginated_db(_make_db(), count=2)
        service = _make_service(db)

        result = await service.list_targets_for_user(ObjectId())
        assert result["nb_items"] == 2

    @pytest.mark.asyncio
    async def test_with_status_filter(self):
        db = _paginated_db(_make_db(), count=1)
        service = _make_service(db)

        result = await service.list_targets_for_user(ObjectId(), status_filter="accepted")
        assert "items" in result


# ---------------------------------------------------------------------------
# list_targets_nearby_for_user
# ---------------------------------------------------------------------------


class TestListTargetsNearbyForUser:
    @pytest.mark.asyncio
    async def test_uses_provided_lat_lon(self):
        db = _paginated_db(_make_db())
        service = _make_service(db)

        result = await service.list_targets_nearby_for_user(ObjectId(), lat=48.85, lon=2.35)
        assert "items" in result

    @pytest.mark.asyncio
    async def test_raises_when_no_location_and_none_lat_lon(self):
        db = _make_db()
        service = _make_service(db)

        with patch(
            "app.services.targets.target_service.get_user_location",
            return_value=None,
        ):
            with pytest.raises(ValueError, match="location"):
                await service.list_targets_nearby_for_user(ObjectId())

    @pytest.mark.asyncio
    async def test_uses_saved_location_when_lat_lon_none(self):
        db = _paginated_db(_make_db())
        service = _make_service(db)

        with patch(
            "app.services.targets.target_service.get_user_location",
            return_value=(48.85, 2.35),
        ):
            result = await service.list_targets_nearby_for_user(ObjectId())

        assert "items" in result


# ---------------------------------------------------------------------------
# delete_targets_for_user_challenge
# ---------------------------------------------------------------------------


class TestDeleteTargetsForUserChallenge:
    @pytest.mark.asyncio
    async def test_deletes_and_returns_count(self):
        db = _make_db()
        db.targets.delete_many = AsyncMock(return_value=MagicMock(deleted_count=3))

        service = _make_service(db)
        result = await service.delete_targets_for_user_challenge(ObjectId(), ObjectId())

        assert result["ok"] is True
        assert result["deleted"] == 3


# ---------------------------------------------------------------------------
# _validate_user_challenge_ownership
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# _score_and_persist_targets — updated vs inserted branches
# ---------------------------------------------------------------------------


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
