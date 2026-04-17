# backend/app/db/seed_indexes.py
# Provides helpers to ensure (create/update) Mongo indexes with option comparison
# (unique, partialFilterExpression, collation) and a global `ensure_indexes()` seeder.

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from typing import Any, Union, cast

from pymongo import ASCENDING, DESCENDING, TEXT
from pymongo.collation import Collation
from pymongo.errors import OperationFailure
from pymongo.operations import IndexModel

from app.db.mongodb import get_collection

# Direction can be 1/-1 for asc/desc, or string for special types ('2dsphere', '2d', etc.)
Direction = Union[int, str]
KeySpec = list[tuple[str, Direction]]

# Case-insensitive (accent-sensitive) collation for users
COLLATION_CI = Collation(locale="en", strength=2)


def _normalize_key_from_mongo(key_doc: dict[str, Any]) -> KeySpec:
    """Normalizes an index key document returned by Mongo.

    Description:
        Converts the key document (ordered mapping) into a list of `(field, direction)` tuples,
        where direction is an int (1/-1) or a string (e.g. ‘2dsphere’).

    Args:
        key_doc (dict[str, Any]): `key` document of a Mongo index.

    Returns:
        KeySpec: Normalized list of (field, direction) pairs.
    """
    norm: KeySpec = []
    for k, v in key_doc.items():
        if isinstance(v, (int, float)):
            norm.append((k, int(v)))
        else:
            # e.g. '2dsphere', 'text'
            norm.append((k, str(v)))
    return norm


async def _find_existing_by_keys(coll, keys: KeySpec) -> dict[str, Any] | None:
    """Finds an existing index matching exactly these keys.

    Description:
        Iterates over `coll.list_indexes()` and compares keys via `_normalize_key_from_mongo`.

    Args:
        coll: MongoDB collection.
        keys (KeySpec): Desired index keys.

    Returns:
        dict | None: Existing index descriptor or `None` if not found.
    """
    async for ix in coll.list_indexes():
        if "key" in ix and _normalize_key_from_mongo(ix["key"]) == keys:
            return ix
    return None


def _collation_to_dict(c: Collation | None) -> dict[str, Any] | None:
    """Converts a Mongo collation to a comparable dict.

    Description:
        Extracts the relevant fields from a `Collation` for option comparison.

    Args:
        c (Collation | None): Collation to convert.

    Returns:
        dict | None: Parameter dictionary or `None`.
    """
    if c is None:
        return None
    # Collation has properties; we compare a subset that matters
    return {
        "locale": c.document.get("locale"),
        "strength": c.document.get("strength"),
        "caseLevel": c.document.get("caseLevel"),
        "caseFirst": c.document.get("caseFirst"),
        "numericOrdering": c.document.get("numericOrdering"),
        "alternate": c.document.get("alternate"),
        "maxVariable": c.document.get("maxVariable"),
        "backwards": c.document.get("backwards"),
    }


def _same_options(
    existing: dict[str, Any],
    *,
    unique: bool | None,
    partial: dict[str, Any] | None,
    collation: Collation | None,
) -> bool:
    """Compares an existing index’s options against the desired options.

    Description:
        Checks equality of `unique`, `partialFilterExpression`, and `collation`.

    Args:
        existing (dict): Existing index descriptor.
        unique (bool | None): Expected uniqueness constraint.
        partial (dict | None): Expected partial filter expression.
        collation (Collation | None): Expected collation.

    Returns:
        bool: True if the options match, False otherwise.
    """
    ex_unique = bool(existing.get("unique", False))
    if bool(unique) != ex_unique:
        return False
    ex_partial = existing.get("partialFilterExpression")
    if (partial or None) != (ex_partial or None):
        return False
    ex_collation = existing.get("collation")
    # ex_collation is a dict when present
    return (_collation_to_dict(collation) or None) == (ex_collation or None)


