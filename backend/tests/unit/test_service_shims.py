"""Tests for compatibility shim modules (unit tests — no DB required).

Covers: gpx_importer_service.py, user_challenges_service.py,
        user_challenge_tasks_service.py, targets_service.py
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId

_UID = ObjectId()
_UC_ID = ObjectId()


# ===========================================================================
# gpx_importer_service.py
# ===========================================================================


@pytest.fixture()
def gpx_shim():
    import app.services.gpx_importer_service as mod

    old = mod._gpx_import_service
    mod._gpx_import_service = None
    yield mod
    mod._gpx_import_service = old


def test_get_gpx_import_service_creates_on_first_call(gpx_shim):
    mod = gpx_shim
    mock_db = MagicMock()
    mock_instance = MagicMock()
    with (
        patch.object(mod, "get_db", return_value=mock_db),
        patch.object(mod, "GpxImportService", return_value=mock_instance) as cls_mock,
    ):
        result = mod.get_gpx_import_service()

    cls_mock.assert_called_once_with(mock_db)
    assert result is mock_instance
    assert mod._gpx_import_service is mock_instance


def test_get_gpx_import_service_reuses_existing(gpx_shim):
    mod = gpx_shim
    existing = MagicMock()
    mod._gpx_import_service = existing

    with patch.object(mod, "get_db") as mock_get_db:
        result = mod.get_gpx_import_service()

    mock_get_db.assert_not_called()
    assert result is existing


@pytest.mark.asyncio
async def test_import_gpx_payload_delegates(gpx_shim):
    mod = gpx_shim
    mock_service = MagicMock()
    mock_service.import_gpx_payload = AsyncMock(return_value={"imported": 1})
    mod._gpx_import_service = mock_service

    result = await mod.import_gpx_payload(
        b"data",
        filename="test.gpx",
        user_id=_UID,
        import_mode="both",
        fetch_elevation=False,
    )

    assert result == {"imported": 1}
    mock_service.import_gpx_payload.assert_awaited_once()


# ===========================================================================
# user_challenges_service.py
# ===========================================================================


@pytest.fixture()
def uc_shim():
    import app.services.user_challenges_service as mod

    old = mod._user_challenge_service
    mod._user_challenge_service = None
    yield mod
    mod._user_challenge_service = old


def test_get_user_challenge_service_creates_on_first_call(uc_shim):
    mod = uc_shim
    mock_db = MagicMock()
    mock_instance = MagicMock()
    with (
        patch.object(mod, "get_db", return_value=mock_db),
        patch.object(mod, "UserChallengeService", return_value=mock_instance) as cls_mock,
    ):
        result = mod.get_user_challenge_service()

    cls_mock.assert_called_once_with(mock_db)
    assert result is mock_instance


def test_get_user_challenge_service_reuses_existing(uc_shim):
    mod = uc_shim
    existing = MagicMock()
    mod._user_challenge_service = existing

    with patch.object(mod, "get_db") as mock_get_db:
        result = mod.get_user_challenge_service()

    mock_get_db.assert_not_called()
    assert result is existing


@pytest.mark.asyncio
async def test_uc_sync_user_challenges_delegates(uc_shim):
    mod = uc_shim
    svc = MagicMock()
    svc.sync_user_challenges = AsyncMock(return_value={"created": 1})
    mod._user_challenge_service = svc

    result = await mod.sync_user_challenges(_UID)
    assert result == {"created": 1}
    svc.sync_user_challenges.assert_awaited_once_with(_UID)


@pytest.mark.asyncio
async def test_uc_list_user_challenges_delegates(uc_shim):
    mod = uc_shim
    svc = MagicMock()
    svc.list_user_challenges = AsyncMock(return_value={"items": []})
    mod._user_challenge_service = svc

    result = await mod.list_user_challenges(_UID, status_filter="pending", page=2, page_size=10)
    assert result == {"items": []}
    svc.list_user_challenges.assert_awaited_once_with(
        user_id=_UID, status_filter="pending", page=2, page_size=10
    )


@pytest.mark.asyncio
async def test_uc_get_user_challenge_detail_delegates(uc_shim):
    mod = uc_shim
    svc = MagicMock()
    svc.get_user_challenge_detail = AsyncMock(return_value={"_id": _UC_ID})
    mod._user_challenge_service = svc

    result = await mod.get_user_challenge_detail(_UID, _UC_ID)
    assert result == {"_id": _UC_ID}


@pytest.mark.asyncio
async def test_uc_patch_user_challenge_delegates(uc_shim):
    mod = uc_shim
    svc = MagicMock()
    svc.patch_user_challenge = AsyncMock(return_value=(True, None, {"status": "accepted"}))
    mod._user_challenge_service = svc

    ok, err, data = await mod.patch_user_challenge(_UID, _UC_ID, {"status": "accepted"})
    assert ok is True
    assert data == {"status": "accepted"}


# ===========================================================================
# user_challenge_tasks_service.py
# ===========================================================================


@pytest.fixture()
def uct_shim():
    import app.services.user_challenge_tasks_service as mod

    old = mod._user_challenge_task_service
    mod._user_challenge_task_service = None
    yield mod
    mod._user_challenge_task_service = old


def test_get_uct_service_creates_on_first_call(uct_shim):
    mod = uct_shim
    mock_instance = MagicMock()
    with patch.object(mod, "UserChallengeTaskService", return_value=mock_instance) as cls_mock:
        result = mod.get_user_challenge_task_service()

    cls_mock.assert_called_once_with()
    assert result is mock_instance


def test_get_uct_service_reuses_existing(uct_shim):
    mod = uct_shim
    existing = MagicMock()
    mod._user_challenge_task_service = existing

    result = mod.get_user_challenge_task_service()
    assert result is existing


@pytest.mark.asyncio
async def test_uct_list_tasks_delegates(uct_shim):
    mod = uct_shim
    svc = MagicMock()
    svc.list_tasks = AsyncMock(return_value=[{"order": 0}])
    mod._user_challenge_task_service = svc

    result = await mod.list_tasks(_UID, _UC_ID)
    assert result == [{"order": 0}]
    svc.list_tasks.assert_awaited_once_with(_UID, _UC_ID)


def test_uct_validate_only_delegates(uct_shim):
    mod = uct_shim
    svc = MagicMock()
    svc.validate_only = MagicMock(return_value={"ok": True})
    mod._user_challenge_task_service = svc

    result = mod.validate_only(_UID, _UC_ID, [])
    assert result == {"ok": True}
    svc.validate_only.assert_called_once_with(_UID, _UC_ID, [])


@pytest.mark.asyncio
async def test_uct_put_tasks_delegates(uct_shim):
    mod = uct_shim
    svc = MagicMock()
    svc.put_tasks = AsyncMock(return_value=[])
    mod._user_challenge_task_service = svc

    result = await mod.put_tasks(_UID, _UC_ID, [])
    assert result == []


def test_uct_compile_expression_delegates(uct_shim):
    from app.domain.models.challenge_ast import RulePlacedYear, TaskAnd

    mod = uct_shim
    svc = MagicMock()
    svc.compile_expression_to_cache_match = MagicMock(return_value={"year": 2020})
    mod._user_challenge_task_service = svc

    expr = TaskAnd(nodes=[RulePlacedYear(year=2020)])
    result = mod.compile_expression_to_cache_match(expr)
    assert result == {"year": 2020}


def test_uct_validate_task_expression_delegates(uct_shim):
    from app.domain.models.challenge_ast import RulePlacedYear, TaskAnd

    mod = uct_shim
    svc = MagicMock()
    svc.validate_task_expression = MagicMock(return_value=[])
    mod._user_challenge_task_service = svc

    expr = TaskAnd(nodes=[RulePlacedYear(year=2020)])
    result = mod.validate_task_expression(expr)
    assert result == []


# ===========================================================================
# targets_service.py
# ===========================================================================


@pytest.fixture()
def tgt_shim():
    import app.services.targets_service as mod

    old = mod._target_service
    mod._target_service = None
    yield mod
    mod._target_service = old


def test_get_target_service_creates_on_first_call(tgt_shim):
    mod = tgt_shim
    mock_db = MagicMock()
    mock_instance = MagicMock()
    with (
        patch.object(mod, "get_db", return_value=mock_db),
        patch.object(mod, "TargetService", return_value=mock_instance) as cls_mock,
    ):
        result = mod.get_target_service()

    cls_mock.assert_called_once_with(mock_db)
    assert result is mock_instance


def test_get_target_service_reuses_existing(tgt_shim):
    mod = tgt_shim
    existing = MagicMock()
    mod._target_service = existing

    with patch.object(mod, "get_db") as mock_get_db:
        result = mod.get_target_service()

    mock_get_db.assert_not_called()
    assert result is existing


@pytest.mark.asyncio
async def test_tgt_evaluate_targets_delegates(tgt_shim):
    mod = tgt_shim
    svc = MagicMock()
    svc.evaluate_targets_for_user_challenge = AsyncMock(return_value={"evaluated": 5})
    mod._target_service = svc

    result = await mod.evaluate_targets_for_user_challenge(_UID, _UC_ID, limit_per_task=100)
    assert result == {"evaluated": 5}
    svc.evaluate_targets_for_user_challenge.assert_awaited_once()


@pytest.mark.asyncio
async def test_tgt_list_targets_for_uc_delegates(tgt_shim):
    mod = tgt_shim
    svc = MagicMock()
    svc.list_targets_for_user_challenge = AsyncMock(return_value={"items": []})
    mod._target_service = svc

    result = await mod.list_targets_for_user_challenge(_UID, _UC_ID, page=1, page_size=20)
    assert result == {"items": []}


@pytest.mark.asyncio
async def test_tgt_list_targets_nearby_for_uc_delegates(tgt_shim):
    mod = tgt_shim
    svc = MagicMock()
    svc.list_targets_nearby_for_user_challenge = AsyncMock(return_value={"items": []})
    mod._target_service = svc

    result = await mod.list_targets_nearby_for_user_challenge(
        _UID, _UC_ID, lat=48.85, lon=2.35, radius_km=10.0
    )
    assert result == {"items": []}


@pytest.mark.asyncio
async def test_tgt_list_targets_for_user_delegates(tgt_shim):
    mod = tgt_shim
    svc = MagicMock()
    svc.list_targets_for_user = AsyncMock(return_value={"items": []})
    mod._target_service = svc

    result = await mod.list_targets_for_user(_UID, status_filter="active")
    assert result == {"items": []}


@pytest.mark.asyncio
async def test_tgt_list_targets_nearby_for_user_delegates(tgt_shim):
    mod = tgt_shim
    svc = MagicMock()
    svc.list_targets_nearby_for_user = AsyncMock(return_value={"items": []})
    mod._target_service = svc

    result = await mod.list_targets_nearby_for_user(_UID, lat=48.0, lon=2.0, radius_km=50.0)
    assert result == {"items": []}


@pytest.mark.asyncio
async def test_tgt_delete_targets_for_uc_delegates(tgt_shim):
    mod = tgt_shim
    svc = MagicMock()
    svc.delete_targets_for_user_challenge = AsyncMock(return_value={"deleted": 3})
    mod._target_service = svc

    result = await mod.delete_targets_for_user_challenge(_UID, _UC_ID)
    assert result == {"deleted": 3}
    svc.delete_targets_for_user_challenge.assert_awaited_once_with(user_id=_UID, uc_id=_UC_ID)
