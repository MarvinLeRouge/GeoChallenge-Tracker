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


class TestFullBackupCreate:
    @pytest.mark.asyncio
    async def test_backs_up_non_empty_non_system_collections_only(self, tmp_path):
        user_doc = {"_id": ObjectId(), "username": "alice"}
        collections = {
            "users": _make_collection([user_doc]),
            "empty_collection": _make_collection([]),
            "system.indexes": _make_collection([{"_id": ObjectId()}]),
        }

        mock_db = MagicMock()
        mock_db.name = "geochallenge_test"
        mock_db.list_collection_names = AsyncMock(return_value=list(collections.keys()))
        mock_db.__getitem__ = MagicMock(side_effect=lambda name: collections[name])

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/maintenance/db_full_backup")

        assert response.status_code == 200
        body = response.json()
        assert body["message"] == "Full backup created successfully"
        assert body["total_collections"] == 1
        assert body["total_documents"] == 1

        backup_files = list(tmp_path.glob("*_full_backup.zip"))
        assert len(backup_files) == 1
        with ZipFile(backup_files[0]) as zf:
            json_name = next(n for n in zf.namelist() if n.endswith(".json"))
            data = json.loads(zf.read(json_name).decode("utf-8"))

        assert data["database"] == "geochallenge_test"
        assert list(data["collections"].keys()) == ["users"]
        assert "empty_collection" not in data["collections"]
        assert "system.indexes" not in data["collections"]
