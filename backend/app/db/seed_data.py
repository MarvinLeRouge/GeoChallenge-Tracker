# backend/app/db/seed_data.py
# Outils de remplissage initial : ping Mongo, seed des référentiels et création/MAJ du compte admin.

import asyncio
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure
from rich import print

import app.core.security as security
from app.core.utils import now
from app.db.mongodb import db, get_collection
from app.db.seed_indexes import ensure_indexes

load_dotenv()
SEEDS_FOLDER = Path(__file__).resolve().parents[2] / "data" / "seeds"


async def test_connection():
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
        await db.command("ping")
        print("✅ Connexion à MongoDB réussie.")
    except ConnectionFailure:
        print("❌ Échec de la connexion à MongoDB.")
        sys.exit(1)


async def seed_collection(file_path: str, collection_name: str, force: bool = False):
    """Remplit une collection depuis un fichier JSON.

    Description:
        Charge le contenu JSON de `file_path` et insère/met à jour les documents dans `collection_name`.
        - Si `force=True`, vide la collection puis insère toutes les données.
        - Si `force=False` et la collection existe, effectue un upsert :
          compare les documents existants avec les seeds et ne met à jour que ceux qui diffèrent,
          tout en insérant les nouveaux documents. Les documents existants non présents dans
          les seeds sont conservés pour préserver les références entre collections.

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
    collection_obj = await get_collection(collection_name)
    count = await collection_obj.count_documents({})

    with open(file_path, encoding="utf-8") as f:
        seed_data = json.load(f)

    if force:
        await collection_obj.delete_many({})
        print(f"♻️ Collection '{collection_name}' vidée (force=True).")
        await collection_obj.insert_many(seed_data)
        print(f"✅ {len(seed_data)} documents insérés dans '{collection_name}'.")
        return

    if count == 0:
        await collection_obj.insert_many(seed_data)
        print(f"✅ {len(seed_data)} documents insérés dans '{collection_name}'.")
        return

    # Upsert logic: update documents that differ, insert new ones, keep existing ones
    updated_count = 0
    inserted_count = 0

    for seed_doc in seed_data:
        # Try to find a unique identifier in the seed document
        unique_field = None
        unique_value = None

        # Check for common ID field names in the seed document
        for field in ['_id', 'id', 'code', 'cache_type_id', 'cache_size_id']:
            if field in seed_doc:
                unique_field = field
                unique_value = seed_doc[field]
                break

        if unique_field is None:
            # If no unique field is found, we can't do upsert, so skip
            print(f"⚠️  Document in {file_path} does not have a unique identifier field. Skipping upsert.")
            continue

        # Find existing document with the same unique value
        if unique_field == '_id':
            existing_doc = await collection_obj.find_one({"_id": unique_value})
        else:
            # For other unique fields, we need to find by that field
            existing_doc = await collection_obj.find_one({unique_field: unique_value})

        if existing_doc:
            # Compare the documents (excluding _id field from comparison)
            existing_for_comparison = {k: v for k, v in existing_doc.items() if k != '_id'}
            seed_for_comparison = {k: v for k, v in seed_doc.items() if k != '_id'}

            if existing_for_comparison != seed_for_comparison:
                # Update the existing document (preserving the _id)
                await collection_obj.update_one(
                    {unique_field: unique_value},
                    {"$set": seed_doc}
                )
                updated_count += 1
            # else: documents are the same, no update needed
        else:
            # Insert new document
            await collection_obj.insert_one(seed_doc)
            inserted_count += 1

    print(f"✅ {updated_count} documents mis à jour, {inserted_count} documents insérés dans '{collection_name}'.")
    print(f"ℹ️  Les documents existants non présents dans le seed ont été conservés.")


async def seed_admin_user(force: bool = False):
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
    coll_users = await get_collection("users")

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_username or not admin_email or not admin_password:
        raise ValueError("ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD must be set in .env")

    admin_password_hashed = security.pwd_context.hash(admin_password)

    await coll_users.update_one(
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


async def seed_referentials(force: bool = False):
    """Seed des collections de référentiels et de l’admin.

    Description:
        Alimente `cache_types`, `cache_sizes`, `cache_attributes` depuis des fichiers JSON
        et appelle `seed_admin_user()` pour garantir la présence du compte admin.

    Args:
        force (bool, optional): Si vrai, réinitialise les collections avant insertion.

    Returns:
        None
    """
    await seed_collection(f"{SEEDS_FOLDER}/cache_types.json", "cache_types", force=force)
    await seed_collection(f"{SEEDS_FOLDER}/cache_sizes.json", "cache_sizes", force=force)
    await seed_collection(f"{SEEDS_FOLDER}/cache_attributes.json", "cache_attributes", force=force)
    await seed_admin_user(force=force)


async def main():
    await test_connection()
    await ensure_indexes()
    await seed_referentials(force=force)


if __name__ == "__main__":
    val = now()
    force = "--force" in sys.argv
    asyncio.run(main())
