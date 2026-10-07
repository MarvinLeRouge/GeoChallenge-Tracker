# backend/app/db/seed_data.py
# Initial seeding utilities: MongoDB ping, referential seeding, and admin account creation/update.

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from pymongo.errors import ConnectionFailure

import app.core.security as security
from app.core.utils import now
from app.db.mongodb import get_collection, get_db
from app.db.seed_indexes import ensure_indexes

log = logging.getLogger(__name__)

SEEDS_FOLDER = Path(__file__).resolve().parents[2] / "data" / "seeds"


async def test_connection():
    """Tests the MongoDB connection (ping).

    Description:
        Sends a `ping` command to the database and prints the result. On failure,
        logs a message and exits the process with an error code (sys.exit).

    Args:
        None

    Returns:
        None
    """
    try:
        db = get_db()
        await db.command("ping")
        print("✅ Connexion à MongoDB réussie.")
    except ConnectionFailure:
        print("❌ Échec de la connexion à MongoDB.")
        sys.exit(1)


async def _force_reseed_collection(collection_obj, collection_name: str, seed_data: list) -> None:
    """Clears a collection then inserts all seed data (force=True path).

    Args:
        collection_obj: MongoDB collection object.
        collection_name (str): Target MongoDB collection name.
        seed_data (list): Documents to insert.

    Returns:
        None
    """
    await collection_obj.delete_many({})
    log.info("Collection ‘%s’ cleared (force=True).", collection_name)
    await collection_obj.insert_many(seed_data)
    log.info("%d documents inserted into ‘%s’.", len(seed_data), collection_name)


async def _upsert_seed_doc(
    collection_obj, seed_doc: dict, unique_field: str, file_path: str
) -> tuple[bool, bool]:
    """Upserts a single seed document against its existing counterpart, if any.

    Args:
        collection_obj: MongoDB collection object.
        seed_doc (dict): Seed document to upsert.
        unique_field (str): Field used as the upsert key.
        file_path (str): Source seed file path, used for warning messages.

    Returns:
        tuple[bool, bool]: (was_updated, was_inserted).
    """
    unique_value = seed_doc.get(unique_field)

    if unique_value is None:
        log.warning("Document in %s is missing ‘%s’. Skipping upsert.", file_path, unique_field)
        return False, False

    existing_doc = await collection_obj.find_one({unique_field: unique_value})

    if not existing_doc:
        await collection_obj.insert_one(seed_doc)
        return False, True

    existing_for_comparison = {k: v for k, v in existing_doc.items() if k != "_id"}
    seed_for_comparison = {k: v for k, v in seed_doc.items() if k != "_id"}

    if existing_for_comparison != seed_for_comparison:
        await collection_obj.update_one({unique_field: unique_value}, {"$set": seed_doc})
        return True, False

    return False, False


async def seed_collection(
    file_path: str,
    collection_name: str,
    unique_field: str = "code",
    force: bool = False,
):
    """Seeds a collection from a JSON file.

    Description:
        Loads the JSON content of `file_path` and inserts/updates documents in `collection_name`.
        - If `force=True`, clears the collection then inserts all data.
        - If `force=False` and the collection already exists, performs an upsert on `unique_field`:
          compares existing documents against seeds and only updates those that differ,
          while inserting new documents. Existing documents absent from the seed are preserved
          to maintain references across collections.

    Args:
        file_path (str): Path to the JSON file (UTF-8).
        collection_name (str): Target MongoDB collection name.
        unique_field (str): Field used as the upsert key. Defaults to ``"code"``.
        force (bool, optional): Force collection reset before insertion. Defaults to `False`.

    Returns:
        None

    Raises:
        FileNotFoundError: If the file does not exist.
        json.JSONDecodeError: If the JSON is invalid.
    """
    collection_obj = await get_collection(collection_name)
    count = await collection_obj.count_documents({})

    with open(file_path, encoding="utf-8") as f:
        seed_data = json.load(f)

    if force:
        await _force_reseed_collection(collection_obj, collection_name, seed_data)
        return

    if count == 0:
        await collection_obj.insert_many(seed_data)
        log.info("%d documents inserted into ‘%s’.", len(seed_data), collection_name)
        return

    # Upsert logic: update documents that differ, insert new ones, keep existing ones
    updated_count = 0
    inserted_count = 0

    for seed_doc in seed_data:
        was_updated, was_inserted = await _upsert_seed_doc(
            collection_obj, seed_doc, unique_field, file_path
        )
        updated_count += was_updated
        inserted_count += was_inserted

    log.info(
        "%d documents updated, %d documents inserted into ‘%s’.",
        updated_count,
        inserted_count,
        collection_name,
    )
    log.info("Existing documents not present in the seed were preserved.")


async def seed_admin_user(force: bool = False):
    """Creates or updates the administrator user.

    Description:
        Reads `ADMIN_USERNAME`, `ADMIN_EMAIL`, `ADMIN_PASSWORD` from the environment.
        Hashes the password and upserts the user with role `admin`, `is_active=True`, `is_verified=True`.

    Args:
        force (bool, optional): Parameter with no direct effect here (API consistency).

    Returns:
        None

    Raises:
        ValueError: If any admin environment variable is missing.
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
    log.info("Admin user seeded/updated.")


async def seed_referentials(force: bool = False):
    """Seeds referential collections and the admin account.

    Description:
        Populates `cache_types`, `cache_sizes`, `cache_attributes` from JSON files
        and calls `seed_admin_user()` to ensure the admin account is present.

    Args:
        force (bool, optional): If true, resets collections before insertion.

    Returns:
        None
    """
    await seed_collection(
        f"{SEEDS_FOLDER}/cache_types.json", "cache_types", unique_field="code", force=force
    )
    await seed_collection(
        f"{SEEDS_FOLDER}/cache_sizes.json", "cache_sizes", unique_field="code", force=force
    )
    await seed_collection(
        f"{SEEDS_FOLDER}/cache_attributes.json",
        "cache_attributes",
        unique_field="code",
        force=force,
    )
    await seed_admin_user(force=force)


async def main():
    await test_connection()
    await ensure_indexes()
    await seed_referentials(force=force)


if __name__ == "__main__":
    val = now()
    force = "--force" in sys.argv
    asyncio.run(main())
