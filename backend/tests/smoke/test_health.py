"""Tests de santé rapide pour CI/CD.

Ces tests doivent :
- Être très rapides (< 10 secondes total)
- Ne PAS nécessiter de base de données
- Vérifier que l'application peut démarrer
- Être exécutés après chaque build/deploy
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# =============================================================================
# CONFIGURATION CRITIQUE
# =============================================================================


def test_jwt_secret_configured():
    """CRITIQUE: JWT secret key doit être configuré (sécurité auth)."""
    from app.core.settings import get_settings

    settings = get_settings()

    assert settings.jwt_secret_key is not None, "JWT secret key is not configured"
    assert len(settings.jwt_secret_key) > 10, "JWT secret key is too short (min 10 chars)"
    assert settings.jwt_secret_key != "changeme", "JWT secret key must be changed from default"


def test_mongodb_uri_configured():
    """CRITIQUE: MongoDB URI doit être configurée (DB requise)."""
    from app.core.settings import get_settings

    settings = get_settings()

    assert settings.mongodb_uri is not None, "MongoDB URI is not configured"
    assert len(settings.mongodb_uri) > 0, "MongoDB URI is empty"
    assert settings.mongodb_uri.startswith("mongodb"), "MongoDB URI must start with 'mongodb'"


# =============================================================================
# API HEALTH
# =============================================================================


def test_api_health():
    """Test que l'API répond au endpoint /health."""
    response = client.get("/health")

    # /health may return 503 if DB is down, but should respond
    assert response.status_code in [200, 503]
    data = response.json()
    assert "status" in data


def test_version_endpoint():
    """Test que l'endpoint /version répond."""
    response = client.get("/version")

    # Should return version info
    assert response.status_code == 200
    data = response.json()
    assert "version" in data


# =============================================================================
# SETTINGS
# =============================================================================


def test_settings_load():
    """Test que les settings se chargent correctement."""
    from app.core.settings import get_settings

    settings = get_settings()

    assert settings is not None
    assert settings.app_name is not None
    assert len(settings.app_name) > 0
    assert settings.environment in ["development", "production"]
