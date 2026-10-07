"""
Tests d'intégration pour les endpoints Caches - Lookup by GC code or id

Organisation par tags Swagger :
- Caches : /caches/*
"""

import pytest


class TestCachesByGcCode:
    """Tests du endpoint GET /caches/{gc}."""

    @pytest.mark.asyncio
    async def test_get_by_gc_requires_auth(self, client):
        """Test que la récupération par GC nécessite une authentification."""
        response = await client.get("/caches/GC_foo")

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_by_gc_not_found(self, auth_client, seeded_caches):
        """Test que la récupération d'une GC inexistante retourne une erreur."""
        response = await auth_client.get("/caches/GC_NON_EXISTENT")

        # 404 (not found)
        assert response.status_code == 404
        data = response.json()
        assert (
            isinstance(data, dict)
            and "error" in data
            and "code" in data["error"]
            and data["error"]["code"] == "HTTP_404"
        )
        print(data)

    @pytest.mark.asyncio
    async def test_get_by_gc_found(self, auth_client, seeded_caches):
        """Test que la récupération d'une GC existante retourne la cache."""
        response = await auth_client.get("/caches/GCQTP6")

        # 200 (found)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict) and "_id" in data


class TestCachesById:
    """Tests du endpoint GET /caches/by-id/{id}."""

    @pytest.mark.asyncio
    async def test_get_by_id_requires_auth(self, client):
        """Test que la récupération par ID nécessite une authentification."""
        # Utiliser un ObjectId valide mais inexistant
        response = await client.get("/caches/by-id/507f1f77bcf86cd799439011")
        print(response.json())
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_by_id_invalid_format(self, auth_client, seeded_caches):
        """Test que la récupération avec un ID invalide retourne une erreur."""
        response = await auth_client.get("/caches/by-id/invalid_id")

        # 400 (bad request), 404 (not found), ou 422 (validation error)
        # L'important est que l'endpoint soit accessible
        assert response.status_code in [400, 404, 422]
        data = response.json()
        assert (
            isinstance(data, dict)
            and "error" in data
            and "code" in data["error"]
            and data["error"]["code"].startswith("HTTP_4")
        )

    @pytest.mark.asyncio
    async def test_get_by_id_not_found(self, auth_client, seeded_caches):
        """Test que la récupération d'un ID inexistant retourne une erreur."""
        # Utiliser un ObjectId valide mais inexistant
        response = await auth_client.get("/caches/by-id/123456789012345678901234")
        # 404 (not found), 500 (erreur interne), ou autre
        # L'important est que l'endpoint soit accessible
        assert response.status_code in [400, 404]
        data = response.json()
        assert (
            isinstance(data, dict)
            and "error" in data
            and "code" in data["error"]
            and data["error"]["code"].startswith("HTTP_4")
        )

    @pytest.mark.asyncio
    async def test_get_by_id_found(self, auth_client, seeded_caches):
        """Test que la récupération d'un ID inexistant retourne une erreur."""
        # Récupérer UN cache au hasard avec $sample
        pipeline = [{"$sample": {"size": 1}}]
        cursor = seeded_caches.caches.aggregate(pipeline)
        caches = await cursor.to_list(length=1)
        ref = caches[0]
        cache_id = str(ref["_id"])

        # Utiliser un ObjectId valide mais inexistant
        response = await auth_client.get(f"/caches/by-id/{cache_id}")
        # 200 (found)
        assert response.status_code == 200
        cache = response.json()
        assert (
            "GC" in cache
            and "title" in cache
            and ref["GC"] == cache["GC"]
            and ref["title"] == cache["title"]
        )
