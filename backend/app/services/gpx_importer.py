# backend/app/services/gpx_importer.py
# Importe des caches depuis un fichier GPX (ou un ZIP de GPX), mappe référentiels, enrichit (altitude), et upsert found_caches.

import asyncio
import datetime as dt
import io
import math
import os
import uuid
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from bson import ObjectId
from fastapi import HTTPException
from pymongo import UpdateOne
from pymongo.errors import BulkWriteError

from app.core.utils import now
from app.db.mongodb import get_collection, get_distinct
from app.services.elevation_retrieval import fetch as fetch_elevations
from app.services.parsers.GPXCacheParser import (
    GPXCacheParser,
)  # ton parser: __init__(gpx_file: Path), parse()

# --------- Constantes & FS helpers ---------

UPLOADS_DIR = Path("../uploads/gpx").resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def _is_zip(buf: bytes) -> bool:
    """Détecter un ZIP via signature magique.

    Description:
        Vérifie les 4 premiers octets (`PK\\x03\\x04`) pour identifier un fichier ZIP.

    Args:
        buf (bytes): En-tête de fichier.

    Returns:
        bool: True si ZIP, sinon False.
    """
    return buf[:4] == b"PK\x03\x04"


def _safe_join(base: Path, *paths: str) -> Path:
    """Joindre des chemins en empêchant le path traversal.

    Description:
        Résout le chemin cible et vérifie qu’il est bien **sous** `base`. Lève une 400 sinon.

    Args:
        base (Path): Répertoire racine autorisé.
        *paths (str): Segments à joindre.

    Returns:
        Path: Chemin final sécurisé.

    Raises:
        fastapi.HTTPException: 400 si tentative de path traversal.
    """
    candidate = (base / Path(*paths)).resolve()
    if not str(candidate).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Unsafe path in ZIP")
    return candidate


def _validate_gpx_minimal_bytes(data: bytes) -> None:
    """Valider grossièrement un GPX (buffer en mémoire).

    Description:
        Parse le XML et vérifie que la racine contient `gpx`. Lève une 400 en cas d’échec.

    Args:
        data (bytes): Contenu du fichier GPX.

    Returns:
        None

    Raises:
        fastapi.HTTPException: 400 si XML invalide ou racine != gpx.
    """
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX XML: {e}") from e
    if "gpx" not in root.tag.lower():
        raise HTTPException(status_code=400, detail="Root element is not <gpx>")


def _validate_gpx_minimal_path(path: Path) -> None:
    """Valider grossièrement un GPX (depuis un fichier sur disque).

    Description:
        Parse le XML en chemin et vérifie la racine `gpx`. Lève une 400 en cas d’échec.

    Args:
        path (Path): Chemin du fichier GPX.

    Returns:
        None

    Raises:
        fastapi.HTTPException: 400 si XML invalide ou racine != gpx.
    """
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX XML in {path.name}: {e}") from e
    if "gpx" not in root.tag.lower():
        raise HTTPException(status_code=400, detail=f"{path.name} is not a <gpx> file")


def _write_single_gpx(payload: bytes, filename: str | None) -> Path:
    """Écrire un GPX unique dans le répertoire d’uploads.

    Description:
        Sanitize le nom, force l’extension `.gpx`, écrit le fichier, puis revalide le contenu.

    Args:
        payload (bytes): Données GPX brutes.
        filename (str | None): Nom d’origine (facultatif).

    Returns:
        Path: Chemin du fichier écrit (validé).
    """
    base = (filename or f"upload-{uuid.uuid4().hex}").replace(os.sep, "_")
    if not base.lower().endswith(".gpx"):
        base += ".gpx"
    out_path = _safe_join(UPLOADS_DIR, base)
    out_path.write_bytes(payload)
    _validate_gpx_minimal_path(out_path)
    return out_path