async def ensure_index(
    coll_name: str,
    keys: KeySpec,
    *,
    name: str | None = None,
    unique: bool | None = None,
    partial: dict[str, Any] | None = None,
    collation: Collation | None = None,
) -> None:
    """Ensures a simple index exists (idempotent create/update).

    Description:
        - If an index with **the same keys** and **the same options** already exists: does nothing.
        - If it exists with **different options**, drops it then recreates it.
        - Otherwise, creates the index with the provided options.

    Args:
        coll_name (str): Collection name.
        keys (KeySpec): List of (field, direction) pairs.
        name (str | None): Explicit index name.
        unique (bool | None): Uniqueness constraint.
        partial (dict | None): `partialFilterExpression`.
        collation (Collation | None): Collation.

    Returns:
        None
    """
    coll = await get_collection(coll_name)
    existing = await _find_existing_by_keys(coll, keys)
    if existing and _same_options(existing, unique=unique, partial=partial, collation=collation):
        return
    if existing:
        # Tolerate concurrent execution (multiple workers):
        #  - re-list to minimize the race window
        #  - ignore IndexNotFound (code 27)
        try:
            server_names = {ix.get("name") async for ix in coll.list_indexes()}
            name_to_drop = cast(str, existing["name"])
            if name_to_drop in server_names:
                await coll.drop_index(name_to_drop)
        except OperationFailure as exc:
            if getattr(exc, "code", None) != 27:  # IndexNotFound
                raise
    opts: dict[str, Any] = {}
    if name:
        opts["name"] = name
    if unique is not None:
        opts["unique"] = unique
    if partial:
        opts["partialFilterExpression"] = partial
    if collation is not None:
        opts["collation"] = collation
    await coll.create_indexes([IndexModel(keys, **opts)])


async def ensure_text_index(
    coll_name: str, fields: Iterable[str], *, name: str | None = None
) -> None:
    """Ensures a **single** text index on the given fields (weight = 1).

    Description:
        Mongo only allows **one** text index per collection:
        - If it exists and covers exactly the `fields`, does nothing.
        - Otherwise, drops it then recreates a text index on those fields.

    Args:
        coll_name (str): Collection name.
        fields (Iterable[str]): Fields to index as text.
        name (str | None): Explicit index name.

    Returns:
        None
    """
    coll = await get_collection(coll_name)
    wanted = {f: 1 for f in fields}
    existing = None
    async for ix in coll.list_indexes():
        if "weights" in ix:  # text index
            existing = ix
            break
    if existing:
        # Compare weights (ignore stray '_id' entry if present)
        ex_weights = {k: v for k, v in existing.get("weights", {}).items() if k != "_id"}
        if ex_weights == wanted:
            return  # already desired
        await coll.drop_index(existing["name"])
    keys = [(f, TEXT) for f in fields]
    await coll.create_indexes([IndexModel(keys, name=name)])


