"""
Tests d'intégration pour les endpoints de base.

Organisation par tags Swagger :

Ces tests vérifient :
- Que les routes API authentifiées fonctionnent
"""

from unittest.mock import AsyncMock, patch

import pytest

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
# TAG: MAINTENANCE - Test email endpoint
# =============================================================================


class TestMaintenanceTestEmail:
    """Tests for the POST /maintenance/test-email admin endpoint."""

    @pytest.mark.asyncio
    async def test_sends_test_email(self, auth_client, seeded_admin):
        """Test that the endpoint sends an email and returns stats."""
        with patch(
            "app.api.routes.maintenance.send_test_email", new_callable=AsyncMock
        ) as mock_send:
            mock_send.return_value = None
            response = await auth_client.post("/maintenance/test-email?to_email=test@example.com")

        assert response.status_code == 200
        data = response.json()
        assert "test@example.com" in data["message"]
        assert "stats" in data
        assert "users" in data["stats"]
        assert "caches" in data["stats"]
        assert "challenges" in data["stats"]
        mock_send.assert_called_once()

    @pytest.mark.asyncio
    async def test_requires_authentication(self, client):
        """Test that the endpoint rejects unauthenticated requests."""
        response = await client.post("/maintenance/test-email?to_email=test@example.com")
        assert response.status_code == 401
