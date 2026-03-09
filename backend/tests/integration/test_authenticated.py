"""
Tests d'intégration pour les endpoints de base.

Organisation par tags Swagger :

Ces tests vérifient :
- Que les routes API authentifiées fonctionnent
"""


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
