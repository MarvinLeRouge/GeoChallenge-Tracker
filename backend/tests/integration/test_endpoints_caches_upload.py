"""
Tests d'intégration pour les endpoints Caches - Upload GPX

Organisation par tags Swagger :
- Caches : /caches/*
"""

from pathlib import Path

import pytest


class TestCachesUploadGpx:
    """Tests du endpoint POST /caches/upload-gpx."""

    @pytest.mark.asyncio
    async def test_upload_gpx_requires_auth(self, client):
        """Test que l'upload GPX nécessite une authentification."""
        # Créer un faux fichier GPX
        gpx_content = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0">
</gpx>"""

        response = await client.post(
            "/caches/upload-gpx", files={"file": ("test.gpx", gpx_content, "application/gpx+xml")}
        )

        assert response.status_code == 401
        response = response.json()
        assert response["error"]["code"] == "HTTP_401"

    @pytest.mark.asyncio
    async def test_upload_gpx_success(self, auth_client, seeded_admin):
        """Test que l'upload GPX fonctionne avec authentification."""
        # Utiliser un vrai fichier GPX de test
        gpx_path = (
            Path(__file__).parent.parent.parent
            / "data"
            / "samples"
            / "gpx"
            / "export-2025-08-01-16-35-30-1 Jasmer+Mamies.gpx"
        )

        with open(gpx_path, "rb") as f:
            response = await auth_client.post(
                "/caches/upload-gpx",
                files={"file": ("test.gpx", f, "application/gpx+xml")},
                params={"import_mode": "all", "source_type": "auto"},
            )

        # 200 (succès), 400 (GPX invalide)
        assert response.status_code in [200, 400]
        response = response.json()
        assert "summary" in response and "nb_gpx_files" in response["summary"]
        assert response["summary"]["nb_gpx_files"] == 1
        assert "nb_inserted_caches" in response["summary"]
        assert "nb_existing_caches" in response["summary"]
        assert (
            response["summary"]["nb_inserted_caches"] + response["summary"]["nb_existing_caches"]
            > 0
        )

    @pytest.mark.asyncio
    async def test_upload_gpx_invalid_file(self, auth_client, seeded_admin):
        """Test qu'un fichier GPX invalide est rejeté."""
        # Fichier XML mais pas un GPX valide
        invalid_gpx = b"""<?xml version="1.0" encoding="UTF-8"?>
<notgpx>
  <invalid>This is not a GPX file</invalid>
</notgpx>"""

        response = await auth_client.post(
            "/caches/upload-gpx",
            files={"file": ("invalid.gpx", invalid_gpx, "application/gpx+xml")},
            params={"import_mode": "all", "source_type": "auto"},
        )

        # 400 (GPX invalide)
        assert response.status_code == 400
        data = response.json()
        assert "error" in data
        assert (
            "invalid" in data["error"].get("message", "").lower()
            or "gpx" in data["error"].get("message", "").lower()
        )

    @pytest.mark.asyncio
    async def test_upload_gpx_file_too_big(self, auth_client, seeded_admin):
        """Test qu'un fichier trop lourd est rejeté (limite 20 Mo)."""
        # Créer un fichier GPX de plus de 20 Mo (21 Mo)
        # En-tête GPX valide
        gpx_header = b"""<?xml version="1.0" encoding="UTF-8"?>
<gpx version="1.0" creator="Test">
"""
        gpx_footer = b"</gpx>"

        # Créer un contenu de 21 Mo
        target_size = 21 * 1024 * 1024  # 21 Mo
        padding_size = target_size - len(gpx_header) - len(gpx_footer)
        padding = b" " * padding_size

        too_big_gpx = gpx_header + padding + gpx_footer

        response = await auth_client.post(
            "/caches/upload-gpx",
            files={"file": ("huge.gpx", too_big_gpx, "application/gpx+xml")},
            params={"import_mode": "all", "source_type": "auto"},
        )

        # 413 (Payload too large)
        assert response.status_code == 413
        data = response.json()
        assert "error" in data