def _extract_zip_to_paths(payload: bytes) -> list[Path]:
    """Extraire les .gpx d’un ZIP vers le répertoire d’uploads.

    Description:
        Parcourt les entrées du ZIP, ignore les répertoires et les fichiers non `.gpx`,
        sécurise les chemins via `_safe_join`, écrit et valide chaque GPX.

    Args:
        payload (bytes): Contenu du fichier ZIP.

    Returns:
        list[Path]: Chemins des fichiers GPX extraits.

    Raises:
        fastapi.HTTPException: 400 si archive invalide ou si aucun GPX valide n’est présent.
    """
    paths: list[Path] = []
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                name = info.filename
                if not name.lower().endswith(".gpx"):
                    # on ignore tout sauf .gpx
                    continue
                # sécurise le chemin et écrit
                dest = _safe_join(UPLOADS_DIR, f"{uuid.uuid4().hex}-{Path(name).name}")
                with z.open(info) as src, open(dest, "wb") as dst:
                    dst.write(src.read())
                _validate_gpx_minimal_path(dest)
                paths.append(dest)
    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail="Provided file is not a valid ZIP") from e
    if not paths:
        raise HTTPException(status_code=400, detail="ZIP contains no valid .gpx files")
    return paths


def _materialize_to_paths(payload: bytes, filename: str | None) -> list[Path]:
    """Matérialiser un upload (ZIP→multi ou GPX→unique) en fichiers sur disque.

    Description:
        - Si ZIP: dézippe via `_extract_zip_to_paths`.
        - Sinon: écrit via `_write_single_gpx` après validation basique.

    Args:
        payload (bytes): Données uploadées.
        filename (str | None): Nom d’origine (pour labelliser le fichier écrit).

    Returns:
        list[Path]: Liste des chemins GPX matérialisés.
    """
    if _is_zip(payload):
        return _extract_zip_to_paths(payload)
    # sinon single GPX
    _validate_gpx_minimal_bytes(payload)
    return [_write_single_gpx(payload, filename)]


# --------- Mapping helpers (IDEM) ---------


def _normalize_name(name: str | None) -> str:
    """Normaliser un libellé pour matching référentiel.

    Description:
        Trim et `casefold()` pour des comparaisons tolérantes (ex. « micro » vs « Micro »).

    Args:
        name (str | None): Libellé source.

    Returns:
        str: Libellé normalisé (éventuellement chaîne vide).
    """
    return (name or "").strip().casefold()


async def _get_all_countries_by_name() -> dict[str, ObjectId]:
    """Indexer les pays par nom normalisé.

    Description:
        Construit `{name_normalized: country._id}` depuis `countries`.

    Returns:
        dict[str, ObjectId]: Index des pays.
    """
    result: dict[str, ObjectId] = {}
    coll_countries = await get_collection("countries")
    cursor = coll_countries.find({}, {"name": 1})
    result = {_normalize_name(item["name"]): item["_id"] async for item in cursor}

    return result


async def _get_all_states_by_countryid_and_name() -> dict[ObjectId, dict[str, ObjectId]]:
    """Indexer les états par (country_id, nom).

    Description:
        Construit `{country_id: {state_name_normalized: state._id}}` depuis `states`.

    Returns:
        dict[ObjectId, dict[str, ObjectId]]: Index imbriqué pays→états.
    """
    result: dict[ObjectId, dict[str, ObjectId]] = {}
    coll_states = await get_collection("states")
    cursor = coll_states.find({}, {"name": 1, "country_id": 1})
    async for item in cursor:
        result[item["country_id"]] = result.get(item["country_id"], {})
        result[item["country_id"]][_normalize_name(item["name"])] = item["_id"]

    return result


async def _get_all_types_by_name() -> dict[str, ObjectId]:
    """Indexer les types par nom normalisé.

    Returns:
        dict[str, ObjectId]: `{type_name: _id}` depuis `cache_types`.
    """
    result: dict[str, ObjectId] = {}
    coll_types = await get_collection("cache_types")
    cursor = coll_types.find({}, {"name": 1})
    result = {_normalize_name(item["name"]): item["_id"] async for item in cursor}

    return result


async def _get_all_sizes_by_name() -> dict[str, ObjectId]:
    """Indexer les tailles par nom normalisé.

    Returns:
        dict[str, ObjectId]: `{size_name: _id}` depuis `cache_sizes`.
    """
    result: dict[str, ObjectId] = {}
    coll_sizes = await get_collection("cache_sizes")
    cursor = coll_sizes.find({}, {"name": 1})
    result = {_normalize_name(item["name"]): item["_id"] async for item in cursor}

    return result


