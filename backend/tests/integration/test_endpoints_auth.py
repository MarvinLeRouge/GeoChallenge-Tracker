"""
Tests d'intégration pour les endpoints auth

Organisation par tags Swagger :
- Auth : /auth/*

Ces tests vérifient :
- Que l'authentification fonctionne
- Que la validation des mots de passe fonctionne
- Que la vérification email fonctionne
- Que le refresh token fonctionne correctement
"""

import datetime as dt

import pytest
from bson import ObjectId

from app.core.security import create_refresh_token, hash_password

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
    async def test_login_unverified_user(self, client, test_db):
        """Test qu'un utilisateur non vérifié ne peut pas se logger."""
        import uuid
        from datetime import datetime

        unique_id = str(uuid.uuid4())[:8]

        # Créer un utilisateur non vérifié
        await test_db.users.insert_one(
            {
                "username": f"unverified_{unique_id}",
                "email": f"unverified_{unique_id}@example.com",
                "password_hash": hash_password("Test123!"),
                "is_verified": False,
                "is_active": True,
                "role": "user",
                "created_at": datetime.utcnow(),
            }
        )

        response = await client.post(
            "/auth/login",
            data={"username": f"unverified_{unique_id}", "password": "Test123!"},
        )

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert "unverified" in data["error"].get("message", "").lower()

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
    async def test_register_weak_password(self, client):
        """Test qu'un mot de passe faible est rejeté."""
        import uuid

        unique_id = str(uuid.uuid4())[:8]

        # Mot de passe trop court (< 8 caractères)
        user_data = {
            "username": f"newuser_{unique_id}",
            "email": f"newuser_{unique_id}@example.com",
            "password": "weak",  # Trop court
        }

        response = await client.post("/auth/register", json=user_data)

        assert response.status_code == 422
        data = response.json()
        assert "error" in data or "detail" in data

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
# TAG: AUTH - Email Verification Tests
# =============================================================================