async def ensure_indexes() -> None:
    """Creates/ensures all indexes used by the application.

    Description:
        Builds all indexes (users, caches, challenges, progress, targets, etc.),
        applying appropriate collations and idempotency.

    Args:
        None

    Returns:
        None
    """
    # ---------- users (CI uniques via collation) ----------
    await ensure_index(
        "users",
        [("username", ASCENDING)],
        name="uniq_username_ci",
        unique=True,
        collation=COLLATION_CI,
    )
    await ensure_index(
        "users",
        [("email", ASCENDING)],
        name="uniq_email_ci",
        unique=True,
        collation=COLLATION_CI,
    )
    # Non-unique helpers
    await ensure_index("users", [("is_active", ASCENDING)])
    await ensure_index("users", [("is_verified", ASCENDING)])
    await ensure_index(
        "users",
        [("verification_expires_at", ASCENDING)],
        name="idx_users_verification_expires",
        partial={"verification_expires_at": {"$type": "date"}},
    )
    await ensure_index("users", [("location", "2dsphere")], name="geo_user_location_2dsphere")

    # ---------- countries ----------
    await ensure_index("countries", [("name", ASCENDING)], name="uniq_country_name", unique=True)
    await ensure_index(
        "countries",
        [("code", ASCENDING)],
        unique=True,
        partial={"code": {"$type": "string"}},
    )

    # ---------- states ----------
    await ensure_index("states", [("country_id", ASCENDING)])
    await ensure_index(
        "states",
        [("country_id", ASCENDING), ("name", ASCENDING)],
        name="uniq_state_name_per_country",
        unique=True,
    )
    await ensure_index(
        "states",
        [("country_id", ASCENDING), ("code", ASCENDING)],
        name="uniq_state_code_per_country_if_present",
        unique=True,
        partial={"code": {"$type": "string"}},
    )

    # ---------- cache_attributes ----------
    await ensure_index(
        "cache_attributes",
        [("cache_attribute_id", ASCENDING)],
        name="uniq_cache_attribute_id",
        unique=True,
    )
    await ensure_index(
        "cache_attributes",
        [("txt", ASCENDING)],
        name="uniq_cache_attribute_txt",
        unique=True,
        partial={"txt": {"$type": "string"}},
    )
    await ensure_index("cache_attributes", [("name", ASCENDING)])

    # ---------- cache_sizes ----------
    await ensure_index(
        "cache_sizes", [("name", ASCENDING)], name="uniq_cache_size_name", unique=True
    )
    await ensure_index(
        "cache_sizes",
        [("code", ASCENDING)],
        name="uniq_cache_size_code_if_present",
        unique=True,
        partial={"code": {"$type": "string"}},
    )
    # Add index for aliases array
    await ensure_index(
        "cache_sizes",
        [("aliases", ASCENDING)],
        name="idx_cache_size_aliases",
    )

    # ---------- cache_types ----------
    await ensure_index(
        "cache_types", [("name", ASCENDING)], name="uniq_cache_type_name", unique=True
    )
    await ensure_index(
        "cache_types",
        [("code", ASCENDING)],
        name="uniq_cache_type_code_if_present",
        unique=True,
        partial={"code": {"$type": "string"}},
    )

    # ---------- caches ----------
    await ensure_index("caches", [("GC", ASCENDING)], name="uniq_gc_code", unique=True)
    await ensure_index("caches", [("type_id", ASCENDING)])
    await ensure_index("caches", [("size_id", ASCENDING)])
    await ensure_index("caches", [("country_id", ASCENDING)])
    await ensure_index("caches", [("state_id", ASCENDING)])
    await ensure_index("caches", [("country_id", ASCENDING), ("state_id", ASCENDING)])
    await ensure_index("caches", [("difficulty", ASCENDING)])
    await ensure_index("caches", [("terrain", ASCENDING)])
    await ensure_index("caches", [("placed_at", DESCENDING)])
    await ensure_index("caches", [("favorites", DESCENDING)], name="ix_caches__favorites_desc")
    await ensure_text_index("caches", ["title", "description_html"], name="text_title_desc")
    await ensure_index("caches", [("loc", "2dsphere")], name="geo_loc_2dsphere")
    # Caches: accelerate attribute-based filters (RuleAttributes)
    await ensure_index(
        "caches",
        [
            ("attributes.attribute_doc_id", ASCENDING),
            ("attributes.is_positive", ASCENDING),
        ],
        name="ix_caches__attributes_attrdocid_ispos",
    )
    # NEW: frequent combos for targets
    await ensure_index(
        "caches",
        [("type_id", ASCENDING), ("size_id", ASCENDING)],
        name="ix_caches__type_size",
    )
    await ensure_index(
        "caches",
        [("difficulty", ASCENDING), ("terrain", ASCENDING)],
        name="ix_caches__difficulty_terrain",
    )
    await ensure_index(
        "caches",
        [("type_id", ASCENDING), ("difficulty", ASCENDING), ("terrain", ASCENDING)],
        name="ix_caches__type_difficulty_terrain",
    )

    # ---------- administrative_zones ----------
    await ensure_index(
        "administrative_zones",
        [("code", ASCENDING), ("level", ASCENDING)],
        name="uniq_zone_code_level",
        unique=True,
    )
    await ensure_index("administrative_zones", [("country_code", ASCENDING)])
    await ensure_index("administrative_zones", [("parent_code", ASCENDING)])

    # ---------- found_caches ----------
    await ensure_index(
        "found_caches",
        [("user_id", ASCENDING), ("cache_id", ASCENDING)],
        name="uniq_user_cache_found",
        unique=True,
    )
    await ensure_index("found_caches", [("user_id", ASCENDING), ("found_date", DESCENDING)])
    await ensure_index("found_caches", [("cache_id", ASCENDING)])

    # ---------- challenges ----------
    await ensure_index(
        "challenges", [("cache_id", ASCENDING)], name="uniq_mother_cache", unique=True
    )
    await ensure_text_index("challenges", ["name", "description"], name="text_name_desc")

    # ---------- user_challenges ----------
    await ensure_index(
        "user_challenges",
        [("user_id", ASCENDING), ("challenge_id", ASCENDING)],
        name="uniq_user_challenge_pair",
        unique=True,
    )
    await ensure_index("user_challenges", [("user_id", ASCENDING)])
    await ensure_index("user_challenges", [("challenge_id", ASCENDING)])
    await ensure_index("user_challenges", [("status", ASCENDING)])
    # UserChallenges: fast listing by user + status sorted by most recently updated
    await ensure_index(
        "user_challenges",
        [("user_id", ASCENDING), ("status", ASCENDING), ("updated_at", DESCENDING)],
        name="ix_user_challenges__by_user_status_updated",
    )

    # ---------- user_challenge_tasks ----------
    await ensure_index(
        "user_challenge_tasks", [("user_challenge_id", ASCENDING), ("order", ASCENDING)]
    )
    await ensure_index(
        "user_challenge_tasks",
        [("user_challenge_id", ASCENDING), ("status", ASCENDING)],
    )
    await ensure_index("user_challenge_tasks", [("user_challenge_id", ASCENDING)])
    await ensure_index("user_challenge_tasks", [("last_evaluated_at", DESCENDING)])

    # ---------- progress ----------
    await ensure_index(
        "progress",
        [("user_challenge_id", ASCENDING), ("checked_at", ASCENDING)],
        name="uniq_progress_time_per_challenge",
        unique=True,
    )

    # ---------- targets ----------
    # Uniqueness of a target per (UC, cache)
    await ensure_index(
        "targets",
        [("user_challenge_id", ASCENDING), ("cache_id", ASCENDING)],
        name="uniq_target_per_challenge_cache",
        unique=True,
    )

    # Common filters and sort orders
    await ensure_index(
        "targets", [("user_challenge_id", ASCENDING), ("satisfies_task_ids", ASCENDING)]
    )
    await ensure_index(
        "targets", [("user_challenge_id", ASCENDING), ("primary_task_id", ASCENDING)]
    )
    await ensure_index("targets", [("cache_id", ASCENDING)])
    await ensure_index(
        "targets",
        [("user_id", ASCENDING), ("score", DESCENDING)],
        name="user_score_desc",
    )
    # Sort by score for a given UC
    await ensure_index(
        "targets",
        [
            ("user_id", ASCENDING),
            ("user_challenge_id", ASCENDING),
            ("score", DESCENDING),
        ],
        name="ix_targets__uc_score_desc",
    )
    # Index géospatial sur loc (GeoJSON Point)
    await ensure_index("targets", [("loc", "2dsphere")], name="geo_targets_loc_2dsphere")

    # Recent sort for temporal ordering when needed
    await ensure_index(
        "targets",
        [("updated_at", DESCENDING), ("created_at", DESCENDING)],
        name="updated_created_desc",
    )


if __name__ == "__main__":
    asyncio.run(ensure_indexes())
