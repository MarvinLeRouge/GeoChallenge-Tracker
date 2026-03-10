"""
Tests d'intégration pour les endpoints auth

Organisation par tags Swagger :
- Auth : /auth/*

Ces tests vérifient :
- Que l'authentification fonctionne
"""

import datetime as dt

import pytest
from bson import ObjectId

from app.core.security import create_refresh_token

# =============================================================================
# TAG: AUTH - Authentication Endpoints
# =============================================================================


class TestAuthEndpoints:
    """Tests des endpoints d'authentification."""

    @pytest.mark.asyncio
    async def test_login_with_test_admin(self, client, seeded_admin):
        """Test que l'admin de test peut se logger."""
        response = await client.post(
            "/auth/login", data={"username": "testadmin", "password": "Test123!"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_with_invalid_credentials(self, client):
        """Test que des credentials invalides échouent."""
        response = await client.post(
            "/auth/login", data={"username": "testadmin", "password": "WrongPassword"}
        )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "HTTP_401"
        assert "message" in data["error"]

    @pytest.mark.asyncio
    async def test_register_new_user(self, client):
        """Test qu'on peut enregistrer un nouvel utilisateur."""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        user_data = {
            "username": f"newuser_{unique_id}",
            "email": f"newuser_{unique_id}@example.com",
            "password": "NewUser123!",
        }

        response = await client.post("/auth/register", json=user_data)

        assert response.status_code == 201
        data = response.json()
        assert "email" in data
        assert data["email"] == user_data["email"]

    @pytest.mark.asyncio
    async def test_register_duplicate_email(self, client):
        """Test qu'on ne peut pas créer deux users avec le même email."""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        user_data = {
            "username": f"user_{unique_id}",
            "email": f"dup_{unique_id}@example.com",
            "password": "Test123!",
        }

        # Première inscription
        response1 = await client.post("/auth/register", json=user_data)
        assert response1.status_code == 201

        # Doublon
        response2 = await client.post("/auth/register", json=user_data)
        assert response2.status_code == 409


# =============================================================================
# TAG: AUTH - Refresh Token Tests
# =============================================================================


class TestAuthRefreshToken:
    """Tests des endpoints de refresh token."""

    @pytest.mark.asyncio
    async def test_refresh_token_valid(self, client, seeded_admin):
        """Test qu'un refresh token valide génère un nouvel access token."""
        # D'abord, se connecter pour obtenir un refresh token
        login_response = await client.post(
            "/auth/login", data={"username": "testadmin", "password": "Test123!"}
        )
        assert login_response.status_code == 200
        refresh_token = login_response.json()["refresh_token"]

        # Utiliser le refresh token
        response = await client.post("/auth/refresh", json={"refresh_token": refresh_token})

        assert response.status_code == 200
        body = response.json()
        assert "access_token" in body
        assert body["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_signature(self, client):
        """Test qu'un refresh token falsifié est rejeté."""
        fake_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.abc.def"
        response = await client.post("/auth/refresh", json={"refresh_token": fake_token})

        assert response.status_code == 401
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_refresh_token_expired(self, client, seeded_admin):
        """Test qu'un refresh token expiré est rejeté."""
        # Créer un token expiré pour l'admin de test
        expired_token = create_refresh_token(
            data={"sub": str(ObjectId("507f1f77bcf86cd799439011"))},
            expires_delta=dt.timedelta(days=-30),  # Déjà expiré
        )

        response = await client.post("/auth/refresh", json={"refresh_token": expired_token})

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
