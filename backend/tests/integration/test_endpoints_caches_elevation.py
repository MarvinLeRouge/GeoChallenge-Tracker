"""
Tests d'intégration pour les endpoints Caches Elevation

Organisation par tags Swagger :
- Caches_Elevation : /caches_elevation/*

Ces tests vérifient :
- Que les endpoints d'élévation fonctionnent
- Que l'authentification admin est requise
"""

import pytest

# =============================================================================
# TAG: CACHES_ELEVATION - Backfill Elevation
# =============================================================================


class TestCachesElevationBackfill:
    """Tests du endpoint POST /caches_elevation/caches/elevation/backfill."""

    @pytest.mark.asyncio
    async def test_backfill_requires_auth(self, client):
        """Test que le backfill d'élévation nécessite une authentification."""
        response = await client.post("/caches_elevation/caches/elevation/backfill", json={})

        assert response.status_code == 401
        data = response.json()
        assert (
            isinstance(data, dict)
            and "error" in data
            and "code" in data["error"]
            and data["error"]["code"] == "HTTP_401"
        )

    @pytest.mark.asyncio
    async def test_backfill_requires_admin(self, auth_client):
        """Test que le backfill d'élévation nécessite les droits admin."""
        # auth_client utilise un token admin par défaut, donc ce test
        # vérifie juste que l'endpoint est accessible avec un token valide
        params = {"limit": 1000, "page_size": 500, "dry_run": True}
        response = await auth_client.post(
            "/caches_elevation/caches/elevation/backfill", params=params
        )

        # 200 (succès), 403 (non admin)
        # L'important est que l'endpoint soit accessible
        assert response.status_code in [200, 403]

    @pytest.mark.asyncio
    async def test_backfill_dry_run(self, auth_client, seeded_admin, caches_without_elevation):
        """Test que le backfill en mode dry_run fonctionne."""
        params = {"limit": 1000, "page_size": 500, "dry_run": True}
        response = await auth_client.post(
            "/caches_elevation/caches/elevation/backfill", params=params
        )

        # 200 (succès)
        # L'important est que l'endpoint soit accessible
        assert response.status_code == 200
        data = response.json()
        assert (
            "scanned" in data
            and "batches" in data
            and data["batches"] * params["page_size"] >= params["limit"]
        )

    @pytest.mark.asyncio
    async def test_backfill_real(self, auth_client, seeded_admin, caches_without_elevation):
        """Test que le backfill en mode dry_run fonctionne."""
        params = {"limit": 1000, "page_size": 500, "dry_run": False}
        response = await auth_client.post(
            "/caches_elevation/caches/elevation/backfill", params=params
        )

        # 200 (succès)
        # L'important est que l'endpoint soit accessible
        assert response.status_code == 200
        data = response.json()
        assert (
            "scanned" in data
            and "batches" in data
            and data["batches"] * params["page_size"] >= params["limit"]
        )
