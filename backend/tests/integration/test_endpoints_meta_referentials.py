"""
Tests d'intégration pour les endpoints de base.

Organisation par tags Swagger :
- Meta : /health, /version, /info
- Referentials : /cache_types, /cache_sizes

Ces tests vérifient :
- Que les routes meta et referentials fonctionnent
"""

import pytest

# =============================================================================
# TAG: META - Health, Version, Info
# =============================================================================


class TestMetaEndpoints:
    """Tests des endpoints Meta (health, version, info)."""

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        """Test que /health répond (même si DB indisponible)."""
        response = await client.get("/health")

        # Doit répondre (200 ou 503 si DB down)
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data

    @pytest.mark.asyncio
    async def test_version_endpoint(self, client):
        """Test que /version répond."""
        response = await client.get("/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    @pytest.mark.asyncio
    async def test_info_endpoint(self, client):
        """Test que /info répond avec les informations de l'API."""
        response = await client.get("/info")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "documentation" in data


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestBasicPerformance:
    """Tests de performance basiques."""

    @pytest.mark.asyncio
    async def test_health_endpoint_response_time(self, client):
        """Test que /health répond en < 1 seconde."""
        import time

        start = time.time()
        response = await client.get("/health")
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Health endpoint took {elapsed:.2f}s (> 1s)"
        assert response.status_code in [200, 503]

    @pytest.mark.asyncio
    async def test_version_endpoint_response_time(self, client):
        """Test que /version répond en < 100ms."""
        import time

        start = time.time()
        response = await client.get("/version")
        elapsed = time.time() - start

        assert elapsed < 0.1, f"Version endpoint took {elapsed:.2f}s (> 100ms)"
        assert response.status_code == 200


# =============================================================================
# TAG: REFERENTIALS - Cache Types, Cache Sizes
# =============================================================================


class TestReferentialEndpoints:
    """Tests des endpoints Referentials (cache_types, cache_sizes)."""

    @pytest.mark.asyncio
    async def test_cache_types_endpoint(self, client):
        """Test que /cache_types répond."""
        response = await client.get("/cache_types")

        # Doit retourner 200 avec une liste
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_cache_sizes_endpoint(self, client):
        """Test que /cache_sizes répond."""
        response = await client.get("/cache_sizes")

        # Doit retourner 200 avec une liste
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
