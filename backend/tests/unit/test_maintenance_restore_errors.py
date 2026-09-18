"""Tests for the error branches of POST /maintenance/db_full_restore/{filename}
that test_maintenance_restore_confirmation.py doesn't cover: it focuses on the
confirmation-key safeguard, not on filename validation or archive-content
errors, which are checked earlier in the route body regardless of dry_run/
drop_existing.
"""

from unittest.mock import MagicMock, patch

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


class TestFullBackupRestoreErrors:
    @pytest.mark.asyncio
    async def test_path_traversal_filename_rejected(self, tmp_path):
        """The {filename} path converter never lets a literal "/" through, so the
        only way to reach the "/" branch of the guard is a filename containing
        two consecutive dots, e.g. from a client bypassing the routing layer."""
        with patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/maintenance/db_full_restore/backup..zip")

        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_missing_backup_file_returns_404(self, tmp_path):
        with patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/maintenance/db_full_restore/missing.zip")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_zip_without_json_entry_returns_400(self, tmp_path):
        from zipfile import ZIP_DEFLATED, ZipFile

        backup_file = tmp_path / "no_json.zip"
        with ZipFile(backup_file, "w", ZIP_DEFLATED) as zf:
            zf.writestr("readme.txt", "not a backup")

        with (
            patch.object(maintenance_module, "FULL_BACKUP_DIR", tmp_path),
            patch.object(maintenance_module, "get_db", return_value=MagicMock()),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/maintenance/db_full_restore/no_json.zip")

        assert response.status_code == 400
