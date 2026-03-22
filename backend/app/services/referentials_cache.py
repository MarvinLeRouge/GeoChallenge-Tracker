# backend/app/services/referentials_cache.py
# Maintains in-memory indexes {code|name|numeric_id -> ObjectId} to speed up validations/resolutions.

from __future__ import annotations

import asyncio
from typing import Any

from bson import ObjectId

from app.db.mongodb import get_collection

collections_mapping: dict[str, dict[str, Any]] = {}
# Async lock to prevent concurrent cache rebuilds
_mapping_lock = asyncio.Lock()
_mapping_ready = False


async def _map_collection(
    collection_name: str,
    *,
    code_field: str | None = None,
    name_field: str | None = None,
    extra_numeric_id_field: str | None = None,
    aliases_field: str | None = None,
) -> None:
    """Index a reference collection in memory.

    Description:
        Builds `collections_mapping[collection_name]` with:
        - `ids`: set of present ObjectIds
        - `code`: map `lower(value)` → ObjectId (if `code_field`)
        - `name`: map `lower(value)` → ObjectId (if `name_field`)
        - `aliases`: map `lower(value)` → ObjectId (if `aliases_field`)
        - `numeric_ids`: set of ints (if `extra_numeric_id_field`)
        - `doc_by_id`: map ObjectId → partial doc (projection)

    Args:
        collection_name: Mongo collection name.
        code_field: Key to index by "code" (optional).
        name_field: Key to index by "name" (optional).
        extra_numeric_id_field: Additional numeric key (optional).
        aliases_field: Key to index by "alias" (optional).

    Returns:
        None
    """
    collection_obj = await get_collection(collection_name)

    # Build the projection dynamically to avoid None keys
    projection: dict[str, int] = {"_id": 1}
    if code_field:
        projection[code_field] = 1
    if name_field:
        projection[name_field] = 1
    if extra_numeric_id_field:
        projection[extra_numeric_id_field] = 1
    if aliases_field:
        projection[aliases_field] = 1

    cursor = collection_obj.find({}, projection)
    docs = await cursor.to_list(length=None)

    ids: set[ObjectId] = set()
    code_map: dict[str, ObjectId] = {}
    name_map: dict[str, ObjectId] = {}
    alias_map: dict[str, ObjectId] = {}
    numeric_ids: set[int] = set()
    doc_by_id: dict[ObjectId, dict[str, Any]] = {}

    for d in docs:
        oid = d["_id"]
        ids.add(oid)
        doc_by_id[oid] = d
        if code_field and d.get(code_field):
            code_map[str(d[code_field]).lower()] = oid
        if name_field and d.get(name_field):
            name_map[str(d[name_field]).lower()] = oid
        if aliases_field and d.get(aliases_field):
            aliases_value = d[aliases_field]
            if isinstance(aliases_value, list):
                for alias in aliases_value:
                    if alias:
                        alias_map[str(alias).lower()] = oid
        if extra_numeric_id_field and d.get(extra_numeric_id_field) is not None:
            try:
                numeric_ids.add(int(d[extra_numeric_id_field]))
            except Exception:
                pass

    out: dict[str, Any] = {"ids": ids, "doc_by_id": doc_by_id}
    if code_field:
        out["code"] = code_map
    if name_field:
        out["name"] = name_map
    if aliases_field:
        out["aliases"] = alias_map
    if extra_numeric_id_field:
        out["numeric_ids"] = numeric_ids

    collections_mapping[collection_name] = out


async def _map_collection_states() -> None:
    """Index the `states` collection by country.

    Description:
        Populates `collections_mapping["states"]` with:
        - `ids`: set of ObjectIds
        - `by_country`: `{str(country_id): {lower(state_name): ObjectId}}`

    Args:
        None

    Returns:
        None
    """
    coll_states = await get_collection("states")
    cursor = coll_states.find({}, {"_id": 1, "country_id": 1, "name": 1})
    docs = await cursor.to_list(length=None)

    ids: set[ObjectId] = set()
    by_country: dict[str, dict[str, ObjectId]] = {}

    for d in docs:
        sid = d["_id"]
        cid = d.get("country_id")
        nm = d.get("name")
        ids.add(sid)
        if cid and nm:
            key = str(cid)
            by_country.setdefault(key, {})
            by_country[key][nm.lower()] = sid

    collections_mapping["states"] = {"ids": ids, "by_country": by_country}


async def populate_mapping() -> None:
    """(Re)initialize all in-memory indexes.

    Description:
        Reloads mappings for `cache_attributes`, `cache_types`, `cache_sizes`,
        `countries` and `states`.

    Args:
        None

    Returns:
        None
    """
    async with _mapping_lock:
        collections_mapping.clear()
        await _map_collection(
            "cache_attributes",
            code_field="code",
            name_field="txt",
            extra_numeric_id_field="cache_attribute_id",
        )
        await _map_collection("cache_types", code_field="code")
        await _map_collection(
            "cache_sizes", code_field="code", name_field="name", aliases_field="aliases"
        )  # if "name" exists
        await _map_collection("countries", name_field="name")
        await _map_collection_states()
        global _mapping_ready
        _mapping_ready = True


async def refresh_referentials_cache() -> None:
    """Force a refresh of in-memory reference data.

    Description:
        Call after a seed/import to pick up the latest reference data.

    Args:
        None

    Returns:
        None
    """
    await populate_mapping()


# --------------------------------------------------------------------------------------
# Existence checks via cache
# --------------------------------------------------------------------------------------