async def _get_all_attributes_by_id() -> dict[int, ObjectId]:
    """Indexer les attributs par identifiant numérique global.

    Returns:
        dict[int, ObjectId]: `{cache_attribute_id: _id}` depuis `cache_attributes`.
    """
    coll_attrs = await get_collection("cache_attributes")
    cursor = coll_attrs.find({}, {"cache_attribute_id": 1})
    result = {item["cache_attribute_id"]: item["_id"] async for item in cursor}

    return result


async def _ensure_country_state(
    country_name: str | None,
    state_name: str | None,
    all_countries_by_name: dict[str, ObjectId] | None = None,
    all_states_by_countryid_and_name: dict[ObjectId, dict[str, ObjectId]] | None = None,
) -> tuple[ObjectId | None, ObjectId | None]:
    """Garantir l’existence (et récupérer les _id) d’un pays/état.

    Description:
        Retourne les `_id` du pays et de l’état ; crée les documents manquants si nécessaires
        et met à jour les index en mémoire passés en paramètres.

    Args:
        country_name (str | None): Nom du pays.
        state_name (str | None): Nom de l’état/région.
        all_countries_by_name (dict | None): Index pays (peut être fourni pour éviter des lectures DB).
        all_states_by_countryid_and_name (dict | None): Index états (idem).

    Returns:
        tuple[ObjectId | None, ObjectId | None]: `(country_id, state_id)`.
    """

    # Récupération des pays si nécessaire
    if all_countries_by_name is None:
        all_countries_by_name = await _get_all_countries_by_name()

    # Récupération des états si nécessaire
    if all_states_by_countryid_and_name is None:
        all_states_by_countryid_and_name = await _get_all_states_by_countryid_and_name()

    country_id = None
    state_id = None

    # Gestion du pays
    if country_name:
        country_id = all_countries_by_name.get(_normalize_name(country_name))
        if country_id is None:
            coll_countries = await get_collection("countries")
            result = await coll_countries.insert_one({"name": country_name})
            country_id = result.inserted_id
            all_countries_by_name[_normalize_name(country_name)] = country_id
            all_states_by_countryid_and_name[country_id] = {}

    # Gestion de l'étatattr_refs
    if state_name and country_id:
        states_for_country = all_states_by_countryid_and_name.get(country_id, {})
        state_id = states_for_country.get(_normalize_name(state_name))
        if state_id is None:
            coll_states = await get_collection("states")
            result = await coll_states.insert_one({"name": state_name, "country_id": country_id})
            state_id = result.inserted_id
            states_for_country[_normalize_name(state_name)] = state_id
            all_states_by_countryid_and_name[country_id] = states_for_country

    return country_id, state_id


def get_type_by_name(
    cache_type_name: str | None,
    all_types_by_name: dict[str, ObjectId] | None = None,
):
    """Résoudre le type par nom (avec synonymes).

    Description:
        Tente d’abord une correspondance exacte via l’index, puis des correspondances partielles,
        et enfin un mapping de synonymes (ex. "unknown" → "mystery"). Retourne l’ObjectId ou None.

    Args:
        cache_type_name (str | None): Libellé type (ex. "Traditional").
        all_types_by_name (dict | None): Index `{name_normalized: _id}` (recommandé).

    Returns:
        ObjectId | None: Référence du type si résolue.
    """
    synonymes = {
        "unknown": "mystery",
    }

    cache_type_name = _normalize_name(cache_type_name)
    type_id: ObjectId | None = None
    if isinstance(all_types_by_name, dict):
        type_id = all_types_by_name.get(cache_type_name, None)
    if type_id is None:
        if isinstance(all_types_by_name, dict):
            for db_name, db_id in all_types_by_name.items():
                if db_name in cache_type_name or cache_type_name in db_name:
                    type_id = db_id
                    break
    if type_id is None:
        for key, label in synonymes.items():
            if key in cache_type_name:
                if isinstance(all_types_by_name, dict):
                    for db_name, db_id in all_types_by_name.items():
                        if label in db_name:
                            type_id = db_id
                            break
                if type_id is not None:
                    break

    return type_id


