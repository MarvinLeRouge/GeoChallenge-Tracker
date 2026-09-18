"""Tests for the backup-listing and download routes in maintenance.py, all
previously uncovered: GET /maintenance/db_cleanup/backups, GET /maintenance/
db_backups, and GET /maintenance/backups/{filepath:path}.
"""

import json
from unittest.mock import patch
from zipfile import ZIP_DEFLATED, ZipFile

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


def _write_zip(path, json_name, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(path, "w", ZIP_DEFLATED) as zf:
        if json_name:
            zf.writestr(json_name, json.dumps(payload))
        else:
            zf.writestr("readme.txt", "no json here")


class TestCleanupListBackups:
    @pytest.mark.asyncio
    async def test_lists_cleanup_backups_and_reports_unreadable_ones(self, tmp_path):
        good = tmp_path / "2026-01-01_00-00-00_cleanup.zip"
        _write_zip(
            good,
            "2026-01-01_00-00-00_cleanup.json",
            {
                "timestamp": "2026-01-01T00:00:00",
                "total_deleted": 2,
                "deleted_by_collection": {"states": 2},
            },
        )
        bad = tmp_path / "2026-01-02_00-00-00_cleanup.zip"
        bad.write_bytes(b"not a real zip")

        with patch.object(maintenance_module, "CLEANUP_BACKUP_DIR", tmp_path):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/db_cleanup/backups")

        assert response.status_code == 200
        body = response.json()
        assert body["total_backups"] == 2
        filenames = {b["filename"] for b in body["backups"]}
        assert filenames == {good.name, bad.name}
        bad_entry = next(b for b in body["backups"] if b["filename"] == bad.name)
        assert "error" in bad_entry


class TestListAllBackups:
    @pytest.mark.asyncio
    async def test_lists_both_cleanup_and_full_backups(self, tmp_path):
        cleanup_dir = tmp_path / "db_cleanup"
        full_dir = tmp_path / "full_backup"

        _write_zip(
            cleanup_dir / "2026-01-01_00-00-00_cleanup.zip",
            "2026-01-01_00-00-00_cleanup.json",
            {"timestamp": "2026-01-01T00:00:00", "total_deleted": 1, "deleted_by_collection": {}},
        )
        _write_zip(
            full_dir / "2026-01-02_00-00-00_full_backup.zip",
            "2026-01-02_00-00-00_full_backup.json",
            {"timestamp": "2026-01-02T00:00:00", "total_collections": 3, "total_documents": 10},
        )
        # A full backup archive with no JSON metadata inside takes the "else" branch.
        no_json = full_dir / "2026-01-03_00-00-00_full_backup.zip"
        _write_zip(no_json, None, None)

        with (
            patch.object(maintenance_module, "CLEANUP_BACKUP_DIR", cleanup_dir),
            patch.object(maintenance_module, "FULL_BACKUP_DIR", full_dir),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/db_backups")

        assert response.status_code == 200
        body = response.json()
        assert body["total_cleanup_backups"] == 1
        assert body["total_full_backups"] == 2
        no_json_entry = next(
            b for b in body["backups"]["full_backups"] if b["filename"] == no_json.name
        )
        assert no_json_entry["error"] == "No JSON metadata file found in archive"


class TestGetBackupFile:
    @pytest.mark.asyncio
    async def test_downloads_existing_backup_file(self, tmp_path):
        backup_root = tmp_path
        target = backup_root / "full_backup" / "backup.zip"
        _write_zip(target, "backup.json", {"timestamp": "2026-01-01T00:00:00"})

        with patch.object(maintenance_module, "BACKUP_ROOT_DIR", backup_root):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/backups/full_backup/backup.zip")

        assert response.status_code == 200
        assert response.headers["content-type"] == "application/zip"

    @pytest.mark.asyncio
    async def test_missing_backup_file_returns_404(self, tmp_path):
        with patch.object(maintenance_module, "BACKUP_ROOT_DIR", tmp_path):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.get("/maintenance/backups/full_backup/missing.zip")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_path_traversal_outside_backup_root_rejected(self, tmp_path):
        """A literal ".." in the URL never reaches the route: httpx (like browsers)
        collapses dot-segments before sending, so a plain "/backups/../x" request is
        normalized client-side into a 404 on an unmatched route. Percent-encoding the
        dots (%2e%2e) survives that normalization and lets ".." through to the
        {filepath:path} converter, which is what the resolve()-based guard defends
        against."""
        outside_secret = tmp_path.parent / f"{tmp_path.name}_outside_secret.txt"
        outside_secret.write_text("top secret")
        backup_root = tmp_path / "backups"
        backup_root.mkdir()

        try:
            with patch.object(maintenance_module, "BACKUP_ROOT_DIR", backup_root):
                app = _make_app()
                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get(
                        f"/maintenance/backups/%2e%2e/{outside_secret.name}"
                    )

            assert response.status_code == 400
        finally:
            outside_secret.unlink(missing_ok=True)
