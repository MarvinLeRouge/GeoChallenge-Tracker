# backend/app/db/mongodb.py
"""
Initializes the MongoDB client from settings and exposes simple collection access helpers.
"""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.settings import get_settings

settings = get_settings()

# Global variables initialized to None (lazy initialization)
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_client() -> AsyncIOMotorClient:
    """Returns the MongoDB client (lazy initialization)."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(
            settings.mongodb_uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=3000,
        )
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Returns the MongoDB database (lazy initialization)."""
    global _db
    if _db is None:
        _db = get_client()[settings.mongodb_db]
    return _db


async def get_collection(name: str) -> AsyncIOMotorCollection:
    """Returns a MongoDB collection by name.

    Description:
        Accesses `db[name]` and returns the collection object. If the collection does not
        yet exist on the server, MongoDB will create it on the first insert.

    Args:
        name (str): Collection name (e.g. "users", "caches").

    Returns:
        AsyncIOMotorCollection: Async MongoDB collection instance.
    """
    return get_db()[name]


async def get_column(collection_name: str, column_name: str, limit: int = 0) -> list:
    """Extracts the values of a field from a collection.

    Description:
        Runs a find() projected on `column_name` (without `_id`) and returns the list of values.
        Useful for quickly retrieving a column (non-deduplicated). Be mindful of data volume.

    Args:
        collection_name (str): Source collection name.
        column_name (str): Name of the field/column to extract.
        limit (int): Maximum number of documents to return (0 = no limit).

    Returns:
        list: List of values found for this field (may contain `None` and duplicates).
    """
    db = get_db()
    cursor = db[collection_name].find({}, {column_name: 1, "_id": 0})
    if limit > 0:
        cursor = cursor.limit(limit)
    result = [item[column_name] async for item in cursor]
    return result


async def get_distinct(
    collection_name: str, field_name: str, filter_query: dict | None = None
) -> list:
    """Returns the list of distinct values for `field_name` in `collection_name`.

    Args:
        collection_name: Collection name.
        field_name: Field for which distinct values are requested.
        filter_query: Optional filter.

    Returns:
        list: Distinct values (potentially of heterogeneous types depending on the field).
    """
    filter_query = filter_query or {}
    db = get_db()
    return await db[collection_name].distinct(field_name, filter_query)


async def close_mongodb_connection():
    """Closes the MongoDB connection."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
