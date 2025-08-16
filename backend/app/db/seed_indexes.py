# backend/app/db/seed_indexes.py

"""
Create MongoDB indexes for GeoChallenge Tracker using get_collection().

- Primary keys: Mongo provides `_id` automatically.
- Foreign keys: not enforced by Mongo; we add indexes on reference fields for fast lookups.
- Unique constraints: via unique indexes (with partial filters when fields are optional).
- Search/optimization indexes: for frequent queries (targets, progress, caches, etc.).
"""

from __future__ import annotations

from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.operations import IndexModel
from app.db.mongodb import get_collection


def _unique_if_present(field: str) -> IndexModel:
    """Unique index on a field only when it exists and is not null (strings)."""
    return IndexModel([(field, ASCENDING)], unique=True,
                      partialFilterExpression={field: {"$type": "string"}})


def seed_indexes() -> None:
    # ---------- users ----------
    users = get_collection("users")
    users.create_indexes([
        IndexModel([("username", ASCENDING)], unique=True, name="uniq_username"),
        IndexModel([("email", ASCENDING)], unique=True, name="uniq_email"),
        IndexModel([("is_active", ASCENDING)], name="by_active"),
        IndexModel([("is_verified", ASCENDING)], name="by_verified"),
    ])

    # ---------- countries ----------
    countries = get_collection("countries")
    countries.create_indexes([
        IndexModel([("name", ASCENDING)], unique=True, name="uniq_country_name"),
        _unique_if_present("code"),  # ISO code may be optional
    ])

    # ---------- states ----------
    states = get_collection("states")
    states.create_indexes([
        IndexModel([("country_id", ASCENDING)], name="by_country"),
        IndexModel([("country_id", ASCENDING), ("name", ASCENDING)], unique=True, name="uniq_state_name_per_country"),
        IndexModel([("country_id", ASCENDING), ("code", ASCENDING)], unique=True,
                   partialFilterExpression={"code": {"$type": "string"}},
                   name="uniq_state_code_per_country_if_present"),
    ])

    # ---------- cache_attributes ----------
    cache_attributes = get_collection("cache_attributes")
    cache_attributes.create_indexes([
        IndexModel([("cache_attribute_id", ASCENDING)], unique=True, name="uniq_cache_attribute_id"),
        IndexModel([("txt", ASCENDING)], unique=True, name="uniq_cache_attribute_txt"),
        IndexModel([("name", ASCENDING)], name="by_name"),
    ])

    # ---------- cache_sizes ----------
    cache_sizes = get_collection("cache_sizes")
    cache_sizes.create_indexes([
        IndexModel([("name", ASCENDING)], unique=True, name="uniq_cache_size_name"),
        IndexModel([("code", ASCENDING)], unique=True,
                   partialFilterExpression={"code": {"$type": "string"}},
                   name="uniq_cache_size_code_if_present"),
    ])

    # ---------- cache_types ----------
    cache_types = get_collection("cache_types")
    cache_types.create_indexes([
        IndexModel([("name", ASCENDING)], unique=True, name="uniq_cache_type_name"),
        IndexModel([("code", ASCENDING)], unique=True,
                   partialFilterExpression={"code": {"$type": "string"}},
                   name="uniq_cache_type_code_if_present"),
    ])

    # ---------- caches ----------
    caches = get_collection("caches")
    caches.create_indexes([
        IndexModel([("GC", ASCENDING)], unique=True, name="uniq_gc_code"),
        # Foreign key lookups
        IndexModel([("type_id", ASCENDING)], name="by_type"),
        IndexModel([("size_id", ASCENDING)], name="by_size"),
        IndexModel([("country_id", ASCENDING)], name="by_country"),
        IndexModel([("state_id", ASCENDING)], name="by_state"),
        IndexModel([("country_id", ASCENDING), ("state_id", ASCENDING)], name="by_country_state"),
        # Range queries / sorts
        IndexModel([("difficulty", ASCENDING)], name="by_difficulty"),
        IndexModel([("terrain", ASCENDING)], name="by_terrain"),
        IndexModel([("placed_at", DESCENDING)], name="by_placed_at_desc"),
        # Text search
        IndexModel([("title", TEXT), ("description_html", TEXT)], name="text_title_desc"),
    ])

    # ---------- found_caches ----------
    found_caches = get_collection("found_caches")
    found_caches.create_indexes([
        IndexModel([("user_id", ASCENDING), ("cache_id", ASCENDING)],
                   unique=True, name="uniq_user_cache_found"),
        IndexModel([("user_id", ASCENDING), ("found_date", DESCENDING)], name="by_user_date_desc"),
        IndexModel([("cache_id", ASCENDING)], name="by_cache"),
    ])

    # ---------- challenges ----------
    challenges = get_collection("challenges")
    challenges.create_indexes([
        IndexModel([("cache_id", ASCENDING)], unique=True, name="uniq_mother_cache"),
        IndexModel([("name", TEXT), ("description", TEXT)], name="text_name_desc"),
    ])

    # ---------- user_challenges ----------
    user_challenges = get_collection("user_challenges")
    user_challenges.create_indexes([
        IndexModel([("user_id", ASCENDING), ("challenge_id", ASCENDING)],
                   unique=True, name="uniq_user_challenge_pair"),
        IndexModel([("user_id", ASCENDING)], name="by_user"),
        IndexModel([("challenge_id", ASCENDING)], name="by_challenge"),
        IndexModel([("status", ASCENDING)], name="by_status"),
    ])

    # ---------- user_challenge_tasks ----------
    user_challenge_tasks = get_collection("user_challenge_tasks")
    user_challenge_tasks.create_indexes([
        IndexModel([("user_challenge_id", ASCENDING), ("order", ASCENDING)], name="by_challenge_order"),
        IndexModel([("user_challenge_id", ASCENDING), ("status", ASCENDING)], name="by_challenge_status"),
        IndexModel([("user_challenge_id", ASCENDING)], name="by_challenge"),
        IndexModel([("last_evaluated_at", DESCENDING)], name="by_last_eval_desc"),
    ])

    # ---------- targets ----------
    targets = get_collection("targets")
    targets.create_indexes([
        IndexModel([("user_challenge_id", ASCENDING), ("cache_id", ASCENDING)],
                   unique=True, name="uniq_target_per_challenge_cache"),
        IndexModel([("user_challenge_id", ASCENDING), ("satisfies_task_ids", ASCENDING)],
                   name="by_challenge_tasks_multi"),  # multikey, supports $all
        IndexModel([("user_challenge_id", ASCENDING), ("primary_task_id", ASCENDING)],
                   name="by_challenge_primary_task"),
        IndexModel([("cache_id", ASCENDING)], name="by_cache"),
        IndexModel([("user_challenge_id", ASCENDING), ("score", DESCENDING)],
                   name="by_challenge_score_desc"),
    ])

    # ---------- progress ----------
    progress = get_collection("progress")
    progress.create_indexes([
        IndexModel([("user_challenge_id", ASCENDING), ("checked_at", ASCENDING)],
                   unique=True, name="uniq_progress_time_per_challenge"),
    ])

    print("Indexes created successfully.")


if __name__ == "__main__":
    seed_indexes()
