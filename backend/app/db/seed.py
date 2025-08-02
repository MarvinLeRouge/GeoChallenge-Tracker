# backend/app/db/seed.py
import os, json, sys
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure
from rich import print
from dotenv import load_dotenv
load_dotenv()
MONGODB_USER = os.getenv("MONGODB_USER")
MONGODB_PASSWORD = os.getenv("MONGODB_PASSWORD")
MONGODB_URI_TPL = os.getenv("MONGODB_URI_TPL")
MONGODB_DB = os.getenv("MONGODB_DB")
MONGODB_URI = MONGODB_URI_TPL.replace("[[MONGODB_USER]]", MONGODB_USER).replace("[[MONGODB_PASSWORD]]", MONGODB_PASSWORD)
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
SEEDS_FOLDER = "../../data/seeds"

def test_connection():
    try:
        db.command("ping")
        print("✅ Connexion à MongoDB réussie.")
    except ConnectionFailure:
        print("❌ Échec de la connexion à MongoDB.")
        sys.exit(1)

def seed_collection(file_path, collection_name, force = False):
    count = db[collection_name].count_documents({})
    if count > 0 and not force:
        print(f"🔁 Collection '{collection_name}' non vide ({count} documents). Rien modifié.")
        return
    force = force or count == 0
    with open(file_path, encoding="utf-8") as f:
        data = json.load(f)
    if force:
        db[collection_name].delete_many({})
        print(f"♻️ Collection '{collection_name}' vidée (force=True).")
    db[collection_name].insert_many(data)
    print(f"✅ {len(data)} documents insérés dans '{collection_name}'.")

if __name__ == "__main__":
    force = "--force" in sys.argv
    test_connection()
    seed_collection(f"{SEEDS_FOLDER}/cache_types.json", "cache_types", force=force)
    seed_collection(f"{SEEDS_FOLDER}/cache_sizes.json", "cache_sizes", force=force)
    seed_collection(f"{SEEDS_FOLDER}/cache_attributes.json", "cache_attributes", force=force)

