# backend/app/db/mongodb.py
"""
Initialise le client MongoDB à partir des settings et expose des helpers simples d'accès aux collections.
"""

from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorCollection, AsyncIOMotorDatabase

from app.core.settings import get_settings

settings = get_settings()

# Variables globales mais initialisées à None (lazy initialization)
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None


def get_client() -> AsyncIOMotorClient:
    """Retourne le client MongoDB (lazy initialization)."""
    global _client
    if _client is None:
        _client = AsyncIOMotorClient(settings.mongodb_uri)
    return _client


def get_db() -> AsyncIOMotorDatabase:
    """Retourne la database MongoDB (lazy initialization)."""
    global _db
    if _db is None:
        _db = get_client()[settings.mongodb_db]
    return _db


async def get_collection(name: str) -> AsyncIOMotorCollection:
    """Retourne une collection MongoDB par son nom.

    Description:
        Accède à `db[name]` et renvoie l'objet collection. Si la collection n'existe pas
        encore côté serveur, MongoDB la créera à la première insertion.

    Args:
        name (str): Nom de la collection (ex. "users", "caches").

    Returns:
        AsyncIOMotorCollection: Instance de collection MongoDB asynchrone.
    """
    return get_db()[name]


async def get_column(collection_name: str, column_name: str) -> list:
    """Extrait toutes les valeurs d'un champ dans une collection.

    Description:
        Fait un find() projeté sur `column_name` (sans `_id`) puis retourne la liste des valeurs.
        Utile pour récupérer rapidement une colonne (non dédupliquée). Attention au volume de données.

    Args:
        collection_name (str): Nom de la collection source.
        column_name (str): Nom du champ/colonne à extraire.

    Returns:
        list: Liste des valeurs trouvées pour ce champ (peut contenir des `None` et des doublons).
    """
    db = get_db()
    cursor = db[collection_name].find({}, {column_name: 1, "_id": 0})
    result = [item[column_name] async for item in cursor]
    return result


async def get_distinct(
    collection_name: str, field_name: str, filter_query: dict | None = None
) -> list:
    """Renvoie la liste des valeurs distinctes pour `field_name` dans `collection_name`.

    Args:
        collection_name: Nom de la collection.
        field_name: Champ pour lequel on veut les valeurs distinctes.
        filter_query: Filtre optionnel.

    Returns:
        list: Valeurs distinctes (potentiellement de types hétérogènes selon le champ).
    """
    filter_query = filter_query or {}
    db = get_db()
    return await db[collection_name].distinct(field_name, filter_query)


async def close_mongodb_connection():
    """Ferme la connexion MongoDB."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
