"""Tests for UserChallengeValidator (unit tests — DB fully mocked)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bson import ObjectId

from app.services.user_challenges.user_challenge_validator import UserChallengeValidator

_UID = ObjectId()
_UCID = ObjectId()


def _make_validator(find_one_result=None, count_documents_result=0):
    """Build a UserChallengeValidator with a mocked DB."""
    mock_db = MagicMock()
    mock_db.user_challenges.find_one = AsyncMock(return_value=find_one_result)
    mock_db.user_challenges.count_documents = AsyncMock(return_value=count_documents_result)
    mock_db.challenges.find_one = AsyncMock(return_value=None)
    mock_db.found_caches.find_one = AsyncMock(return_value=None)
    return UserChallengeValidator(mock_db)


# ---------------------------------------------------------------------------
# validate_bulk_operation — structural checks (no DB needed for failure paths)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_bulk_empty_list_invalid():
    validator = _make_validator()
    ok, err, valid_ids = await validator.validate_bulk_operation(_UID, [], "dismiss")
    assert ok is False
    assert "No UserChallenge" in err
    assert valid_ids == []


@pytest.mark.asyncio
async def test_bulk_too_many_ids():
    validator = _make_validator()
    ids = [ObjectId() for _ in range(101)]
    ok, err, valid_ids = await validator.validate_bulk_operation(_UID, ids, "dismiss")
    assert ok is False
    assert "max 100" in err


@pytest.mark.asyncio
async def test_bulk_invalid_operation():
    validator = _make_validator()
    ok, err, _ = await validator.validate_bulk_operation(_UID, [_UCID], "fly_to_moon")
    assert ok is False
    assert "Invalid operation" in err


@pytest.mark.asyncio
async def test_bulk_valid():
    validator = _make_validator(count_documents_result=2)
    ids = [ObjectId(), ObjectId()]
    ok, err, valid_ids = await validator.validate_bulk_operation(_UID, ids, "accept")
    assert ok is True
    assert err is None
    assert valid_ids == ids


@pytest.mark.asyncio
async def test_bulk_count_mismatch():
    """Some IDs not found or not owned."""
    validator = _make_validator(count_documents_result=1)
    ids = [ObjectId(), ObjectId()]
    ok, err, _ = await validator.validate_bulk_operation(_UID, ids, "dismiss")
    assert ok is False
    assert "not found or not owned" in err


# ---------------------------------------------------------------------------
# validate_patch_operation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_uc_not_found():
    validator = _make_validator(find_one_result=None)
    ok, err, data = await validator.validate_patch_operation(_UID, _UCID, {"status": "accepted"})
    assert ok is False
    assert "not found" in err


@pytest.mark.asyncio
async def test_patch_invalid_fields():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, _ = await validator.validate_patch_operation(_UID, _UCID, {"unknown_field": "x"})
    assert ok is False
    assert "Invalid fields" in err


@pytest.mark.asyncio
async def test_patch_notes_too_long():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, _ = await validator.validate_patch_operation(_UID, _UCID, {"notes": "x" * 2001})
    assert ok is False
    assert "too long" in err


@pytest.mark.asyncio
async def test_patch_notes_not_string():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, _ = await validator.validate_patch_operation(_UID, _UCID, {"notes": 123})
    assert ok is False
    assert "string" in err


@pytest.mark.asyncio
async def test_patch_notes_none_accepted():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(_UID, _UCID, {"notes": None})
    assert ok is True
    assert data["notes"] is None


@pytest.mark.asyncio
async def test_patch_status_valid():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending", "computed_status": None}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(_UID, _UCID, {"status": "accepted"})
    assert ok is True
    assert data["status"] == "accepted"


@pytest.mark.asyncio
async def test_patch_manual_override_non_bool():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, _ = await validator.validate_patch_operation(_UID, _UCID, {"manual_override": "yes"})
    assert ok is False
    assert "boolean" in err


@pytest.mark.asyncio
async def test_patch_override_reason_too_long():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, _ = await validator.validate_patch_operation(
        _UID, _UCID, {"override_reason": "r" * 501}
    )
    assert ok is False
    assert "too long" in err


@pytest.mark.asyncio
async def test_patch_override_reason_not_string():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, _ = await validator.validate_patch_operation(_UID, _UCID, {"override_reason": 42})
    assert ok is False
    assert "string" in err


# ---------------------------------------------------------------------------
# validate_ownership
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ownership_found():
    uc = {"_id": _UCID, "user_id": _UID}
    validator = _make_validator(find_one_result=uc)
    assert await validator.validate_ownership(_UID, _UCID) is True


@pytest.mark.asyncio
async def test_ownership_not_found():
    validator = _make_validator(find_one_result=None)
    assert await validator.validate_ownership(_UID, _UCID) is False


# ---------------------------------------------------------------------------
# validate_patch_operation — missing branches
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_invalid_status_transition():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending", "computed_status": None}
    validator = _make_validator(find_one_result=uc)
    ok, err, _ = await validator.validate_patch_operation(_UID, _UCID, {"status": "invalid_status"})
    assert ok is False
    assert err is not None


@pytest.mark.asyncio
async def test_patch_notes_stripped():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(_UID, _UCID, {"notes": "  hello  "})
    assert ok is True
    assert data["notes"] == "hello"


@pytest.mark.asyncio
async def test_patch_notes_whitespace_only_becomes_none():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(_UID, _UCID, {"notes": "   "})
    assert ok is True
    assert data["notes"] is None


@pytest.mark.asyncio
async def test_patch_manual_override_valid_bool():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(_UID, _UCID, {"manual_override": True})
    assert ok is True
    assert data["manual_override"] is True


@pytest.mark.asyncio
async def test_patch_override_reason_valid():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(
        _UID, _UCID, {"override_reason": "  justified  "}
    )
    assert ok is True
    assert data["override_reason"] == "justified"


@pytest.mark.asyncio
async def test_patch_override_reason_whitespace_becomes_none():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(
        _UID, _UCID, {"override_reason": "   "}
    )
    assert ok is True
    assert data["override_reason"] is None


@pytest.mark.asyncio
async def test_patch_override_reason_none():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    ok, err, data = await validator.validate_patch_operation(_UID, _UCID, {"override_reason": None})
    assert ok is True
    assert data["override_reason"] is None


# ---------------------------------------------------------------------------
# get_patch_dependencies
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def testget_patch_dependencies_not_found():
    validator = _make_validator(find_one_result=None)
    result = await validator.get_patch_dependencies(_UID, _UCID)
    assert result == {}


@pytest.mark.asyncio
async def testget_patch_dependencies_found_no_challenge_id():
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending"}
    validator = _make_validator(find_one_result=uc)
    result = await validator.get_patch_dependencies(_UID, _UCID)
    assert "current_uc" in result
    assert result["challenge_cache_found"] is False


@pytest.mark.asyncio
async def testget_patch_dependencies_with_objectid_challenge_id():
    challenge_id = ObjectId()
    uc = {"_id": _UCID, "user_id": _UID, "status": "pending", "challenge_id": challenge_id}
    validator = _make_validator(find_one_result=uc)
    result = await validator.get_patch_dependencies(_UID, _UCID)
    assert "current_uc" in result
    assert "challenge_cache_found" in result


# ---------------------------------------------------------------------------
# _is_challenge_cache_found
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_challenge_cache_found_no_challenge():
    mock_db = MagicMock()
    mock_db.challenges.find_one = AsyncMock(return_value=None)
    mock_db.found_caches.find_one = AsyncMock(return_value=None)
    validator = UserChallengeValidator(mock_db)
    result = await validator._is_challenge_cache_found(_UID, ObjectId())
    assert result is False


@pytest.mark.asyncio
async def test_is_challenge_cache_found_no_cache_id():
    mock_db = MagicMock()
    mock_db.challenges.find_one = AsyncMock(return_value={"_id": ObjectId()})
    mock_db.found_caches.find_one = AsyncMock(return_value=None)
    validator = UserChallengeValidator(mock_db)
    result = await validator._is_challenge_cache_found(_UID, ObjectId())
    assert result is False


@pytest.mark.asyncio
async def test_is_challenge_cache_found_cache_found():
    cache_id = ObjectId()
    mock_db = MagicMock()
    mock_db.challenges.find_one = AsyncMock(return_value={"_id": ObjectId(), "cache_id": cache_id})
    mock_db.found_caches.find_one = AsyncMock(return_value={"_id": ObjectId()})
    validator = UserChallengeValidator(mock_db)
    result = await validator._is_challenge_cache_found(_UID, ObjectId())
    assert result is True


@pytest.mark.asyncio
async def test_is_challenge_cache_not_found():
    cache_id = ObjectId()
    mock_db = MagicMock()
    mock_db.challenges.find_one = AsyncMock(return_value={"_id": ObjectId(), "cache_id": cache_id})
    mock_db.found_caches.find_one = AsyncMock(return_value=None)
    validator = UserChallengeValidator(mock_db)
    result = await validator._is_challenge_cache_found(_UID, ObjectId())
    assert result is False
