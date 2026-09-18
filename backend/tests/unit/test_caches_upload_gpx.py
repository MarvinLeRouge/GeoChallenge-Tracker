"""Tests for POST /caches/upload-gpx, previously entirely untested. Covers the
streaming size-limit check, the import/challenges/sync error-swallowing
branches (each wrapped in its own try/except so one failure doesn't break the
others), and the import_mode="found" post-import progress evaluation.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bson import ObjectId
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient

from app.api.routes import caches as caches_module
from app.core.security import get_current_user
from app.domain.models.user import User


def _make_app():
    app = FastAPI()
    app.include_router(caches_module.router)

    user = User(id=ObjectId(), username="alice", email="alice@example.com", role="user")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


def _small_settings():
    settings = MagicMock()
    settings.one_mb = 1024 * 1024
    settings.max_upload_mb = 1
    settings.max_upload_bytes = 100
    return settings


class TestUploadGpxSizeLimit:
    @pytest.mark.asyncio
    async def test_oversized_file_rejected_with_413(self):
        with (
            patch.object(caches_module, "settings", _small_settings()),
            patch.object(caches_module, "import_gpx_payload") as mock_import,
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/upload-gpx",
                    files={"file": ("caches.gpx", b"x" * 500, "application/gpx+xml")},
                )

        assert response.status_code == 413
        mock_import.assert_not_called()


class TestUploadGpxImportErrors:
    @pytest.mark.asyncio
    async def test_generic_import_error_is_reported_as_400(self):
        with (
            patch.object(
                caches_module,
                "import_gpx_payload",
                new=AsyncMock(side_effect=ValueError("malformed GPX")),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/upload-gpx",
                    files={"file": ("caches.gpx", b"<gpx></gpx>", "application/gpx+xml")},
                )

        assert response.status_code == 400
        assert "malformed GPX" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_http_exception_from_import_is_passed_through(self):
        with patch.object(
            caches_module,
            "import_gpx_payload",
            new=AsyncMock(side_effect=HTTPException(status_code=422, detail="bad format")),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/upload-gpx",
                    files={"file": ("caches.gpx", b"<gpx></gpx>", "application/gpx+xml")},
                )

        assert response.status_code == 422
        assert response.json()["detail"] == "bad format"


class TestUploadGpxPostImportSteps:
    @pytest.mark.asyncio
    async def test_challenge_and_sync_failures_are_swallowed_as_error_fields(self):
        with (
            patch.object(
                caches_module,
                "import_gpx_payload",
                new=AsyncMock(return_value={"imported": 3}),
            ),
            patch.object(
                caches_module,
                "create_new_challenges_from_caches",
                new=AsyncMock(side_effect=RuntimeError("challenge scan failed")),
            ),
            patch.object(
                caches_module,
                "sync_user_challenges",
                new=AsyncMock(side_effect=RuntimeError("sync failed")),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/upload-gpx",
                    files={"file": ("caches.gpx", b"<gpx></gpx>", "application/gpx+xml")},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["summary"] == {"imported": 3}
        assert body["challenges_stats"] == {"error": "challenge scan failed"}
        assert body["sync_stats"] == {"error": "sync failed"}
        # import_mode defaults to "all", so no progress evaluation is attempted.
        assert "progress_stats" not in body


class TestUploadGpxFoundModeProgress:
    @pytest.mark.asyncio
    async def test_found_mode_evaluates_progress_for_accepted_user_challenges(self):
        uc_id_ok = ObjectId()
        uc_id_failing = ObjectId()
        coll_uc = AsyncMock()
        coll_uc.find = MagicMock(
            return_value=MagicMock(
                to_list=AsyncMock(return_value=[{"_id": uc_id_ok}, {"_id": uc_id_failing}])
            )
        )

        async def _evaluate_progress(uid, uc_id):
            if uc_id == uc_id_failing:
                raise RuntimeError("evaluation exploded")
            return {"percent": 50, "tasks_done": 1, "tasks_total": 2}

        with (
            patch.object(
                caches_module,
                "import_gpx_payload",
                new=AsyncMock(return_value={"imported": 1}),
            ),
            patch.object(
                caches_module,
                "create_new_challenges_from_caches",
                new=AsyncMock(return_value={"created": 0}),
            ),
            patch.object(
                caches_module, "sync_user_challenges", new=AsyncMock(return_value={"synced": 0})
            ),
            patch.object(caches_module, "get_collection", new=AsyncMock(return_value=coll_uc)),
            patch.object(caches_module, "evaluate_progress", side_effect=_evaluate_progress),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/upload-gpx",
                    params={"import_mode": "found"},
                    files={"file": ("caches.gpx", b"<gpx></gpx>", "application/gpx+xml")},
                )

        assert response.status_code == 200
        body = response.json()
        assert body["progress_stats"] == {"evaluated": 1, "total": 2}

    @pytest.mark.asyncio
    async def test_found_mode_outer_failure_is_reported_as_error_field(self):
        with (
            patch.object(
                caches_module,
                "import_gpx_payload",
                new=AsyncMock(return_value={"imported": 1}),
            ),
            patch.object(
                caches_module,
                "create_new_challenges_from_caches",
                new=AsyncMock(return_value={"created": 0}),
            ),
            patch.object(
                caches_module, "sync_user_challenges", new=AsyncMock(return_value={"synced": 0})
            ),
            patch.object(
                caches_module,
                "get_collection",
                new=AsyncMock(side_effect=RuntimeError("db unavailable")),
            ),
        ):
            app = _make_app()
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    "/caches/upload-gpx",
                    params={"import_mode": "found"},
                    files={"file": ("caches.gpx", b"<gpx></gpx>", "application/gpx+xml")},
                )

        assert response.status_code == 200
        assert response.json()["progress_stats"] == {"error": "db unavailable"}
