# backend/app/db/seed_indexes.py

from app.db.mongodb import get_collection

def ensure_indexes():
    get_collection("cache_attributes").create_index("cache_attribute_id", unique=True)
    get_collection("cache_attributes").create_index("name", unique=True)

    get_collection("cache_sizes").create_index("name", unique=True)
    get_collection("cache_sizes").create_index("code", unique=True, sparse=True)

    get_collection("cache_types").create_index("name", unique=True)
    get_collection("cache_types").create_index("code", unique=True, sparse=True)
