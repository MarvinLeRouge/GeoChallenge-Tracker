"""Tests for POST /maintenance/db_full_backup (full_backup_create), previously
untested. Mocks get_db to return a fake database exposing list_collection_names
and per-collection find(), and lets write_json_zip run for real against a
tmp_path-patched FULL_BACKUP_DIR so the produced archive can be inspected.
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch
from zipfile import ZipFile

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import maintenance as maintenance_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(maintenance_module.router)

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


def _make_collection(docs: list):
    cursor = MagicMock()
    cursor.to_list = AsyncMock(return_value=docs)
    coll = MagicMock()
    coll.find = MagicMock(return_value=cursor)
    return coll


def _make_mock_db(collections: dict, db_name: str) -> MagicMock:
    """Build a fake Motor database exposing the given collections.

    Args:
        collections: Collection name -> fake collection mock.
        db_name: Value returned for `db.name`.

    Returns:
        MagicMock: Fake database handle.
    """
    mock_db = MagicMock()
    mock_db.name = db_name
    mock_db.list_collection_names = AsyncMock(return_value=list(collections.keys()))
    mock_db.__getitem__ = MagicMock(side_effect=lambda name: collections[name])
    return mock_db


async def _create_full_backup_and_inspect(mock_db: MagicMock, tmp_path):
    """Call the full-backup endpoint with `mock_db`, then load the produced archive.

    Args:
        mock_db: Fake database to patch `get_db` with.
        tmp_path: Directory to patch `FULL_BACKUP_DIR` with.

    Returns:
        tuple: `(response, archive_data, backup_files)`.
    """
    with (
        patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
        patch.object(maintenance_module, "get_db", return_value=mock_db),
    ):
        app = _make_app()
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.post("/maintenance/db_full_backup")

    backup_files = list(tmp_path.glob("*_full_backup.zip"))
    with ZipFile(backup_files[0]) as zf:
        json_name = next(n for n in zf.namelist() if n.endswith(".json"))
        archive_data = json.loads(zf.read(json_name).decode("utf-8"))

    return response, archive_data, backup_files


class TestFullBackupCreate:
    @pytest.mark.asyncio
    async def test_backs_up_non_empty_non_system_collections_only(self, tmp_path):
        user_doc = {"_id": ObjectId(), "username": "alice"}
        collections = {
            "users": _make_collection([user_doc]),
            "empty_collection": _make_collection([]),
            "system.indexes": _make_collection([{"_id": ObjectId()}]),
        }

        mock_db = _make_mock_db(collections, "geochallenge_test")

        response, data, backup_files = await _create_full_backup_and_inspect(mock_db, tmp_path)

        expected_body = {
            "message": "Full backup created successfully",
            "total_collections": 1,
            "total_documents": 1,
        }
        assert response.status_code == 200
        body = response.json()
        for key, expected_value in expected_body.items():
            assert body[key] == expected_value

        assert len(backup_files) == 1
        assert data["database"] == "geochallenge_test"
        assert list(data["collections"].keys()) == ["users"]
        assert "empty_collection" not in data["collections"]
        assert "system.indexes" not in data["collections"]
