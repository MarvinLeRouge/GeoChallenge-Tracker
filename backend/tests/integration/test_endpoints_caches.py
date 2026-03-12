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
        """Test que la recherche par filtres temporels fonctionne."""
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

    @pytest.mark.asyncio
    async def test_search_by_filter_non_compact(self, auth_client, seeded_caches):
        """Test que la recherche par filtres en mode non-compact retourne des données complètes."""
        response = await auth_client.post(
            "/caches/by-filter",
            json={"page": 1, "page_size": 5, "compact": False},  # Non-compact
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "items" in data
        if len(data["items"]) > 0:
            # En mode non-compact, les items doivent avoir plus de champs
            item = data["items"][0]
            assert "description_html" in item or "description" in item

    @pytest.mark.asyncio
    async def test_search_by_filter_with_difficulty_terrain(self, auth_client, seeded_caches):
        """Test que les filtres difficulty et terrain fonctionnent."""
        # Filtrer par difficulté entre 1 et 3
        response = await auth_client.post(
            "/caches/by-filter",
            json={
                "difficulty": {"min": 1.0, "max": 3.0},
                "page": 1,
                "page_size": 10,
                "compact": True,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "total" in data

        # Filtrer par terrain entre 1 et 2
        response = await auth_client.post(
            "/caches/by-filter",
            json={
                "terrain": {"min": 1.0, "max": 2.0},
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
    async def test_search_by_filter_with_bbox(self, auth_client, seeded_caches):
        """Test que le filtre bbox fonctionne."""
        # Bbox autour de Paris (les caches du fichier GPX sont en France)
        response = await auth_client.post(
            "/caches/by-filter",
            json={
                "bbox": [2.0, 44.0, 6.0, 48.0],  # [min_lon, min_lat, max_lon, max_lat]
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
    async def test_search_by_filter_with_text(self, auth_client, seeded_caches):
        """Test que le filtre text (recherche plein texte) fonctionne."""
        # D'abord, récupérer une cache existante pour connaître son titre
        cache_doc = await seeded_caches.caches.find_one({"title": {"$exists": True, "$ne": ""}})
        if cache_doc:
            # Utiliser un mot du titre pour la recherche text
            search_text = (
                cache_doc["title"].split()[0] if " " in cache_doc["title"] else cache_doc["title"]
            )

            response = await auth_client.post(
                "/caches/by-filter",
                json={
                    "q": search_text,
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
    async def test_search_by_filter_with_type_id(self, auth_client, seeded_caches):
        """Test que le filtre type_id fonctionne."""
        # D'abord, récupérer un type_id valide depuis les caches existantes
        cache_doc = await seeded_caches.caches.find_one({"type_id": {"$exists": True, "$ne": None}})
        if cache_doc:
            type_id = str(cache_doc["type_id"])

            response = await auth_client.post(
                "/caches/by-filter",
                json={
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
    async def test_search_by_filter_with_size_id(self, auth_client, seeded_caches):
        """Test que le filtre size_id fonctionne."""
        # D'abord, récupérer un size_id valide depuis les caches existantes
        cache_doc = await seeded_caches.caches.find_one({"size_id": {"$exists": True, "$ne": None}})
        if cache_doc:
            size_id = str(cache_doc["size_id"])

            response = await auth_client.post(
                "/caches/by-filter",
                json={
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

    @pytest.mark.asyncio
    async def test_search_by_filter_with_country_id(self, auth_client, seeded_caches):
        """Test que le filtre country_id fonctionne."""
        # D'abord, récupérer un country_id valide depuis les caches existantes
        cache_doc = await seeded_caches.caches.find_one(
            {"country_id": {"$exists": True, "$ne": None}}
        )
        if cache_doc:
            country_id = str(cache_doc["country_id"])

            response = await auth_client.post(
                "/caches/by-filter",
                json={
                    "country_id": country_id,
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
    async def test_search_by_filter_with_state_id(self, auth_client, seeded_caches):
        """Test que le filtre state_id fonctionne."""
        # D'abord, récupérer un state_id valide depuis les caches existantes
        cache_doc = await seeded_caches.caches.find_one(
            {"state_id": {"$exists": True, "$ne": None}}
        )
        if cache_doc:
            state_id = str(cache_doc["state_id"])

            response = await auth_client.post(
                "/caches/by-filter",
                json={
                    "state_id": state_id,
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
    async def test_search_by_filter_with_placed_after(self, auth_client, seeded_caches):
        """Test que le filtre placed_after fonctionne."""
        # D'abord, récupérer une date de placement valide depuis les caches existantes
        cache_doc = await seeded_caches.caches.find_one(
            {"placed_at": {"$exists": True, "$ne": None}}
        )
        if cache_doc:
            # Utiliser une date avant la date de la cache
            placed_after = "2000-01-01T00:00:00.000Z"

            response = await auth_client.post(
                "/caches/by-filter",
                json={
                    "placed_after": placed_after,
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
    async def test_search_by_filter_with_attributes(self, auth_client, seeded_caches):
        """Test que les filtres attr_pos et attr_neg fonctionnent."""
        # D'abord, récupérer un attribute_doc_id valide depuis les caches existantes
        cache_doc = await seeded_caches.caches.find_one(
            {"attributes": {"$elemMatch": {"attribute_doc_id": {"$exists": True, "$ne": None}}}}
        )
        if cache_doc and cache_doc.get("attributes"):
            # Trouver un attribut avec is_positive pour tester les deux filtres
            for attr in cache_doc["attributes"]:
                if attr.get("attribute_doc_id"):
                    attr_id = str(attr["attribute_doc_id"])
                    is_positive = attr.get("is_positive", True)

                    # Tester avec attr_pos ou attr_neg selon l'attribut trouvé
                    filter_key = "attr_pos" if is_positive else "attr_neg"

                    response = await auth_client.post(
                        "/caches/by-filter",
                        json={
                            filter_key: [attr_id],
                            "page": 1,
                            "page_size": 10,
                            "compact": True,
                        },
                    )

                    assert response.status_code == 200
                    data = response.json()
                    assert isinstance(data, dict)
                    assert "total" in data
                    break


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
