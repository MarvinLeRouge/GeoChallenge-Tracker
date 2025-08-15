# backend/app/api/db/seed.py

import os, json, sys
import datetime as dt
from pymongo.errors import ConnectionFailure
from rich import print
from bson import ObjectId
from dotenv import load_dotenv
from pathlib import Path
from app.core.utils import *
import app.core.security as security
from app.models.user import User
from app.db.mongodb import client as mg_client, db as mg_db, get_collection
from app.db.seed_indexes import ensure_indexes

load_dotenv()
SEEDS_FOLDER = Path(__file__).resolve().parents[2] / "data" / "seeds"

def test_connection():
    try:
        mg_db.command("ping")
        print("✅ Connexion à MongoDB réussie.")
    except ConnectionFailure:
        print("❌ Échec de la connexion à MongoDB.")
        sys.exit(1)

def seed_collection(file_path, collection_name, force = False):
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
    collection = get_collection("users")

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_username or not admin_email or not admin_password:
        raise ValueError("ADMIN_USERNAME/ADMIN_EMAIL/ADMIN_PASSWORD must be set in .env")

    admin_password_hashed = security.pwd_context.hash(admin_password)

    collection.update_one(
        {"username": admin_username},
        {"$set": {
            "username": admin_username,
            "email": admin_email,
            "password_hash": admin_password_hashed,
            "role": "admin",
            "is_active": True,
            "is_verified": True,
            "preferences": {"language": "fr", "dark_mode": True},
            "updated_at": now(),
        }, "$setOnInsert": {"created_at": now()}},
        upsert=True,
    )
    print("✅ Admin user seeded/updated.")


def seed_referentials(force:bool = False):
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

