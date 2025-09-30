# backend/app/db/mongodb.py
# Initialise le client MongoDB à partir des settings et expose des helpers simples d’accès aux collections.

from pymongo import MongoClient
from pymongo.database import Database

from app.core.settings import get_settings
settings = get_settings()

client: MongoClient[dict] = MongoClient(settings.mongodb_uri)
db: Database[dict] = client[settings.mongodb_db]


def get_collection(name: str):
    """Retourne une collection MongoDB par son nom.

    Description:
        Accède à `db[name]` et renvoie l’objet collection. Si la collection n’existe pas
        encore côté serveur, MongoDB la créera à la première insertion.

    Args:
        name (str): Nom de la collection (ex. "users", "caches").

    Returns:
        Collection: Instance de collection MongoDB.
    """
    return db[name]


def get_column(collection_name: str, column_name: str) -> list:
    """Extrait toutes les valeurs d’un champ dans une collection.

    Description:
        Fait un find() projeté sur `column_name` (sans `_id`) puis retourne la liste des valeurs.
        Utile pour récupérer rapidement une colonne (non dédupliquée). Attention au volume de données.

    Args:
        collection_name (str): Nom de la collection source.
        column_name (str): Nom du champ/colonne à extraire.

    Returns:
        list: Liste des valeurs trouvées pour ce champ (peut contenir des `None` et des doublons).
    """
    result = [
        item[column_name] for item in db[collection_name].find({}, {column_name: 1, "_id": 0})
    ]

    return result