def exists_id(coll_name: str, oid: ObjectId) -> bool:
    """Check whether an ObjectId exists in a reference collection.

    Args:
        coll_name: Reference collection name.
        oid: Identifier to check.

    Returns:
        bool: True if the ObjectId is known to the cache, False otherwise.
    """
    try:
        oid = oid if isinstance(oid, ObjectId) else ObjectId(str(oid))
    except Exception:
        return False
    entry = collections_mapping.get(coll_name) or {}
    return oid in entry.get("ids", set())


def exists_attribute_id(attr_id: int) -> bool:
    """Check whether a numeric attribute identifier exists.

    Args:
        attr_id: Numeric `cache_attribute_id`.

    Returns:
        bool: True if the numeric ID is known, False otherwise.
    """
    entry = collections_mapping.get("cache_attributes") or {}
    try:
        return int(attr_id) in entry.get("numeric_ids", set())
    except Exception:
        return False


# --------------------------------------------------------------------------------------
# Resolve code/name → document id (via cache)
# --------------------------------------------------------------------------------------


def _resolve_code_to_id(collection: str, field: str, value: str) -> ObjectId | None:
    """Resolve a code/name to an ObjectId via the cache.

    Args:
        collection: Collection name.
        field: `code`, `name`, or `aliases`.
        value: Provided value (case-insensitive).

    Returns:
        ObjectId | None: Found reference or None.
    """
    entry = collections_mapping.get(collection) or {}
    if field == "aliases":
        # For aliases, we check the aliases map which has been pre-built
        m = entry.get(field) or {}
        return m.get(str(value).lower())
    else:
        # For other fields (code, name), use the original logic
        m = entry.get(field) or {}
        return m.get(str(value).lower())


def resolve_attribute_code(code: str) -> tuple[ObjectId, int | None] | None:
    """Resolve an attribute by code/text.

    Description:
        Tries `code` first, then `txt`, and returns (ObjectId, `cache_attribute_id`).

    Args:
        code: Code or text identifier (e.g. "dogs_allowed").

    Returns:
        tuple[ObjectId, int|None] | None: Reference and numeric ID, or None if not found.
    """
    entry = collections_mapping.get("cache_attributes") or {}
    # try by code, then by ‘txt’ (stored in name_map)
    oid = (entry.get("code", {}) or {}).get(code.lower())
    if oid is None:
        oid = (entry.get("name", {}) or {}).get(code.lower())
    if oid is None:
        return None
    doc = (entry.get("doc_by_id") or {}).get(oid) or {}
    num = int(doc["cache_attribute_id"]) if doc.get("cache_attribute_id") is not None else None
    return oid, num


def resolve_type_code(code: str) -> ObjectId | None:
    """Resolve a cache type by code.

    Args:
        code: Type code (e.g. "TR").

    Returns:
        ObjectId | None: Type reference.
    """
    return _resolve_code_to_id("cache_types", "code", code)


def resolve_size_code(code: str) -> ObjectId | None:
    """Resolve a cache size by code.

    Args:
        code: Size code (e.g. "S").

    Returns:
        ObjectId | None: Size reference.
    """
    return _resolve_code_to_id("cache_sizes", "code", code)


def resolve_size_name(name: str) -> ObjectId | None:
    """Resolve a cache size by name.

    Args:
        name: Name (e.g. "Micro").

    Returns:
        ObjectId | None: Size reference.
    """
    # First check the name field
    result = _resolve_code_to_id("cache_sizes", "name", name)
    if result is not None:
        return result

    # Then check the aliases field
    return _resolve_code_to_id("cache_sizes", "aliases", name)


def resolve_size_alias(alias: str) -> ObjectId | None:
    """Resolve a cache size by alias.

    Args:
        alias: Alias (e.g. "nano" for Micro).

    Returns:
        ObjectId | None: Size reference.
    """
    return _resolve_code_to_id("cache_sizes", "aliases", alias)


def resolve_country_name(name: str) -> ObjectId | None:
    """Resolve a country by name.

    Args:
        name: Country name (e.g. "France").

    Returns:
        ObjectId | None: Country reference.
    """
    return _resolve_code_to_id("countries", "name", name)


def resolve_state_name(
    state_name: str, *, country_id: ObjectId | None = None
) -> tuple[ObjectId | None, str | None]:
    """Resolve a state/region by name (optionally scoped to a country).

    Description:
        If `country_id` is not provided, handles ambiguities:
        - 0 hits → "not found" message
        - >1 hit → "ambiguous" message

    Args:
        state_name: State/region name.
        country_id: Country filter (ObjectId) for disambiguation.

    Returns:
        tuple[ObjectId|None, str|None]: (state_id, error message or None).
    """
    entry = collections_mapping.get("states") or {}
    by_country = entry.get("by_country", {})
    target = (state_name or "").lower()

    if country_id:
        key = str(country_id if isinstance(country_id, ObjectId) else ObjectId(str(country_id)))
        sid = (by_country.get(key) or {}).get(target)
        return (sid, None) if sid else (None, f"state not found ‘{state_name}’ in country ‘{key}’")

    # no country provided → possible ambiguities
    hits = []
    for _cid, states in by_country.items():
        if target in states:
            hits.append(states[target])
    if not hits:
        return None, f"state name not found '{state_name}'"
    if len(hits) > 1:
        return None, f"state name ambiguous without country '{state_name}'"
    return hits[0], None