def get_size_by_name(
    cache_size_name: str | None,
    all_sizes_by_name: dict[str, ObjectId] | None = None,
):
    """Résoudre la taille par nom.

    Description:
        Similarité avec `get_type_by_name` : exact puis partiel, retourne l’ObjectId ou None.

    Args:
        cache_size_name (str | None): Libellé taille (ex. "Micro").
        all_sizes_by_name (dict | None): Index `{name_normalized: _id}`.

    Returns:
        ObjectId | None: Référence de la taille si résolue.
    """
    cache_size_name = _normalize_name(cache_size_name)
    size_id: ObjectId | None = None
    if isinstance(all_sizes_by_name, dict):
        size_id = all_sizes_by_name.get(cache_size_name, None)
    if size_id is None:
        if isinstance(all_sizes_by_name, dict):
            for db_name, db_id in all_sizes_by_name.items():
                if db_name in cache_size_name or cache_size_name in db_name:
                    size_id = db_id
                    break

    return size_id


async def _map_type_size_attrs(
    cache_type_name: str | None,
    cache_size_name: str | None,
    cache_attributes: list | None = None,
    all_types_by_name: dict[str, ObjectId] | None = None,
    all_sizes_by_name: dict[str, ObjectId] | None = None,
    all_attributes_by_id: dict[int, ObjectId] | None = None,
) -> tuple[ObjectId | None, ObjectId | None, list]:
    """Mapper type/size/attributes vers des références Mongo.

    Description:
        Résout les `type_id` et `size_id` puis convertit les attributs en
        `{'attribute_doc_id': ObjectId, 'is_positive': bool}`.

    Args:
        cache_type_name (str | None): Libellé type.
        cache_size_name (str | None): Libellé taille.
        cache_attributes (list | None): Attributs GPX (id + is_positive).
        all_types_by_name (dict | None): Index types.
        all_sizes_by_name (dict | None): Index tailles.
        all_attributes_by_id (dict | None): Index attributs.

    Returns:
        tuple[ObjectId | None, ObjectId | None, list]: `(type_id, size_id, attr_refs)`.
    """
    cache_attributes = cache_attributes or []
    if all_types_by_name is None:
        all_types_by_name = await _get_all_types_by_name()
    if all_sizes_by_name is None:
        all_sizes_by_name = await _get_all_sizes_by_name()
    if all_attributes_by_id is None:
        all_attributes_by_id = await _get_all_attributes_by_id()

    type_id = get_type_by_name(cache_type_name, all_types_by_name)
    size_id = get_size_by_name(cache_size_name, all_sizes_by_name)
    attr_refs = []

    for cache_attribute in cache_attributes:
        attribute_id = cache_attribute.get("id", None)
        attribute_object_id = all_attributes_by_id.get(attribute_id, None)
        if attribute_object_id is None:
            continue
        is_positive = cache_attribute.get("is_positive", True)
        attr_refs.append(
            {"attribute_doc_id": attribute_object_id, "is_positive": bool(is_positive)}
        )

    return type_id, size_id, attr_refs


def _parse_dt_iso8601(s: str | None) -> dt.datetime | None:
    """Parser ISO 8601 (support 'Z') vers `datetime`.

    Args:
        s (str | None): Chaîne de date/heure.

    Returns:
        datetime | None: Objet `datetime` ou None si parsing impossible.
    """
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None


# --------- Import principal ---------


