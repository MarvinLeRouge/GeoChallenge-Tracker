# backend/app/api/db/seed.py

import os, json, sys
import datetime as dt
from pymongo.errors import ConnectionFailure
from rich import print
from bson import ObjectId
from dotenv import load_dotenv
from app.core.utils import *
import app.core.security as security
from app.models.user import User
from app.db.mongodb import client as mg_client, db as mg_db, get_collection

load_dotenv()
SEEDS_FOLDER = "../../data/seeds"

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

    if collection.find_one({"username": "admin"}) and not force:
        print("🔒 Admin already exists.")
        return

    admin_username = os.getenv("ADMIN_USERNAME")
    admin_email = os.getenv("ADMIN_EMAIL")
    admin_password = os.getenv("ADMIN_PASSWORD")
    if not admin_password:
        raise ValueError("ADMIN_PASSWORD not set in .env")

    admin_password_hashed = security.pwd_context.hash(admin_password)

    user = {
        "_id": ObjectId(),
        "username": admin_username,
        "email": admin_email,
        "password_hash": admin_password_hashed,
        "role": "admin",
        "is_active": True,
        "is_verified": True,
        "preferences": {
            "language": "fr",
            "dark_mode": True
        },
        "created_at": now(),
        "updated_at": None
    }

    collection.insert_one(user)
    print("✅ Admin user seeded.")


if __name__ == "__main__":
    val = now()
    force = "--force" in sys.argv
    test_connection()
    seed_collection(f"{SEEDS_FOLDER}/cache_types.json", "cache_types", force=force)
    seed_collection(f"{SEEDS_FOLDER}/cache_sizes.json", "cache_sizes", force=force)
    seed_collection(f"{SEEDS_FOLDER}/cache_attributes.json", "cache_attributes", force=force)
    seed_admin_user(force=force)

