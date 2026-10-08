"""
Tests d'intégration pour les endpoints Caches - Search by filter

Organisation par tags Swagger :
- Caches : /caches/*
"""

import pytest


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
