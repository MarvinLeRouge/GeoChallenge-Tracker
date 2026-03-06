"""
Tests d'intégration pour les endpoints de base.

Organisation par tags Swagger :
- Meta : /health, /version, /info
- Referentials : /cache_types, /cache_sizes

Ces tests vérifient :
- Que l'API répond correctement
- Que la DB de test est accessible
- Que l'authentification fonctionne
"""

import pytest

# =============================================================================
# TAG: META - Health, Version, Info
# =============================================================================


class TestMetaEndpoints:
    """Tests des endpoints Meta (health, version, info)."""

    def test_health_endpoint(self, client):
        """Test que /health répond (même si DB indisponible)."""
        response = client.get("/health")

        # Doit répondre (200 ou 503 si DB down)
        assert response.status_code in [200, 503]
        data = response.json()
        assert "status" in data
        assert "checks" in data

    def test_version_endpoint(self, client):
        """Test que /version répond."""
        response = client.get("/version")

        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert isinstance(data["version"], str)

    def test_info_endpoint(self, client):
        """Test que /info répond avec les informations de l'API."""
        response = client.get("/info")

        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "documentation" in data


# =============================================================================
# TAG: REFERENTIALS - Cache Types, Cache Sizes
# =============================================================================


class TestReferentialEndpoints:
    """Tests des endpoints Referentials (cache_types, cache_sizes)."""

    def test_cache_types_endpoint(self, client):
        """Test que /cache_types répond."""
        response = client.get("/cache_types")

        # Peut être 200 (si DB connectée) ou 500 (si DB down)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)

    def test_cache_sizes_endpoint(self, client):
        """Test que /cache_sizes répond."""
        response = client.get("/cache_sizes")

        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)


# =============================================================================
# TAG: AUTH - Authentication Endpoints
# =============================================================================


class TestAuthEndpoints:
    """Tests des endpoints d'authentification."""

    def test_login_with_test_admin(self, client, seeded_db):
        """Test que l'admin de test peut se logger."""
        response = client.post(
            "/auth/login", data={"username": "testadmin", "password": "Test123!"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_login_with_invalid_credentials(self, client):
        """Test que des credentials invalides échouent."""
        response = client.post(
            "/auth/login", data={"username": "testadmin", "password": "WrongPassword"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "detail" in data

    def test_register_new_user(self, client, clean_collections):
        """Test qu'on peut enregistrer un nouvel utilisateur."""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        user_data = {
            "username": f"newuser_{unique_id}",
            "email": f"newuser_{unique_id}@example.com",
            "password": "NewUser123!",
        }

        response = client.post("/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert "email" in data
        assert data["email"] == user_data["email"]

    def test_register_duplicate_email(self, client, clean_collections):
        """Test qu'on ne peut pas créer deux users avec le même email."""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        user_data = {
            "username": f"user_{unique_id}",
            "email": f"dup_{unique_id}@example.com",
            "password": "Test123!",
        }

        # Première inscription
        response1 = client.post("/auth/register", json=user_data)
        assert response1.status_code == 201

        # Doublon
        response2 = client.post("/auth/register", json=user_data)
        assert response2.status_code == 400


# =============================================================================
# TAG: MY-CHALLENGES - Authenticated Endpoints
# =============================================================================


class TestAuthenticatedEndpoints:
    """Tests des endpoints nécessitant une authentification."""

    def test_my_profile_with_valid_token(self, auth_client):
        """Test que /my/profile répond avec un token valide."""
        response = auth_client.get("/my/profile")

        assert response.status_code == 200
        data = response.json()
        assert "email" in data
        assert "username" in data

    def test_my_profile_without_token(self, client):
        """Test que /my/profile échoue sans token."""
        response = client.get("/my/profile")

        assert response.status_code == 401

    def test_my_challenges_sync(self, auth_client, clean_collections):
        """Test que /my/challenges/sync fonctionne."""
        response = auth_client.post("/my/challenges/sync")

        # Peut être 200 ou 201 selon l'implémentation
        assert response.status_code in [200, 201]
        data = response.json()
        assert isinstance(data, dict)

    def test_user_challenges_list(self, auth_client):
        """Test que /my/challenges répond."""
        response = auth_client.get("/my/challenges")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert "items" in data or isinstance(data, list)


# =============================================================================
# DATABASE CONNECTIVITY TESTS
# =============================================================================


class TestDatabaseConnectivity:
    """Tests de connectivité à la DB de test."""

    @pytest.mark.asyncio
    async def test_test_db_is_accessible(self, test_db):
        """Test que la DB de test est accessible."""
        # Lister les collections
        collections = await test_db.list_collection_names()

        assert len(collections) > 0
        assert "users" in collections
        assert "caches" in collections

    @pytest.mark.asyncio
    async def test_test_db_has_referentials(self, test_db):
        """Test que les référentiels sont présents."""
        referential_collections = [
            "cache_types",
            "cache_sizes",
            "cache_attributes",
            "countries",
            "states",
        ]

        for coll_name in referential_collections:
            count = await test_db[coll_name].count_documents({})
            assert count > 0, f"Referential {coll_name} is empty"

    @pytest.mark.asyncio
    async def test_test_db_has_test_admin(self, test_db):
        """Test que l'admin de test existe."""
        admin = await test_db.users.find_one({"username": "testadmin"})

        assert admin is not None
        assert admin["email"].endswith("@test.local")
        assert admin["role"] == "admin"

    @pytest.mark.asyncio
    async def test_test_db_is_isolated(self, test_db, test_settings):
        """Test que la DB de test est différente de la prod."""
        # Vérifier que le nom de la DB contient _TEST
        assert test_settings.mongodb_db.endswith("_TEST")

        # Compter les users (devrait être < prod car anonymisés)
        user_count = await test_db.users.count_documents({})
        assert user_count > 0  # Au moins l'admin de test


# =============================================================================
# PERFORMANCE TESTS
# =============================================================================


class TestBasicPerformance:
    """Tests de performance basiques."""

    def test_health_endpoint_response_time(self, client):
        """Test que /health répond en < 1 seconde."""
        import time

        start = time.time()
        response = client.get("/health")
        elapsed = time.time() - start

        assert elapsed < 1.0, f"Health endpoint took {elapsed:.2f}s (> 1s)"
        assert response.status_code in [200, 503]

    def test_version_endpoint_response_time(self, client):
        """Test que /version répond en < 100ms."""
        import time

        start = time.time()
        response = client.get("/version")
        elapsed = time.time() - start

        assert elapsed < 0.1, f"Version endpoint took {elapsed:.2f}s (> 100ms)"
        assert response.status_code == 200
