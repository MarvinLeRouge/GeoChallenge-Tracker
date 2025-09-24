# backend/app/services/referentials_cache.py
# Maintient en mémoire des index {code|name|numeric_id -> ObjectId} pour accélérer les validations/résolutions.

from __future__ import annotations

from threading import RLock
from typing import Any

from bson import ObjectId

from app.db.mongodb import get_collection

collections_mapping: dict[str, dict[str, Any]] = {}
_collections_lock = RLock()
_mapping_ready = False


def _map_collection(
    collection_name: str,
    *,
    code_field: str | None = None,
    name_field: str | None = None,
    extra_numeric_id_field: str | None = None,
) -> None:
    """Indexer une collection référentielle en mémoire.

    Description:
        Construit `collections_mapping[collection_name]` avec:
        - `ids`: set d’ObjectId présents
        - `code`: map `lower(value)` → ObjectId (si `code_field`)
        - `name`: map `lower(value)` → ObjectId (si `name_field`)
        - `numeric_ids`: set d’ints (si `extra_numeric_id_field`)
        - `doc_by_id`: map ObjectId → doc partiel (projection)

    Args:
        collection_name: Nom de la collection Mongo.
        code_field: Clé à indexer par « code » (optionnel).
        name_field: Clé à indexer par « nom » (optionnel).
        extra_numeric_id_field: Clé numérique supplémentaire (optionnel).

    Returns:
        None
    """
    coll = get_collection(collection_name)

    # Construire la projection dynamiquement pour éviter les clés None
    projection: dict[str, int] = {"_id": 1}
    if code_field:
        projection[code_field] = 1
    if name_field:
        projection[name_field] = 1
    if extra_numeric_id_field:
        projection[extra_numeric_id_field] = 1

    docs = list(coll.find({}, projection))

    ids: set[ObjectId] = set()
    code_map: dict[str, ObjectId] = {}
    name_map: dict[str, ObjectId] = {}
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
    if extra_numeric_id_field:
        out["numeric_ids"] = numeric_ids

    collections_mapping[collection_name] = out


def _map_collection_states() -> None:
    """Indexer la collection `states` par pays.

    Description:
        Alimente `collections_mapping["states"]` avec:
        - `ids`: set des ObjectId
        - `by_country`: `{str(country_id): {lower(state_name): ObjectId}}`

    Args:
        None

    Returns:
        None
    """
    coll = get_collection("states")
    docs = list(coll.find({}, {"_id": 1, "country_id": 1, "name": 1}))

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


def _populate_mapping() -> None:
    """(Ré)initialiser tous les index en mémoire.

    Description:
        Recharge les mappings pour `cache_attributes`, `cache_types`, `cache_sizes`,
        `countries` et `states`.

    Args:
        None

    Returns:
        None
    """
    collections_mapping.clear()
    _map_collection(
        "cache_attributes",
        code_field="code",
        name_field="txt",
        extra_numeric_id_field="cache_attribute_id",
    )
    _map_collection("cache_types", code_field="code")
    _map_collection("cache_sizes", code_field="code", name_field="name")  # si "name" existe
    _map_collection("countries", name_field="name")
    _map_collection_states()


def refresh_referentials_cache() -> None:
    """Forcer un rafraîchissement des référentiels en mémoire.

    Description:
        À appeler après un seed/import pour prendre en compte les derniers référentiels.

    Args:
        None

    Returns:
        None
    """
    _populate_mapping()


# Populate au chargement du module
if not _mapping_ready:
    _populate_mapping()

# --------------------------------------------------------------------------------------
# Existence checks via cache
# --------------------------------------------------------------------------------------


def exists_id(coll_name: str, oid: ObjectId) -> bool:
    """Tester l’existence d’un ObjectId dans un référentiel.

    Args:
        coll_name: Nom de la collection référentielle.
        oid: Identifiant à vérifier.

    Returns:
        bool: True si l’ObjectId est connu par le cache, sinon False.
    """
    try:
        oid = oid if isinstance(oid, ObjectId) else ObjectId(str(oid))
    except Exception:
        return False
    entry = collections_mapping.get(coll_name) or {}
    return oid in entry.get("ids", set())


def exists_attribute_id(attr_id: int) -> bool:
    """Vérifier l’existence d’un identifiant numérique d’attribut.

    Args:
        attr_id: `cache_attribute_id` numérique.

    Returns:
        bool: True si l’ID numérique est connu, sinon False.
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
    """Résoudre un code/nom vers un ObjectId via le cache.

    Args:
        collection: Nom de collection.
        field: `code` ou `name`.
        value: Valeur fournie (insensible à la casse).

    Returns:
        ObjectId | None: Référence trouvée ou None.
    """
    entry = collections_mapping.get(collection) or {}
    m = entry.get(field) or {}
    return m.get(str(value).lower())


def resolve_attribute_code(code: str) -> tuple[ObjectId, int | None] | None:
    """Résoudre un attribut par code/texte.

    Description:
        Tente d’abord `code`, puis `txt`, et renvoie (ObjectId, `cache_attribute_id`).

    Args:
        code: Code ou identifiant texte (ex. "dogs_allowed").

    Returns:
        tuple[ObjectId, int|None] | None: Référence et ID numérique, ou None si introuvable.
    """
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


def resolve_type_code(code: str) -> ObjectId | None:
    """Résoudre un type de cache par code.

    Args:
        code: Code de type (ex. "TR").

    Returns:
        ObjectId | None: Référence du type.
    """
    return _resolve_code_to_id("cache_types", "code", code)


def resolve_size_code(code: str) -> ObjectId | None:
    """Résoudre une taille de cache par code.

    Args:
        code: Code de taille (ex. "S").

    Returns:
        ObjectId | None: Référence de taille.
    """
    return _resolve_code_to_id("cache_sizes", "code", code)


def resolve_size_name(name: str) -> ObjectId | None:
    """Résoudre une taille de cache par nom.

    Args:
        name: Nom (ex. "Micro").

    Returns:
        ObjectId | None: Référence de taille.
    """
    return _resolve_code_to_id("cache_sizes", "name", name)


def resolve_country_name(name: str) -> ObjectId | None:
    """Résoudre un pays par nom.

    Args:
        name: Nom de pays (ex. "France").

    Returns:
        ObjectId | None: Référence de pays.
    """
    return _resolve_code_to_id("countries", "name", name)


def resolve_state_name(
    state_name: str, *, country_id: ObjectId | None = None
) -> tuple[ObjectId | None, str | None]:
    """Résoudre un État/région par nom (optionnellement borné à un pays).

    Description:
        Si `country_id` n’est pas fourni, gère les ambiguïtés:
        - 0 hit → message « not found »
        - >1 hit → message « ambiguous »

    Args:
        state_name: Nom d’État/région.
        country_id: Filtre pays (ObjectId) pour désambiguïser.

    Returns:
        tuple[ObjectId|None, str|None]: (state_id, message d’erreur ou None).
    """
    entry = collections_mapping.get("states") or {}
    by_country = entry.get("by_country", {})
    target = (state_name or "").lower()

    if country_id:
        key = str(country_id if isinstance(country_id, ObjectId) else ObjectId(str(country_id)))
        sid = (by_country.get(key) or {}).get(target)
        return (sid, None) if sid else (None, f"state not found '{state_name}' in country '{key}'")

    # pas de pays fourni → ambiguïtés possibles
    hits = []
    for _cid, states in by_country.items():
        if target in states:
            hits.append(states[target])
    if not hits:
        return None, f"state name not found '{state_name}'"
    if len(hits) > 1:
        return None, f"state name ambiguous without country '{state_name}'"
    return hits[0], None
