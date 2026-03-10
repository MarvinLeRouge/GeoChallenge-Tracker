"""
Fixtures pour tests d'intégration.

- Utilisent la DB de test (geoChallenge_Tracker_TEST)
- Nettoient les collections avant/après chaque test
- Fournissent un client HTTP de test
- Gèrent l'authentification pour les tests
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from bson import ObjectId
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

# noqa: E402 - Imports must come after env setup
from app.core.security import create_access_token, hash_password  # noqa: E402
from app.main import app  # noqa: E402

# Import de ton script de duplication
from tests.utils.duplicate_db_for_tests import duplicate_db_with_indexes  # noqa: E402


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session):
    """
    Hook appelé avant le début de la session pytest.
    Duplique la DB de prod vers la DB de test pour garantir que toutes les collections existent.
    """
    # Vérifier si -s (--capture=no) est activé
    verbose = session.config.getoption("capture") == "no"
    if verbose:
        print("\n🔄 Préparation de la DB de test (duplication)...")
    try:
        asyncio.run(duplicate_db_with_indexes(verbose))
    except Exception as e:
        if verbose:
            print(f"\n❌ ERREUR lors de la duplication de la DB : {e}")
        raise


# =============================================================================
# SESSION LOOP
# =============================================================================
@pytest.fixture(scope="session")
def event_loop():
    """
    Session-scoped event loop for all async fixtures and tests.
    Ensures Motor client and FastAPI share the same loop.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# =============================================================================
# SETTINGS
# =============================================================================
@pytest.fixture(scope="session")
def test_settings():
    from app.core.settings import get_settings

    return get_settings()


@pytest.fixture(scope="session", autouse=True)
def verify_test_database(test_settings):
    if not test_settings.mongodb_db.endswith("_TEST"):
        pytest.exit(
            f"ERREUR CRITIQUE : Tests lancés sur '{test_settings.mongodb_db}' "
            f"qui n'est PAS une base de test (_TEST manquant).",
            returncode=1,
        )
    print(f"\n✓ Tests s'exécutent sur la base : {test_settings.mongodb_db}")


@pytest.fixture(scope="session")
def test_db_url(test_settings):
    return test_settings.mongodb_uri


# =============================================================================
# DATABASE FIXTURES
# =============================================================================
@pytest.fixture(scope="session")
async def mongo_client(test_db_url):
    from motor.motor_asyncio import AsyncIOMotorClient

    client = AsyncIOMotorClient(test_db_url)
    yield client
    client.close()


@pytest.fixture(scope="session")
def test_db(mongo_client, test_settings):
    return mongo_client[test_settings.mongodb_db]


@pytest.fixture(scope="function")
async def seeded_admin(test_db):
    """
    Database seeded with admin user.
    """
    from datetime import datetime

    admin = await test_db.users.find_one({"username": "testadmin"})
    if not admin:
        await test_db.users.insert_one(
            {
                "_id": ObjectId("507f1f77bcf86cd799439011"),
                "username": "testadmin",
                "email": "testadmin@geochallenge.app",
                "password_hash": hash_password("Test123!"),
                "role": "admin",
                "is_verified": True,
                "is_active": True,
                "created_at": datetime.utcnow(),
            }
        )
    yield test_db


@pytest.fixture(scope="session")
async def seeded_caches(test_db):
    """
    Database seeded with sample caches via GPX.
    """
    from pathlib import Path

    from httpx import ASGITransport, AsyncClient

    gpx_path = (
        Path(__file__).parent.parent.parent
        / "data"
        / "samples"
        / "gpx"
        / "export-2025-08-01-16-35-30-1 Jasmer+Mamies.gpx"
    )
    if gpx_path.exists():
        admin_token = create_access_token(data={"sub": str(ObjectId("507f1f77bcf86cd799439011"))})
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            client.headers["Authorization"] = f"Bearer {admin_token}"
            with open(gpx_path, "rb") as f:
                resp = await client.post(
                    "/caches/upload-gpx",
                    files={"file": ("test.gpx", f, "application/gpx+xml")},
                    params={"import_mode": "all", "source_type": "auto"},
                )
                if resp.status_code == 200:
                    nb_inserted = resp.json().get("summary", {}).get("nb_inserted_caches", 0)
                    print(f"\n   📦 {nb_inserted} caches seedées via upload-gpx")
    yield test_db


# =============================================================================
# HTTP CLIENT FIXTURES
# =============================================================================
@pytest.fixture(scope="function")
async def client():
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture(scope="function")
async def auth_client(admin_token):
    from httpx import ASGITransport, AsyncClient

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        c.headers["Authorization"] = f"Bearer {admin_token}"
        yield c


# =============================================================================
# AUTHENTICATION FIXTURES
# =============================================================================
@pytest.fixture(scope="function")
def admin_token():
    return create_access_token(data={"sub": str(ObjectId("507f1f77bcf86cd799439011"))})


@pytest.fixture(scope="function")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# =============================================================================
# CACHES ELEVATION
# =============================================================================
@pytest.fixture
async def caches_without_elevation(test_db):
    """
    Met elevation à None pour les 2000 premières caches.
    Utile pour tester les calculs d'élévation.
    """
    # Récupérer les 2000 premiers IDs
    cursor = test_db.caches.find({}, {"_id": 1}).limit(2000)
    cache_ids = [doc["_id"] async for doc in cursor]

    # Mettre elevation à None
    result = await test_db.caches.update_many(
        {"_id": {"$in": cache_ids}}, {"$set": {"elevation": None}}
    )

    print(f"\n✓ {result.modified_count} caches mis à jour (elevation=None)")

    yield test_db

    # Optionnel : cleanup après le test si besoin
    # await test_db.caches.update_many(
    #     {"_id": {"$in": cache_ids}},
    #     {"$unset": {"elevation": ""}}
    # )


# =============================================================================
# TEST DATA FIXTURES
# =============================================================================
@pytest.fixture(scope="function")
def sample_cache_data():
    return {
        "GC": "GC_TEST_001",
        "title": "Test Cache",
        "description_html": "<p>Test description</p>",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "difficulty": 2.5,
        "terrain": 3.0,
        "type_id": None,
        "size_id": None,
    }


@pytest.fixture(scope="function")
def sample_user_data():
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
@pytest.fixture(scope="function")
def test_object_id():
    return ObjectId()


@pytest.fixture(scope="function")
def test_datetime():
    from datetime import datetime

    return datetime.utcnow()


@pytest.fixture(autouse=True)
def mock_send_verification_email():
    with patch("app.api.routes.auth.send_verification_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = None
        yield mock_send
