# backend/app/services/referentials_cache.py

from __future__ import annotations
from typing import Any, Dict, Optional, Tuple
from bson import ObjectId
from app.db.mongodb import get_collection

from threading import RLock

collections_mapping: Dict[str, Dict[str, Any]] = {}
_collections_lock = RLock()
_mapping_ready = False

def _map_collection(collection_name: str, *, code_field: Optional[str] = None,
                    name_field: Optional[str] = None,
                    extra_numeric_id_field: Optional[str] = None) -> None:
    """
    Construit collections_mapping[collection_name] avec :
      - ids: set(ObjectId)
      - code: {lower -> ObjectId}         (si code_field)
      - name: {lower -> ObjectId}         (si name_field)
      - numeric_ids: set(int)             (si extra_numeric_id_field)
      - doc_by_id: {ObjectId -> doc partiel}
    """
    coll = get_collection(collection_name)

    # Construire la projection dynamiquement pour éviter les clés None
    projection: Dict[str, int] = {"_id": 1}
    if code_field:
        projection[code_field] = 1
    if name_field:
        projection[name_field] = 1
    if extra_numeric_id_field:
        projection[extra_numeric_id_field] = 1

    docs = list(coll.find({}, projection))

    ids: set[ObjectId] = set()
    code_map: Dict[str, ObjectId] = {}
    name_map: Dict[str, ObjectId] = {}
    numeric_ids: set[int] = set()
    doc_by_id: Dict[ObjectId, Dict[str, Any]] = {}

    for d in docs:
        oid = d["_id"]
        ids.add(oid)
        doc_by_id[oid] = d
        if code_field and d.get(code_field):
            code_map[str(d[code_field]).lower()] = oid
        if name_field and d.get(name_field):
            name_map[str(d[name_field]).lower()] = oid
        if extra_numeric_id_field and d.get(extra_numeric_id_field) is not None:
            try:
                numeric_ids.add(int(d[extra_numeric_id_field]))
            except Exception:
                pass

    out: Dict[str, Any] = {"ids": ids, "doc_by_id": doc_by_id}
    if code_field:
        out["code"] = code_map
    if name_field:
        out["name"] = name_map
    if extra_numeric_id_field:
        out["numeric_ids"] = numeric_ids

    collections_mapping[collection_name] = out


def _map_collection_states() -> None:
    """
    states :
      collections_mapping["states"] = {
        "ids": set(ObjectId),
        "by_country": { str(country_id): { lower(state_name): ObjectId } }
      }
    """
    coll = get_collection("states")
    docs = list(coll.find({}, {"_id": 1, "country_id": 1, "name": 1}))

    ids: set[ObjectId] = set()
    by_country: Dict[str, Dict[str, ObjectId]] = {}

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


def _populate_mapping() -> None:
    collections_mapping.clear()
    _map_collection("cache_attributes", code_field="code", name_field="txt",
                    extra_numeric_id_field="cache_attribute_id")
    _map_collection("cache_types",    code_field="code")
    _map_collection("cache_sizes",    code_field="code", name_field="name")  # si "name" existe
    _map_collection("countries",      name_field="name")
    _map_collection_states()


def refresh_referentials_cache():
    """À appeler après un seed pour recharger les mappings en mémoire."""
    _populate_mapping()


# Populate au chargement du module
if not _mapping_ready:
    _populate_mapping()

# --------------------------------------------------------------------------------------
# Existence checks via cache
# --------------------------------------------------------------------------------------

def exists_id(coll_name: str, oid: ObjectId) -> bool:
    try:
        oid = oid if isinstance(oid, ObjectId) else ObjectId(str(oid))
    except Exception:
        return False
    entry = collections_mapping.get(coll_name) or {}
    return oid in entry.get("ids", set())

def exists_attribute_id(attr_id: int) -> bool:
    entry = collections_mapping.get("cache_attributes") or {}
    try:
        return int(attr_id) in entry.get("numeric_ids", set())
    except Exception:
        return False

# --------------------------------------------------------------------------------------
# Resolve code/name → document id (via cache)
# --------------------------------------------------------------------------------------

def _resolve_code_to_id(collection: str, field: str, value: str) -> Optional[ObjectId]:
    entry = collections_mapping.get(collection) or {}
    m = entry.get(field) or {}
    return m.get(str(value).lower())

def resolve_attribute_code(code: str) -> Optional[Tuple[ObjectId, Optional[int]]]:
    entry = collections_mapping.get("cache_attributes") or {}
    # on tente par code, puis par 'txt' (rangé dans name_map)
    oid = (entry.get("code", {}) or {}).get(code.lower())
    if oid is None:
        oid = (entry.get("name", {}) or {}).get(code.lower())
    if oid is None:
        return None
    doc = (entry.get("doc_by_id") or {}).get(oid) or {}
    num = int(doc["cache_attribute_id"]) if doc.get("cache_attribute_id") is not None else None
    return oid, num

def resolve_type_code(code: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("cache_types", "code", code)

def resolve_size_code(code: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("cache_sizes", "code", code)

def resolve_size_name(name: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("cache_sizes", "name", name)

def resolve_country_name(name: str) -> Optional[ObjectId]:
    return _resolve_code_to_id("countries", "name", name)

def resolve_state_name(state_name: str, *, country_id: Optional[ObjectId] = None) -> Tuple[Optional[ObjectId], Optional[str]]:
    entry = collections_mapping.get("states") or {}
    by_country = entry.get("by_country", {})
    target = (state_name or "").lower()

    if country_id:
        key = str(country_id if isinstance(country_id, ObjectId) else ObjectId(str(country_id)))
        sid = (by_country.get(key) or {}).get(target)
        return (sid, None) if sid else (None, f"state not found '{state_name}' in country '{key}'")

    # pas de pays fourni → ambiguïtés possibles
    hits = []
    for cid, states in by_country.items():
        if target in states:
            hits.append(states[target])
    if not hits:
        return None, f"state name not found '{state_name}'"
    if len(hits) > 1:
        return None, f"state name ambiguous without country '{state_name}'"
    return hits[0], None


