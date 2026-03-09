"""
Fixtures pour tests d'intégration.

Ces fixtures :
- Utilisent la DB de test (geoChallenge_Tracker_TEST)
- Nettoyent les collections avant/après chaque test
- Fournissent un client HTTP de test
- Gèrent l'authentification pour les tests
"""

import os
from pathlib import Path

# Charger les variables d'environnement depuis la RACINE du projet
root_dir = Path(__file__).resolve().parents[2]  # Remonte à la racine
env_file = root_dir / ".env"

from dotenv import load_dotenv  # noqa: E402

load_dotenv(env_file)

# Set TEST_MODE to skip lifespan initialization (populate_mapping, ensure_indexes)
# This avoids event loop issues with Motor during tests
os.environ["TEST_MODE"] = "true"

# Override MONGODB_DB to use test database BEFORE importing app
# This ensures the app uses geoChallenge_Tracker_TEST instead of geoChallenge_Tracker
# Only add _TEST suffix if not already present
original_db = os.environ.get("MONGODB_DB", "geoChallenge_Tracker")
if not original_db.endswith("_TEST"):
    os.environ["MONGODB_DB"] = f"{original_db}_TEST"

# NOW import app and other modules after env vars are set
from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402
from bson import ObjectId  # noqa: E402

from app.core.security import create_access_token, hash_password  # noqa: E402

# Import app last to ensure it picks up the modified env vars
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def verify_test_database(test_settings):
    """
    Sécurité : vérifie qu'on est bien sur une DB de test.
    Bloque l'exécution si la DB ne finit pas par _TEST.
    """
    if not test_settings.mongodb_db.endswith("_TEST"):
        pytest.exit(
            f"ERREUR CRITIQUE : Tests lancés sur '{test_settings.mongodb_db}' "
            f"qui n'est PAS une base de test (_TEST manquant). "
            f"Exécution bloquée pour éviter de corrompre les données de production.",
            returncode=1,
        )

    # Afficher la DB utilisée pour confirmation
    print(f"\n✓ Tests s'exécutent sur la base : {test_settings.mongodb_db}")


@pytest.fixture(scope="session")
def test_settings():
    """Return test settings from environment."""
    from app.core.settings import get_settings

    return get_settings()


@pytest.fixture(scope="session")
def test_db_url(test_settings):
    """Return MongoDB test database URL."""
    # La DB de test est {MONGODB_DB}_TEST
    return test_settings.mongodb_uri


# =============================================================================
# DATABASE FIXTURES
# =============================================================================


@pytest.fixture(scope="function", autouse=True)
async def reset_db_client():
    """Force la réinitialisation du client MongoDB avant chaque test."""
    import app.db.mongodb as mongodb_module

    # Fermer l'ancien client s'il existe
    if mongodb_module._client is not None:
        mongodb_module._client.close()
        mongodb_module._client = None
        mongodb_module._db = None

    yield

    # Cleanup après le test
    if mongodb_module._client is not None:
        mongodb_module._client.close()
        mongodb_module._client = None
        mongodb_module._db = None


@pytest.fixture(scope="function")
async def mongo_client(test_db_url):
    """Create MongoDB client for test database."""

    # Get the current running event loop and configure Motor to use it
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(test_db_url)
    yield client
    client.close()


@pytest.fixture(scope="function")
def test_db(mongo_client, test_settings):
    """Get test database connection."""
    db = mongo_client[test_settings.mongodb_db]
    yield db


@pytest.fixture
async def clean_collections(test_db):
    """
    Clean all test collections before each test.

    Keeps referential data (cache_types, cache_sizes, etc.) but clears
    user-generated data (users, caches, challenges, etc.).
    """
    # Collections à nettoyer (données utilisateurs)
    test_collections = [
        "users",
        "caches",
        "found_caches",
        "challenges",
        "user_challenges",
        "user_challenge_tasks",
        "progress",
        "targets",
        "api_quotas",
    ]

    for coll_name in test_collections:
        # Supprimer tous les documents sauf l'admin de test
        if coll_name == "users":
            await test_db[coll_name].delete_many({"username": {"$ne": "testadmin"}})
        else:
            await test_db[coll_name].delete_many({})

    yield test_db


@pytest.fixture
async def seeded_db(clean_collections, test_db):
    """
    Database with test seeds (admin user, referentials).

    Use this fixture when tests need:
    - Admin user for authentication
    - Referential data (cache types, sizes, etc.)
    """
    from datetime import datetime

    # Vérifier que l'admin de test existe
    admin = await test_db.users.find_one({"username": "testadmin"})

    if not admin:
        # Créer l'admin de test
        await test_db.users.insert_one(
            {
                "_id": ObjectId("507f1f77bcf86cd799439011"),
                "username": "testadmin",
                "email": "testadmin@test.local",
                "password_hash": hash_password("Test123!"),
                "role": "admin",
                "is_verified": True,
                "is_active": True,
                "created_at": datetime.utcnow(),
            }
        )

    yield test_db


# =============================================================================
# HTTP CLIENT FIXTURES
# =============================================================================


@pytest.fixture
async def client():
    """
    Create async HTTP client for testing.

    Uses httpx.AsyncClient with ASGI transport for proper async handling.
    """
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def auth_client(admin_token):
    """
    Create authenticated async HTTP client.

    Returns a client with valid JWT token for test admin user.
    """
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        c.headers["Authorization"] = f"Bearer {admin_token}"
        yield c


# =============================================================================
# AUTHENTICATION FIXTURES
# =============================================================================


@pytest.fixture
def admin_token():
    """Create access token for test admin user."""
    return create_access_token(data={"sub": str(ObjectId("507f1f77bcf86cd799439011"))})


@pytest.fixture
def auth_headers(admin_token):
    """Return authorization headers with admin token."""
    return {"Authorization": f"Bearer {admin_token}"}


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================


@pytest.fixture
def sample_cache_data():
    """Return sample cache data for tests."""
    return {
        "GC": "GC_TEST_001",
        "title": "Test Cache",
        "description_html": "<p>Test description</p>",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "difficulty": 2.5,
        "terrain": 3.0,
        "type_id": None,  # Will be set from referential
        "size_id": None,  # Will be set from referential
    }


@pytest.fixture
def sample_user_data():
    """Return sample user data for tests."""
    import uuid

    unique_id = str(uuid.uuid4())[:8]

    return {
        "username": f"testuser_{unique_id}",
        "email": f"test_{unique_id}@test.local",
        "password": "Test123!",
    }


# =============================================================================
# UTILITY FIXTURES
# =============================================================================


@pytest.fixture
def test_object_id():
    """Generate a test ObjectId."""
    return ObjectId()


@pytest.fixture
def test_datetime():
    """Get current datetime from MongoDB."""
    from datetime import datetime

    return datetime.utcnow()


@pytest.fixture(autouse=True)
def mock_send_verification_email():
    """Mock l'envoi d'emails pendant les tests."""
    with patch("app.api.routes.auth.send_verification_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = None
        yield mock_send