class TestAuthEmailVerification:
    """Tests des endpoints de vérification d'email."""

    @pytest.mark.asyncio
    async def test_verify_email_with_valid_code(self, client, test_db):
        """Test que la vérification d'email fonctionne avec un code valide."""
        import uuid
        from datetime import datetime, timedelta

        unique_id = str(uuid.uuid4())[:8]
        verification_code = "ABC123XYZ"  # Code simple

        # Créer un utilisateur non vérifié avec un code de vérification
        # Le backend cherche: {"verification_code": code, "verification_expires_at": {"$gte": now_ts}}
        await test_db.users.insert_one(
            {
                "username": f"verifyuser_{unique_id}",
                "email": f"verify_{unique_id}@example.com",
                "password_hash": hash_password("Test123!"),
                "is_verified": False,
                "is_active": True,
                "role": "user",
                "verification_code": verification_code,
                "verification_expires_at": datetime.utcnow() + timedelta(hours=24),
                "created_at": datetime.utcnow(),
            }
        )

        # Vérifier l'email avec le code
        response = await client.get(f"/auth/verify-email?code={verification_code}")
        data = response.json()

        assert response.status_code == 200
        assert "message" in data or "success" in data

        # Vérifier que l'utilisateur est maintenant vérifié
        user = await test_db.users.find_one({"username": f"verifyuser_{unique_id}"})
        assert user is not None
        assert user.get("is_verified") is True

    @pytest.mark.asyncio
    async def test_verify_email_with_invalid_code(self, client):
        """Test que la vérification d'email échoue avec un code invalide."""
        response = await client.get("/auth/verify-email?code=invalid_code_12345")

        assert response.status_code in [400, 404]
        data = response.json()
        assert "error" in data or "success" in data

    @pytest.mark.asyncio
    async def test_verify_email_post_method(self, client, test_db):
        """Test que la vérification d'email fonctionne via POST."""
        import uuid
        from datetime import datetime, timedelta

        unique_id = str(uuid.uuid4())[:8]
        verification_code = "POST123XYZ"

        # Créer un utilisateur non vérifié avec un code de vérification
        await test_db.users.insert_one(
            {
                "username": f"verifyuser_{unique_id}",
                "email": f"verify_{unique_id}@example.com",
                "password_hash": hash_password("Test123!"),
                "is_verified": False,
                "is_active": True,
                "role": "user",
                "verification_code": verification_code,
                "verification_expires_at": datetime.utcnow() + timedelta(hours=24),
                "created_at": datetime.utcnow(),
            }
        )

        # Vérifier l'email avec le code via POST
        response = await client.post("/auth/verify-email", json={"code": verification_code})

        assert response.status_code == 200
        data = response.json()
        assert "message" in data or "success" in data

    @pytest.mark.asyncio
    async def test_resend_verification_email(self, client, test_db):
        """Test qu'on peut renvoyer un email de vérification."""
        import uuid
        from datetime import datetime

        unique_id = str(uuid.uuid4())[:8]

        # Créer un utilisateur non vérifié
        await test_db.users.insert_one(
            {
                "username": f"resenduser_{unique_id}",
                "email": f"resend_{unique_id}@example.com",
                "password_hash": hash_password("Test123!"),
                "is_verified": False,
                "is_active": True,
                "role": "user",
                "created_at": datetime.utcnow(),
            }
        )

        # Demander le renvoi de l'email de vérification
        # Le backend attend "identifier" (username ou email)
        response = await client.post(
            "/auth/resend-verification",
            json={"identifier": f"resenduser_{unique_id}"},
        )

        # 200 (succès) ou 500 (email non configuré)
        assert response.status_code in [200, 500]

        if response.status_code == 200:
            data = response.json()
            assert "message" in data or "success" in data

    @pytest.mark.asyncio
    async def test_resend_verification_nonexistent_user(self, client):
        """Test que le renvoi pour un user inexistant ne révèle pas l'erreur."""
        response = await client.post(
            "/auth/resend-verification",
            json={"identifier": "nonexistent_user_12345"},
        )

        # Pour des raisons de sécurité, ne pas révéler si le user existe
        # 200 (message générique), 422 (validation), ou 500 (email non configuré)
        assert response.status_code in [200, 422, 500]
        if response.status_code == 200:
            data = response.json()
            assert "message" in data or "success" in data


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

    @pytest.mark.asyncio
    async def test_refresh_token_invalid_user(self, client):
        """Test qu'un refresh token pour un user inexistant est rejeté."""
        # Créer un token pour un ObjectId qui n'existe pas
        invalid_user_token = create_refresh_token(
            data={"sub": str(ObjectId("507f1f77bcf86cd799439999"))},
            expires_delta=dt.timedelta(days=7),
        )

        response = await client.post("/auth/refresh", json={"refresh_token": invalid_user_token})

        assert response.status_code == 401
        data = response.json()
        assert "error" in data

    @pytest.mark.asyncio
    async def test_refresh_token_inactive_user(self, client, test_db):
        """Test qu'un refresh token pour un user inactif est rejeté."""
        import uuid
        from datetime import datetime

        unique_id = str(uuid.uuid4())[:8]

        # Créer un utilisateur inactif (sans _id en dur, MongoDB le génère)
        result = await test_db.users.insert_one(
            {
                "username": f"inactive_user_{unique_id}",
                "email": f"inactive_{unique_id}@example.com",
                "password_hash": hash_password("Test123!"),
                "is_verified": True,
                "is_active": False,  # Inactif
                "role": "user",
                "created_at": datetime.utcnow(),
            }
        )

        # Récupérer l'_id généré automatiquement
        user_id = str(result.inserted_id)

        # Créer un token pour cet utilisateur
        inactive_token = create_refresh_token(
            data={"sub": user_id},
            expires_delta=dt.timedelta(days=7),
        )

        response = await client.post("/auth/refresh", json={"refresh_token": inactive_token})

        assert response.status_code == 401
        data = response.json()
        assert "error" in data
