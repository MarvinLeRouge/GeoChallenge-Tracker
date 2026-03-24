"""Tests for UserChallengeService."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.user_challenges.user_challenge_service import UserChallengeService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_db():
    class MockDB:
        def __init__(self):
            self.user_challenges = AsyncMock()

    return MockDB()


def _make_service(db=None):
    db = db or _make_db()
    return UserChallengeService(db)


# ---------------------------------------------------------------------------
# Delegation methods
# ---------------------------------------------------------------------------


class TestDelegationMethods:
    @pytest.mark.asyncio
    async def test_sync_user_challenges_delegates(self):
        service = _make_service()
        service.sync_service = AsyncMock()
        service.sync_service.sync_user_challenges = AsyncMock(return_value={"created": 1})

        result = await service.sync_user_challenges(ObjectId())
        assert result == {"created": 1}

    @pytest.mark.asyncio
    async def test_list_user_challenges_delegates(self):
        service = _make_service()
        service.query_service = AsyncMock()
        service.query_service.list_user_challenges = AsyncMock(return_value={"items": []})

        result = await service.list_user_challenges(ObjectId())
        assert result == {"items": []}

    @pytest.mark.asyncio
    async def test_get_user_challenge_detail_delegates(self):
        service = _make_service()
        service.query_service = AsyncMock()
        service.query_service.get_user_challenge_detail = AsyncMock(return_value={"id": "x"})

        result = await service.get_user_challenge_detail(ObjectId(), ObjectId())
        assert result == {"id": "x"}


# ---------------------------------------------------------------------------
# patch_user_challenge
# ---------------------------------------------------------------------------


class TestPatchUserChallenge:
    @pytest.mark.asyncio
    async def test_returns_false_when_validation_fails(self):
        service = _make_service()
        service.validator = AsyncMock()
        service.validator.validate_patch_operation = AsyncMock(
            return_value=(False, "Invalid status", None)
        )

        ok, err, uc = await service.patch_user_challenge(ObjectId(), ObjectId(), {})
        assert ok is False
        assert err == "Invalid status"
        assert uc is None

    @pytest.mark.asyncio
    async def test_returns_false_when_apply_fails(self):
        service = _make_service()
        service.validator = AsyncMock()
        service.validator.validate_patch_operation = AsyncMock(
            return_value=(True, None, {"status": "accepted"})
        )
        service.validator.get_patch_dependencies = AsyncMock(
            return_value={"current_uc": {}, "computed_status": None, "can_auto_complete": False}
        )

        db = _make_db()
        db.user_challenges.update_one = AsyncMock(return_value=MagicMock(modified_count=0))
        service.db = db

        ok, err, uc = await service.patch_user_challenge(ObjectId(), ObjectId(), {})
        assert ok is False
        assert err == "Failed to update UserChallenge"

    @pytest.mark.asyncio
    async def test_returns_updated_uc_on_success(self):
        service = _make_service()
        service.validator = AsyncMock()
        service.validator.validate_patch_operation = AsyncMock(
            return_value=(True, None, {"status": "accepted"})
        )
        service.validator.get_patch_dependencies = AsyncMock(
            return_value={"current_uc": {}, "computed_status": None, "can_auto_complete": False}
        )

        db = _make_db()
        db.user_challenges.update_one = AsyncMock(return_value=MagicMock(modified_count=1))
        service.db = db

        service.query_service = AsyncMock()
        service.query_service.get_user_challenge_detail = AsyncMock(return_value={"id": "updated"})

        ok, err, uc = await service.patch_user_challenge(ObjectId(), ObjectId(), {})
        assert ok is True
        assert err is None
        assert uc == {"id": "updated"}


# ---------------------------------------------------------------------------
# bulk_update_status
# ---------------------------------------------------------------------------


class TestBulkUpdateStatus:
    @pytest.mark.asyncio
    async def test_returns_error_when_validation_fails(self):
        service = _make_service()
        service.validator = AsyncMock()
        service.validator.validate_bulk_operation = AsyncMock(
            return_value=(False, "Bad request", None)
        )

        result = await service.bulk_update_status(ObjectId(), [], "accepted")
        assert result["success"] is False
        assert result["error"] == "Bad request"

    @pytest.mark.asyncio
    async def test_bulk_update_accepted_status(self):
        user_id = ObjectId()
        uc_ids = [ObjectId()]

        db = _make_db()
        db.user_challenges.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

        service = _make_service(db)
        service.validator = AsyncMock()
        service.validator.validate_bulk_operation = AsyncMock(return_value=(True, None, uc_ids))

        result = await service.bulk_update_status(user_id, uc_ids, "accepted")
        assert result["success"] is True
        assert result["updated"] == 1

    @pytest.mark.asyncio
    async def test_bulk_update_completed_adds_snapshot(self):
        user_id = ObjectId()
        uc_ids = [ObjectId()]

        db = _make_db()
        db.user_challenges.update_many = AsyncMock(return_value=MagicMock(modified_count=1))

        service = _make_service(db)
        service.validator = AsyncMock()
        service.validator.validate_bulk_operation = AsyncMock(return_value=(True, None, uc_ids))

        result = await service.bulk_update_status(user_id, uc_ids, "completed")
        assert result["success"] is True

        call_args = db.user_challenges.update_many.call_args[0]
        update_doc = call_args[1]["$set"]
        assert update_doc["manual_override"] is True
        assert "progress" in update_doc


# ---------------------------------------------------------------------------
# reset_user_challenge
# ---------------------------------------------------------------------------


class TestResetUserChallenge:
    @pytest.mark.asyncio
    async def test_returns_false_when_not_owner(self):
        service = _make_service()
        service.validator = AsyncMock()
        service.validator.validate_ownership = AsyncMock(return_value=False)

        ok, err = await service.reset_user_challenge(ObjectId(), ObjectId())
        assert ok is False
        assert "not found" in err

    @pytest.mark.asyncio
    async def test_returns_true_on_success(self):
        service = _make_service()
        service.validator = AsyncMock()
        service.validator.validate_ownership = AsyncMock(return_value=True)
        service.sync_service = AsyncMock()
        service.sync_service.reset_user_challenge_status = AsyncMock(return_value=True)

        ok, err = await service.reset_user_challenge(ObjectId(), ObjectId())
        assert ok is True
        assert err is None

    @pytest.mark.asyncio
    async def test_returns_false_on_sync_failure(self):
        service = _make_service()
        service.validator = AsyncMock()
        service.validator.validate_ownership = AsyncMock(return_value=True)
        service.sync_service = AsyncMock()
        service.sync_service.reset_user_challenge_status = AsyncMock(return_value=False)

        ok, err = await service.reset_user_challenge(ObjectId(), ObjectId())
        assert ok is False


# ---------------------------------------------------------------------------
# _prepare_patch_update
# ---------------------------------------------------------------------------


class TestPreparePatchUpdate:
    def test_copies_basic_fields(self):
        service = _make_service()
        validated = {"status": "accepted", "notes": "my note"}
        result = service._prepare_patch_update(validated, {}, {"computed_status": None})

        assert result["status"] == "accepted"
        assert result["notes"] == "my note"

    def test_none_value_goes_to_unset(self):
        service = _make_service()
        validated = {"notes": None}
        result = service._prepare_patch_update(validated, {}, {"computed_status": None})

        assert result["$unset"]["notes"] == ""
        assert "notes" not in result

    def test_is_override_true_sets_override_fields(self):
        service = _make_service()
        service.status_calculator.determine_override_logic = MagicMock(
            return_value=(True, "manual_completion")
        )
        validated = {"status": "completed"}
        result = service._prepare_patch_update(
            validated, {}, {"computed_status": "in_progress", "can_auto_complete": False}
        )

        assert result["manual_override"] is True
        assert "progress" in result

    def test_is_override_false_no_override_fields(self):
        service = _make_service()
        service.status_calculator.determine_override_logic = MagicMock(return_value=(False, None))
        validated = {"status": "accepted"}
        result = service._prepare_patch_update(
            validated, {}, {"computed_status": None, "can_auto_complete": False}
        )

        assert "manual_override" not in result
        assert "progress" not in result

    def test_can_auto_complete_sets_computed_status(self):
        service = _make_service()
        validated = {}
        # no status → determine_override_logic never called
        result = service._prepare_patch_update(
            validated,
            {"computed_status": None},
            {"computed_status": None, "can_auto_complete": True},
        )

        assert result["computed_status"] == "completed"
        assert "progress" in result

    def test_can_auto_complete_skipped_when_computed_status_set(self):
        """If current_uc already has computed_status, skip auto-complete."""
        service = _make_service()
        validated = {}
        result = service._prepare_patch_update(
            validated,
            {"computed_status": "completed"},
            {"computed_status": "completed", "can_auto_complete": True},
        )

        assert "computed_status" not in result


# ---------------------------------------------------------------------------
# _apply_patch_update
# ---------------------------------------------------------------------------


class TestApplyPatchUpdate:
    @pytest.mark.asyncio
    async def test_returns_true_when_modified(self):
        db = _make_db()
        db.user_challenges.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        service = _make_service(db)
        result = await service._apply_patch_update(ObjectId(), ObjectId(), {"status": "accepted"})
        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_not_modified(self):
        db = _make_db()
        db.user_challenges.update_one = AsyncMock(return_value=MagicMock(modified_count=0))

        service = _make_service(db)
        result = await service._apply_patch_update(ObjectId(), ObjectId(), {"status": "accepted"})
        assert result is False

    @pytest.mark.asyncio
    async def test_separates_unset_from_set(self):
        db = _make_db()
        db.user_challenges.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

        service = _make_service(db)
        await service._apply_patch_update(
            ObjectId(), ObjectId(), {"status": "accepted", "$unset": {"notes": ""}}
        )

        call_query = db.user_challenges.update_one.call_args[0][1]
        assert "status" in call_query["$set"]
        assert "$unset" in call_query
        assert "notes" in call_query["$unset"]
        assert "$unset" not in call_query["$set"]
