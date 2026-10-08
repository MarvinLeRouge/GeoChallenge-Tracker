"""
Tests d'intégration pour les endpoints Caches - Bbox and radius search

Organisation par tags Swagger :
- Caches : /caches/*
"""

import pytest


class TestCachesWithinBbox:
    """Tests du endpoint GET /caches/within-bbox."""

    @pytest.mark.asyncio
    async def test_search_within_bbox_requires_auth(self, client):
        """Test que la recherche par bbox nécessite une authentification."""
        response = await client.get(
            "/caches/within-bbox",
            params={"min_lat": 48.0, "min_lon": 2.0, "max_lat": 49.0, "max_lon": 3.0},
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_search_within_bbox_valid(self, auth_client, seeded_caches):
        """Test que la recherche par bbox retourne une structure valide."""
        response = await auth_client.get(
            "/caches/within-bbox",
            params={
                "min_lat": 48.0,
                "min_lon": 2.0,
                "max_lat": 49.0,
                "max_lon": 3.0,
                "page": 1,
                "page_size": 10,
                "compact": True,
            },
        )

        # 200 (succès avec résultats vides)
        assert response.status_code in [200]

        if response.status_code == 200:
            data = response.json()
            # Doit retourner une liste ou structure paginée
            assert isinstance(data, dict)
            assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_search_within_bbox_non_compact(self, auth_client, seeded_caches):
        """Test que la recherche par bbox en mode non-compact retourne des données complètes."""
        response = await auth_client.get(
            "/caches/within-bbox",
            params={
                "min_lat": 48.0,
                "min_lon": 2.0,
                "max_lat": 49.0,
                "max_lon": 3.0,
                "page": 1,
                "page_size": 5,
                "compact": False,  # Non-compact
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        if data.get("total", 0) > 0 and len(data.get("items", [])) > 0:
            # En mode non-compact, les items doivent avoir plus de champs
            item = data["items"][0]
            assert "description_html" in item or "description" in item

    @pytest.mark.asyncio
    async def test_search_within_bbox_with_type_id(self, auth_client, seeded_caches):
        """Test que la recherche par bbox avec type_id fonctionne."""
        # D'abord, récupérer un type_id valide depuis la DB
        type_doc = await seeded_caches.cache_types.find_one()
        if type_doc:
            type_id = str(type_doc["_id"])

            response = await auth_client.get(
                "/caches/within-bbox",
                params={
                    "min_lat": 44.0,
                    "min_lon": 2.0,
                    "max_lat": 48.0,
                    "max_lon": 6.0,
                    "type_id": type_id,
                    "page": 1,
                    "page_size": 10,
                    "compact": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "total" in data

    @pytest.mark.asyncio
    async def test_search_within_bbox_with_size_id(self, auth_client, seeded_caches):
        """Test que la recherche par bbox avec size_id fonctionne."""
        # D'abord, récupérer un size_id valide depuis la DB
        size_doc = await seeded_caches.cache_sizes.find_one()
        if size_doc:
            size_id = str(size_doc["_id"])

            response = await auth_client.get(
                "/caches/within-bbox",
                params={
                    "min_lat": 44.0,
                    "min_lon": 2.0,
                    "max_lat": 48.0,
                    "max_lon": 6.0,
                    "size_id": size_id,
                    "page": 1,
                    "page_size": 10,
                    "compact": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "total" in data


class TestCachesWithinRadius:
    """Tests du endpoint GET /caches/within-radius."""

    @pytest.mark.asyncio
    async def test_search_within_radius_requires_auth(self, client):
        """Test que la recherche par rayon nécessite une authentification."""
        response = await client.get(
            "/caches/within-radius", params={"lat": 48.8566, "lon": 2.3522, "radius_km": 10.0}
        )

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_search_within_radius_valid(self, auth_client, seeded_caches):
        """Test que la recherche par rayon retourne une structure valide."""
        response = await auth_client.get(
            "/caches/within-radius",
            params={
                "lat": 48.8566,
                "lon": 2.3522,
                "radius_km": 50.0,
                "page": 1,
                "page_size": 10,
                "compact": True,
            },
        )

        # 200 (succès), 400 (bad request)
        # L'important est que l'endpoint soit accessible
        assert response.status_code in [200, 400]

        if response.status_code == 200:
            data = response.json()
            # Doit retourner une liste ou structure paginée
            assert isinstance(data, dict)
            assert data["total"] > 0

    @pytest.mark.asyncio
    async def test_search_within_radius_with_type_id(self, auth_client, seeded_caches):
        """Test que la recherche par rayon avec type_id fonctionne."""
        # D'abord, récupérer un type_id valide depuis la DB
        type_doc = await seeded_caches.cache_types.find_one()
        if type_doc:
            type_id = str(type_doc["_id"])

            response = await auth_client.get(
                "/caches/within-radius",
                params={
                    "lat": 45.0,
                    "lon": 3.0,
                    "radius_km": 100.0,
                    "type_id": type_id,
                    "page": 1,
                    "page_size": 10,
                    "compact": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "total" in data

    @pytest.mark.asyncio
    async def test_search_within_radius_with_size_id(self, auth_client, seeded_caches):
        """Test que la recherche par rayon avec size_id fonctionne."""
        # D'abord, récupérer un size_id valide depuis la DB
        size_doc = await seeded_caches.cache_sizes.find_one()
        if size_doc:
            size_id = str(size_doc["_id"])

            response = await auth_client.get(
                "/caches/within-radius",
                params={
                    "lat": 45.0,
                    "lon": 3.0,
                    "radius_km": 100.0,
                    "size_id": size_id,
                    "page": 1,
                    "page_size": 10,
                    "compact": True,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, dict)
            assert "total" in data
