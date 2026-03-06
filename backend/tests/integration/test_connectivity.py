"""Tests de connectivité - Integration tests.

Ces tests vérifient que l'application peut se connecter aux services externes :
- MongoDB
- (Futur) Redis
- (Futur) Services externes (email, elevation API)

Nécessite une base de données MongoDB configurée.
"""

import pytest
from motor.motor_asyncio import AsyncIOMotorClient

from app.core.settings import get_settings


@pytest.fixture
def mongo_client():
    """Create MongoDB client for tests."""
    settings = get_settings()
    client = AsyncIOMotorClient(settings.mongodb_uri)
    yield client
    client.close()


class TestMongoDBConnectivity:
    """Tests de connectivité MongoDB."""

    @pytest.mark.asyncio
    async def test_backend_can_access_mongo(self, mongo_client):
        """Test que le backend peut se connecter à MongoDB."""
        dbs = await mongo_client.list_database_names()

        assert isinstance(dbs, list)
        assert len(dbs) > 0

    @pytest.mark.asyncio
    async def test_mongo_database_exists(self, mongo_client):
        """Test que la base de données de l'app existe."""
        settings = get_settings()
        dbs = await mongo_client.list_database_names()

        assert settings.mongodb_db in dbs

    @pytest.mark.asyncio
    async def test_mongo_collections_accessible(self, mongo_client):
        """Test que les collections principales sont accessibles."""
        settings = get_settings()
        db = mongo_client[settings.mongodb_db]

        # Should not raise any exception
        caches = db.caches
        users = db.users
        challenges = db.challenges

        assert caches is not None
        assert users is not None
        assert challenges is not None
