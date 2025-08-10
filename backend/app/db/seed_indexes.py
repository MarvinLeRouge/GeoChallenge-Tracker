# backend/app/db/seed_indexes.py

from app.db.mongodb import get_collection

def ensure_indexes():
    get_collection("caches").create_index("GC", unique=True)
    get_collection("countries").create_index("name", unique=True)
    get_collection("states").create_index([("country_id", 1), ("name", 1)], unique=True)
    get_collection("found_caches").create_index([("user_id", 1), ("cache_id", 1)], unique=True)
    # pour filtres sur attributs/polarité
    get_collection("caches").create_index([("attributes.attribute_id", 1)])
    get_collection("caches").create_index([("attributes.attribute_id", 1), ("attributes.included", 1)])