async def import_gpx_payload(payload: bytes, filename: str, found: bool, user_id: ObjectId) -> dict:
    """Importer des caches depuis un upload GPX/ZIP (avec enrichissements).

    Description:
        1) Matérialise l’upload en fichiers GPX (ZIP → multi) dans `../uploads/gpx` (sécurité path traversal).\n
        2) Parse via `GPXCacheParser` pour extraire les champs utiles.\n
        3) Upsert des documents `caches` (par `GC`) avec mapping référentiels + `loc` GeoJSON.\n
        4) **Enrichit l’altitude** (si lat/lon) via `services.elevation_retrieval.fetch`.\n
        5) Si `found=True`, upsert des `found_caches` (par `user_id` + `cache_id`), gère `notes` et timestamps.

    Args:
        payload (bytes): Contenu du fichier uploadé (GPX ou ZIP).
        filename (str): Nom de fichier d’origine (pour étiquette de sortie).
        user (dict): Utilisateur courant (pour `found_caches`).
        found (bool): Créer/mettre à jour les logs de trouvailles.

    Returns:
        dict: Résumé : `nb_gpx_files`, `nb_inserted_caches`, `nb_existing_caches`,
              `nb_inserted_found_caches`, `nb_updated_found_caches`,
              `nb_new_countries`, `nb_new_states`.
    """
    loop = asyncio.get_running_loop()
    gpx_paths = await loop.run_in_executor(None, _materialize_to_paths, payload, filename)

    caches_collection = await get_collection("caches")
    found_caches_collection = await get_collection("found_caches")

    nb_inserted_caches = 0
    nb_existing_caches = 0
    nb_inserted_found_caches = 0
    nb_updated_found_caches = 0
    all_countries_by_name = await _get_all_countries_by_name()
    all_states_by_countryid_and_name = await _get_all_states_by_countryid_and_name()
    all_types_by_name = await _get_all_types_by_name()
    all_sizes_by_name = await _get_all_sizes_by_name()
    all_attributes_by_id = await _get_all_attributes_by_id()

    nb_countries_before = len(all_countries_by_name)
    nb_states_before = sum(
        len(states_country)
        for country_id, states_country in all_states_by_countryid_and_name.items()
    )

    def _as_float(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    # Récupérer les GC connus (distinct côté serveur -> moins d'I/O et pas de doublons)
    known_gcs = set(await get_distinct("caches", "GC"))
    seen_gcs: set[str] = set()

    items = []
    for path in gpx_paths:
        parser = GPXCacheParser(gpx_file=path)
        items.extend(parser.parse())

    all_caches_to_db = []
    for item in items:
        gc = item.get("GC")
        if not gc:
            continue

        if gc in known_gcs or gc in seen_gcs:
            nb_existing_caches += 1
            continue

        lat = _as_float(item.get("latitude"))
        lon = _as_float(item.get("longitude"))
        loc = (
            {"type": "Point", "coordinates": [lon, lat]}
            if lat is not None and lon is not None
            else None
        )

        country_id, state_id = await _ensure_country_state(
            item.get("country"),
            item.get("state"),
            all_countries_by_name,
            all_states_by_countryid_and_name,
        )
        type_id, size_id, attr_refs = await _map_type_size_attrs(
            item.get("cache_type"),
            item.get("cache_size"),
            item.get("attributes"),
            all_types_by_name,
            all_sizes_by_name,
            all_attributes_by_id,
        )
        placed_dt = _parse_dt_iso8601(item.get("placed_date")) or None
        item_to_db = {
            "GC": gc,
            "title": item.get("title"),
            "description_html": item.get("description_html"),
            "type_id": type_id,
            "size_id": size_id,
            "difficulty": _as_float(item.get("difficulty"), default=None),
            "terrain": _as_float(item.get("terrain"), default=None),
            "placed_at": placed_dt,
            "lat": lat,
            "lon": lon,
            "loc": loc,
            "elevation": None,
            "country_id": country_id,
            "state_id": state_id,
            "location_more": None,
            "attributes": attr_refs,
            "owner": item.get("owner"),
            "favorites": int(item.get("favorites") or 0),
            "created_at": now(),
        }
        all_caches_to_db.append(item_to_db)
        seen_gcs.add(gc)

    # Ajout elevation
    to_enrich_idx = []
    points = []  # liste de tuples (lat, lon) pour l’API OpenTopo

    for i, doc in enumerate(all_caches_to_db):
        # On n’enrichit QUE les docs qui ont lat/lon valides et pas d’elevation
        lat = doc.get("lat")
        lon = doc.get("lon")
        if lat is None or lon is None:
            continue
        if doc.get("elevation") is not None:
            continue
        to_enrich_idx.append(i)
        # ⚠️ OpenTopoData attend "lat,lon" (ton loc interne est [lon, lat])
        points.append((float(lat), float(lon)))

    # Appel au service (gère batching, 100 pts max, URL max, 1 req/s, quotas…)
    if points:
        elevations = await fetch_elevations(points)  # renvoie une liste alignée de int | None

        # Réinjection dans les docs correspondants (on laisse None si échec)
        for k, elev in enumerate(elevations):
            if elev is not None:
                all_caches_to_db[to_enrich_idx[k]]["elevation"] = int(elev)

    nb_items_to_db = len(all_caches_to_db)
    INSERTS_CHUNK_SIZE = 100
    nb_chunks = math.ceil(nb_items_to_db / INSERTS_CHUNK_SIZE)
    items_to_db_chunks = [
        all_caches_to_db[i * INSERTS_CHUNK_SIZE : min(nb_items_to_db, (i + 1) * INSERTS_CHUNK_SIZE)]
        for i in range(nb_chunks)
    ]
    for _i, items_to_db_chunk in enumerate(items_to_db_chunks):
        try:
            result_chunk = await caches_collection.insert_many(items_to_db_chunk)
            nb_inserted_caches += len(result_chunk.inserted_ids)
        except BulkWriteError as bwe:
            # Compter les duplicates comme existants et continuer
            for err in bwe.details.get("writeErrors", []):
                if err.get("code") == 11000:
                    nb_existing_caches += 1

    if found:
        found_ops = []
        found_caches_by_gc = {}
        for item in items:
            found_date = _parse_dt_iso8601(item.get("found_date"))
            if item.get("GC") and found_date:
                # stocker un datetime "minuit" (naïf) pour être compatible PyMongo
                found_dt = dt.datetime(found_date.year, found_date.month, found_date.day)
                found_caches_by_gc[item["GC"]] = {
                    "found_date": found_dt,  # <-- OK: type datetime
                    "notes": item.get("notes"),
                }
        if found_caches_by_gc:
            cursor = caches_collection.find(
                {"GC": {"$in": list(found_caches_by_gc.keys())}},
                {"_id": 1, "GC": 1},
            )
            found_caches_in_db_ids = {item["GC"]: item["_id"] async for item in cursor}
            for gc, db_cache_id in found_caches_in_db_ids.items():
                found_caches_by_gc[gc].update(
                    {
                        "cache_id": db_cache_id,
                        "user_id": user_id,
                    }
                )
        # map GC -> cache _id en base
        cursor = caches_collection.find(
            {"GC": {"$in": list(found_caches_by_gc.keys())}}, {"_id": 1, "GC": 1}
        )
        found_caches_in_db_ids = {item["GC"]: item["_id"] async for item in cursor}

        # ne garder que les items avec cache_id présent
        found_caches_to_db = []
        for gc, meta in found_caches_by_gc.items():
            cache_id = found_caches_in_db_ids.get(gc)
            if not cache_id:
                continue
            doc = {
                "cache_id": cache_id,
                "user_id": user_id,
                "found_date": meta["found_date"],
            }
            if "notes" in meta:
                doc["notes"] = meta["notes"]
            found_caches_to_db.append(doc)

        for item in found_caches_to_db:
            q = {"user_id": item["user_id"], "cache_id": item["cache_id"]}
            update = {
                "$setOnInsert": {
                    "found_date": item["found_date"],
                    "created_at": now(),
                },
                "$set": {"updated_at": now()},
            }
            # notes: set si fourni, sinon ne pas toucher ; si None -> $unset
            if "notes" in item:
                if item["notes"] is None:
                    update["$unset"] = {"notes": ""}
                else:
                    update["$set"]["notes"] = item["notes"]

            found_ops.append(UpdateOne(q, update, upsert=True))

        if found_ops:
            result_found = await found_caches_collection.bulk_write(found_ops, ordered=False)
            nb_inserted_found_caches = result_found.upserted_count
            nb_updated_found_caches = result_found.modified_count
        else:
            nb_inserted_found_caches = 0
            nb_updated_found_caches = 0

    collection = await get_collection("countries")
    nb_countries_after = await collection.count_documents({})
    collection = await get_collection("states")
    nb_states_after = await collection.count_documents({})

    return {
        "nb_gpx_files": len(gpx_paths),
        "nb_inserted_caches": nb_inserted_caches,
        "nb_existing_caches": nb_existing_caches,
        "nb_inserted_found_caches": nb_inserted_found_caches,
        "nb_updated_found_caches": nb_updated_found_caches,
        "nb_new_countries": nb_countries_after - nb_countries_before,
        "nb_new_states": nb_states_after - nb_states_before,
    }
