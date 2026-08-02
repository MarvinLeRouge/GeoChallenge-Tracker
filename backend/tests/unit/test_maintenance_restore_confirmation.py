"""Tests for the confirmation-key safeguard on POST /maintenance/db_full_restore.

Before this, a destructive restore (dry_run=False, drop_existing=True - which wipes
every existing collection before restoring) needed nothing beyond a valid admin JWT:
one request, no confirmation, no undo. This mirrors the confirmation-key pattern
already used by DELETE /maintenance/db_cleanup: the first destructive call returns a
short-lived key instead of acting, and the actual restore only runs once that same
key is passed back.

Runs the real route functions against a mocked admin user (dependency override) and
a mocked database/filesystem, rather than a real MongoDB - keeps this in tests/unit/
while still exercising the actual route body.
"""

import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from zipfile import ZIP_DEFLATED, ZipFile

import pytest
from bson import ObjectId
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes import maintenance as maintenance_module
from app.core.security import get_current_user
from app.core.utils import utcnow
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(maintenance_module.router)

    admin_user = User(id=ObjectId(), username="admin", email="admin@example.com", role="admin")
    app.dependency_overrides[get_current_user] = lambda: admin_user
    return app


def _write_backup_zip(path: Path, collections: dict) -> None:
    backup_data = {"timestamp": "2026-01-01T00:00:00", "collections": collections}
    with ZipFile(path, "w", ZIP_DEFLATED) as zf:
        zf.writestr("backup.json", json.dumps(backup_data))


def _make_mock_db():
    mock_collection = AsyncMock()
    mock_collection.insert_many = AsyncMock(
        return_value=AsyncMock(inserted_ids=[ObjectId(), ObjectId()])
    )
    mock_db = MagicMock()
    mock_db.__getitem__ = MagicMock(return_value=mock_collection)
    return mock_db, mock_collection


class TestFullBackupRestoreConfirmation:
    @pytest.mark.asyncio
    async def test_dry_run_never_requires_confirmation(self, tmp_path):
        backup_file = tmp_path / "backup.zip"
        _write_backup_zip(backup_file, {"users": [{"_id": {"$oid": str(ObjectId())}}]})
        mock_db, mock_collection = _make_mock_db()

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": True, "drop_existing": True},
                )

        assert response.status_code == 200
        assert "confirmation_key" not in response.json()
        mock_collection.delete_many.assert_not_awaited()
        mock_collection.insert_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_non_destructive_restore_runs_immediately(self, tmp_path):
        """dry_run=False but drop_existing=False never drops data - no confirmation needed."""
        backup_file = tmp_path / "backup.zip"
        _write_backup_zip(backup_file, {"users": [{"_id": {"$oid": str(ObjectId())}}]})
        mock_db, mock_collection = _make_mock_db()

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": False, "drop_existing": False},
                )

        assert response.status_code == 200
        assert response.json()["message"] == "Full backup restored successfully"
        mock_collection.delete_many.assert_not_awaited()
        mock_collection.insert_many.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_destructive_restore_without_key_returns_confirmation_without_acting(
        self, tmp_path
    ):
        backup_file = tmp_path / "backup.zip"
        _write_backup_zip(backup_file, {"users": [{"_id": {"$oid": str(ObjectId())}}]})
        mock_db, mock_collection = _make_mock_db()
        pending_dir = tmp_path / "pending_restores"

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "PENDING_RESTORE_DIR", pending_dir),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": False, "drop_existing": True},
                )

        assert response.status_code == 200
        body = response.json()
        assert "confirmation_key" in body
        assert "expires_at" in body
        mock_collection.delete_many.assert_not_awaited()
        mock_collection.insert_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_destructive_restore_with_valid_key_actually_restores(self, tmp_path):
        backup_file = tmp_path / "backup.zip"
        _write_backup_zip(backup_file, {"users": [{"_id": {"$oid": str(ObjectId())}}]})
        mock_db, mock_collection = _make_mock_db()
        pending_dir = tmp_path / "pending_restores"

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "PENDING_RESTORE_DIR", pending_dir),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                first = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": False, "drop_existing": True},
                )
                key = first.json()["confirmation_key"]

                second = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": False, "drop_existing": True, "key": key},
                )

        assert second.status_code == 200
        body = second.json()
        assert body["message"] == "Full backup restored successfully"
        assert body["dropped_collections"] == ["users"]
        mock_collection.delete_many.assert_awaited_once_with({})
        mock_collection.insert_many.assert_awaited_once()
        # The key must be single-use.
        assert not (pending_dir / f"{key}.json").exists()

    @pytest.mark.asyncio
    async def test_destructive_restore_with_invalid_key_raises_404(self, tmp_path):
        backup_file = tmp_path / "backup.zip"
        _write_backup_zip(backup_file, {"users": []})
        mock_db, mock_collection = _make_mock_db()
        pending_dir = tmp_path / "pending_restores"

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "PENDING_RESTORE_DIR", pending_dir),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": False, "drop_existing": True, "key": "not-a-real-key"},
                )

        assert response.status_code == 404
        mock_collection.delete_many.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_destructive_restore_with_expired_key_is_rejected(self, tmp_path):
        """An expired key is swept away by clean_expired_keys() before it's even looked
        up, so it surfaces as 404 (not found) rather than the 410 (expired) branch below
        it in the route - same pre-existing behavior as DELETE /maintenance/db_cleanup,
        which this mirrors. Either way, the restore must not run."""
        backup_file = tmp_path / "backup.zip"
        _write_backup_zip(backup_file, {"users": []})
        mock_db, mock_collection = _make_mock_db()
        pending_dir = tmp_path / "pending_restores"
        pending_dir.mkdir(parents=True)
        expired_key = "expired-key"
        (pending_dir / f"{expired_key}.json").write_text(
            json.dumps(
                {
                    "filename": "backup.zip",
                    "expires_at": (utcnow() - timedelta(minutes=1)).isoformat(),
                }
            )
        )

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "PENDING_RESTORE_DIR", pending_dir),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": False, "drop_existing": True, "key": expired_key},
                )

        assert response.status_code == 404
        mock_collection.delete_many.assert_not_awaited()
        assert not (pending_dir / f"{expired_key}.json").exists()

    @pytest.mark.asyncio
    async def test_key_for_a_different_backup_file_is_rejected(self, tmp_path):
        backup_file = tmp_path / "backup.zip"
        _write_backup_zip(backup_file, {"users": []})
        mock_db, mock_collection = _make_mock_db()
        pending_dir = tmp_path / "pending_restores"
        pending_dir.mkdir(parents=True)
        mismatched_key = "mismatched-key"
        (pending_dir / f"{mismatched_key}.json").write_text(
            json.dumps(
                {
                    "filename": "some-other-backup.zip",
                    "expires_at": (utcnow() + timedelta(minutes=10)).isoformat(),
                }
            )
        )

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "PENDING_RESTORE_DIR", pending_dir),
            patch.object(maintenance_module, "get_db", return_value=mock_db),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/maintenance/db_full_restore/backup.zip",
                    params={"dry_run": False, "drop_existing": True, "key": mismatched_key},
                )

        assert response.status_code == 400
        mock_collection.delete_many.assert_not_awaited()
