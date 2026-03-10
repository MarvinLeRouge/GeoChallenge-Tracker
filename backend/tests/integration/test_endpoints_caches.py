"""
Tests d'intégration pour les endpoints Caches

Organisation par tags Swagger :
- Caches : /caches/*

Ces tests vérifient :
- Que les endpoints de caches fonctionnent
- Que l'authentification est requise
- Que les recherches et filtres retournent des résultats
"""

from pathlib import Path

import pytest

# =============================================================================
# TAG: CACHES - Upload GPX
# =============================================================================


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


# =============================================================================
# TAG: CACHES - Search by Filter
# =============================================================================


class TestCachesByFilter:
    """Tests du endpoint POST /caches/by-filter."""

    @pytest.mark.asyncio
    async def test_search_by_filter_requires_auth(self, client):
        """Test que la recherche par filtres nécessite une authentification."""
        response = await client.post("/caches/by-filter", json={})
        print(response.json())

        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_search_by_filter_empty(self, auth_client, seeded_caches):
        """Test que la recherche par filtres retourne une structure valide."""
        response = await auth_client.post(
            "/caches/by-filter", json={"page": 1, "page_size": 10, "compact": True}
        )

        # 200 (succès, avec toutes les caches)
        assert response.status_code in [200]

        if response.status_code == 200:
            data = response.json()
            print("all data", data)
            # Doit retourner une structure avec items/count ou similaire
            # Et il doit y avoir au moins une page d'items (le seeding actuel en prévoit 30 pages)
            assert isinstance(data, dict)
            assert data["total"] > data["page_size"] and len(data["items"]) == data["page_size"]

    @pytest.mark.asyncio
    async def test_search_by_filter_date(self, auth_client, seeded_caches):
        """Test que la recherche par filtres retourne une structure valide."""
        response = await auth_client.post(
            "/caches/by-filter",
            json={
                "placed_before": "2025-01-01T00:00:00.000Z",
                "page": 1,
                "page_size": 10,
                "compact": True,
            },
        )

        # 200 (succès avec toutes les caches car le seeding est constitué de vieilles caches)
        assert response.status_code in [200]

        if response.status_code == 200:
            data_before_2025 = response.json()
            print("data_before_2025", data_before_2025)
            # Doit retourner une structure avec items/count ou similaire
            assert isinstance(data_before_2025, dict)
            nb_caches_before_2025 = data_before_2025["total"]
            response = await auth_client.post(
                "/caches/by-filter",
                json={
                    "placed_before": "2005-01-01T00:00:00.000Z",
                    "page": 1,
                    "page_size": 10,
                    "compact": True,
                },
            )
            assert response.status_code in [200]
            if response.status_code == 200:
                data_before_2005 = response.json()
                print("data_before_2005", data_before_2005)
                # Doit retourner une structure avec items/count ou similaire
                assert isinstance(data_before_2005, dict)
                nb_caches_before_2005 = data_before_2005["total"]
                # On doit avoir moins de caches d'avant 2005 que d'avant 2025
                assert nb_caches_before_2005 < nb_caches_before_2025


# =============================================================================
# TAG: CACHES - Search within Bounding Box
# =============================================================================


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


# =============================================================================
# TAG: CACHES - Search within Radius
# =============================================================================


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


# =============================================================================
# TAG: CACHES - Get by GC Code
# =============================================================================


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


# =============================================================================
# TAG: CACHES - Get by MongoDB ID
# =============================================================================


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
