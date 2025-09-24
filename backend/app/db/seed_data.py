# backend/app/db/seed_data.py
# Outils de remplissage initial : ping Mongo, seed des référentiels et création/MAJ du compte admin.

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure
from rich import print

import app.core.security as security
from app.core.utils import now
from app.db.mongodb import db as mg_db
from app.db.mongodb import get_collection
from app.db.seed_indexes import ensure_indexes

load_dotenv()
SEEDS_FOLDER = Path(__file__).resolve().parents[2] / "data" / "seeds"


def test_connection():
    """Teste la connexion à MongoDB (ping).

    Description:
        Envoie une commande `ping` à la base et affiche le résultat. En cas d’échec,
        logue un message et termine le processus avec un code d’erreur (sys.exit).

    Args:
        None

    Returns:
        None
    """
    try:
        mg_db.command("ping")
        print("✅ Connexion à MongoDB réussie.")
    except ConnectionFailure:
        print("❌ Échec de la connexion à MongoDB.")
        sys.exit(1)


def seed_collection(file_path: str, collection_name: str, force: bool = False):
    """Remplit une collection depuis un fichier JSON.

    Description:
        Charge le contenu JSON de `file_path` et insère les documents dans `collection_name`.
        - Si la collection est non vide et `force=False`, ne fait rien.
        - Si `force=True`, vide la collection puis insère toutes les données.

    Args:
        file_path (str): Chemin du fichier JSON (UTF-8).
        collection_name (str): Nom de la collection MongoDB cible.
        force (bool, optional): Forcer la réinitialisation de la collection. Par défaut `False`.

    Returns:
        None

    Raises:
        FileNotFoundError: Si le fichier n’existe pas.
        json.JSONDecodeError: Si le JSON est invalide.
    """
    count = mg_db[collection_name].count_documents({})
    if count > 0 and not force:
        print(f"🔁 Collection '{collection_name}' non vide ({count} documents). Rien modifié.")
        return
    force = force or count == 0
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if force:
        mg_db[collection_name].delete_many({})
        print(f"♻️ Collection '{collection_name}' vidée (force=True).")
    mg_db[collection_name].insert_many(data)
    print(f"✅ {len(data)} documents insérés dans '{collection_name}'.")


def seed_admin_user(force: bool = False):
    """Crée ou met à jour l’utilisateur administrateur.

    Description:
        Lit `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` depuis l’environnement.
        Calcule le hash du mot de passe, upsert l’utilisateur avec rôle `admin`, `is_active=True`, `is_verified=True`.

    Args:
        force (bool, optional): Paramètre sans effet direct ici (cohérence d’API).

    Returns:
        None

    Raises:
        ValueError: Si une des variables d’environnement admin est absente.
    """
    collection = get_collection("users")

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_username or not admin_email or not admin_password:
        raise ValueError("ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD must be set in .env")

    admin_password_hashed = security.pwd_context.hash(admin_password)

    collection.update_one(
        {"username": admin_username},
        {
            "$set": {
                "username": admin_username,
                "email": admin_email,
                "password_hash": admin_password_hashed,
                "role": "admin",
                "is_active": True,
                "is_verified": True,
                "preferences": {"language": "fr", "dark_mode": True},
                "updated_at": now(),
            },
            "$setOnInsert": {"created_at": now()},
        },
        upsert=True,
    )
    print("✅ Admin user seeded/updated.")


def seed_referentials(force: bool = False):
    """Seed des collections de référentiels et de l’admin.

    Description:
        Alimente `cache_types`, `cache_sizes`, `cache_attributes` depuis des fichiers JSON
        et appelle `seed_admin_user()` pour garantir la présence du compte admin.

    Args:
        force (bool, optional): Si vrai, réinitialise les collections avant insertion.

    Returns:
        None
    """
    seed_collection(f"{SEEDS_FOLDER}/cache_types.json", "cache_types", force=force)
    seed_collection(f"{SEEDS_FOLDER}/cache_sizes.json", "cache_sizes", force=force)
    seed_collection(f"{SEEDS_FOLDER}/cache_attributes.json", "cache_attributes", force=force)
    seed_admin_user(force=force)


if __name__ == "__main__":
    val = now()
    force = "--force" in sys.argv
    test_connection()
    ensure_indexes()
    seed_referentials(force=force)
