# backend/app/services/gpx_importer.py

import os, math
import io
import zipfile
import datetime as dt
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from xml.etree import ElementTree as ET
from fastapi import HTTPException
from bson import ObjectId
import uuid
from pymongo import UpdateOne

from app.core.utils import *
from app.db.mongodb import get_collection, get_column
from app.services.parsers.GPXCacheParser import GPXCacheParser  # ton parser: __init__(gpx_file: Path), parse()

# --------- Constantes & FS helpers ---------

UPLOADS_DIR = Path("../uploads/gpx").resolve()
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

def _is_zip(buf: bytes) -> bool:
    return buf[:4] == b"PK\x03\x04"

def _safe_join(base: Path, *paths: str) -> Path:
    """Empêche le path traversal lors de l'extraction ZIP."""
    candidate = (base / Path(*paths)).resolve()
    if not str(candidate).startswith(str(base)):
        raise HTTPException(status_code=400, detail="Unsafe path in ZIP")
    return candidate

def _validate_gpx_minimal_bytes(data: bytes) -> None:
    try:
        root = ET.fromstring(data)
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX XML: {e}")
    if "gpx" not in root.tag.lower():
        raise HTTPException(status_code=400, detail="Root element is not <gpx>")

def _validate_gpx_minimal_path(path: Path) -> None:
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except ET.ParseError as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX XML in {path.name}: {e}")
    if "gpx" not in root.tag.lower():
        raise HTTPException(status_code=400, detail=f"{path.name} is not a <gpx> file")

def _write_single_gpx(payload: bytes, filename: Optional[str]) -> Path:
    ext = ".gpx" if not filename or not filename.lower().endswith(".gpx") else ""
    safe_name = (filename or f"upload-{uuid.uuid4().hex}.gpx").replace(os.sep, "_")
    out_path = _safe_join(UPLOADS_DIR, safe_name + ext)
    out_path.write_bytes(payload)
    _validate_gpx_minimal_path(out_path)
    return out_path

def _extract_zip_to_paths(payload: bytes) -> List[Path]:
    paths: List[Path] = []
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
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="Provided file is not a valid ZIP")
    if not paths:
        raise HTTPException(status_code=400, detail="ZIP contains no valid .gpx files")
    return paths

def _materialize_to_paths(payload: bytes, filename: Optional[str]) -> List[Path]:
    """Retourne la liste des paths GPX enregistrés en uploads (ZIP → multi, GPX → 1)."""
    if _is_zip(payload):
        return _extract_zip_to_paths(payload)
    # sinon single GPX
    _validate_gpx_minimal_bytes(payload)
    return [_write_single_gpx(payload, filename)]

# --------- Mapping helpers (IDEM) ---------

def _normalize_name(name: str) -> str:
    return name.strip().casefold()

def _get_all_countries_by_name() -> Dict[str, ObjectId]:
    """
    Retourne un index: nom_normalisé -> country id
    """
    result: Dict[str, ObjectId] = {}
    cursor = get_collection("countries").find({}, {"name": 1})
    result = {_normalize_name(item["name"]):item["_id"] for item in cursor}

    return result

def _get_all_states_by_countryid_and_name() -> Dict[ObjectId, Dict[str, ObjectId]]:
    """
    Retourne un index imbriqué : (country_id, nom_normalisé) -> state id
    """
    result: Dict[ObjectId, Dict[str, ObjectId]] = {}
    cursor = get_collection("states").find({}, {"name": 1, "country_id": 1})
    for item in cursor:
        result[item["country_id"]] = result.get(item["country_id"], {})
        result[item["country_id"]][ _normalize_name(item["name"])] = item["_id"]

    return result

def _get_all_types_by_name() -> Dict[str, ObjectId]:
    """
    Retourne un index: nom_normalisé -> type _id
    """
    result: Dict[str, ObjectId] = {}
    cursor = get_collection("cache_types").find({}, {"label": 1})
    result = {_normalize_name(item["label"]):item["_id"] for item in cursor}

    return result

def _get_all_sizes_by_name() -> Dict[str, ObjectId]:
    """
    Retourne un index: nom_normalisé -> size _id
    """
    result: Dict[str, ObjectId] = {}
    cursor = get_collection("cache_sizes").find({}, {"label": 1})
    result = {_normalize_name(item["label"]):item["_id"] for item in cursor}

    return result

def _get_all_attributes_by_id() -> Dict[int, ObjectId]:
    """
    Retourne un index: id -> attribute _id
    """
    result = {item["id"]:item["_id"] for item in get_collection("cache_attributes").find({}, {"id": 1})}

    return result

def _ensure_country_state(
    country_name: Optional[str],
    state_name: Optional[str],
    all_countries_by_name: Optional[Dict[str, ObjectId]] = None,
    all_states_by_countryid_and_name: Optional[Dict[ObjectId, Dict[str, ObjectId]]] = None
) -> Tuple[Optional[ObjectId], Optional[ObjectId]]:
    """
    Retourne les ObjectId du pays et de l'état.
    Si les dictionnaires indexés ne sont pas fournis, ils sont construits depuis la base.
    """

    # Récupération des pays si nécessaire
    if all_countries_by_name is None:
        all_countries_by_name = _get_all_countries_by_name()

    # Récupération des états si nécessaire
    if all_states_by_countryid_and_name is None:
        all_states_by_countryid_and_name = _get_all_states_by_countryid_and_name()

    country_id = None
    state_id = None

    # Gestion du pays
    if country_name:
        country_id = all_countries_by_name.get(_normalize_name(country_name))
        if country_id is None:
            country_id = get_collection("countries").insert_one({"name": country_name}).inserted_id
            all_countries_by_name[_normalize_name(country_name)] = country_id
            all_states_by_countryid_and_name[country_id] = {}

    # Gestion de l'état
    if state_name and country_id:
        states_for_country = all_states_by_countryid_and_name.get(country_id, {})
        state_id = states_for_country.get(_normalize_name(state_name))
        if state_id is None:
            state_id = get_collection("states").insert_one({
                "name": state_name,
                "country_id": country_id
            }).inserted_id
            states_for_country[_normalize_name(state_name)] = state_id
            all_states_by_countryid_and_name[country_id] = states_for_country

    return country_id, state_id

def get_type_by_name(cache_type_name: Optional[str], all_types_by_name: Optional[Dict[str, ObjectId]] = None):
    synonymes = {
        "unknown" : "mystery",
    }

    cache_type_name = _normalize_name(cache_type_name)
    type_id = all_types_by_name.get(cache_type_name, None)
    if type_id is None:
        for db_name, db_id in all_types_by_name.items():
            if db_name in cache_type_name or cache_type_name in db_name:
                type_id = db_id
                break
    if type_id is None:
        for key, label in synonymes.items():
            if key in cache_type_name:
                for db_name, db_id in all_types_by_name.items():
                    if label in db_name:
                        type_id = db_id
                        break
                if type_id is not None:
                    break

    return type_id

def get_size_by_name(cache_size_name: Optional[str], all_sizes_by_name: Optional[Dict[str, ObjectId]] = None):
    cache_size_name = _normalize_name(cache_size_name)
    size_id = all_sizes_by_name.get(cache_size_name, None)
    if size_id is None:
        for db_name, db_id in all_sizes_by_name.items():
            if db_name in cache_size_name or cache_size_name in db_name:
                size_id = db_id
                break

    return size_id

def _map_type_size_attrs(cache_type_name: Optional[str], cache_size_name: Optional[str], cache_attributes: Optional[List] = [], all_types_by_name: Optional[Dict[str, ObjectId]] = None, all_sizes_by_name: Optional[Dict[str, ObjectId]] = None, all_attributes_by_id: Optional[Dict[int, ObjectId]] = None) -> tuple[Optional[ObjectId], Optional[ObjectId], list]:
    if all_types_by_name is None:
        all_types_by_name = _get_all_types_by_name()
    if all_sizes_by_name is None:
        all_sizes_by_name = _get_all_sizes_by_name()
    if all_attributes_by_id is None:
        all_attributes_by_id = _get_all_attributes_by_id()

    type_id = get_type_by_name(cache_type_name, all_types_by_name)
    size_id = get_size_by_name(cache_size_name, all_sizes_by_name)
    attr_refs = []

    for cache_attribute in cache_attributes:
        attribute_id = cache_attribute.get("id", None)
        attribute_object_id = all_attributes_by_id.get(attribute_id, None)
        if attribute_object_id is None:
            continue
        is_positive = cache_attribute.get("is_positive", True)
        attr_refs.append({"attribute_id": attribute_object_id, "is_positive": bool(is_positive)})

    return type_id, size_id, attr_refs

def _parse_dt_iso8601(s: Optional[str]) -> Optional[dt.datetime]:
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return dt.datetime.fromisoformat(s)
    except Exception:
        return None

# --------- Import principal ---------

def import_gpx_payload(payload: bytes, filename: str, user: dict, found: bool) -> dict:
    """
    1) Matérialise le payload en fichiers dans backend/uploads/gpx
       - ZIP → dézippe, retourne la liste des .gpx extraits
       - GPX → sauvegarde le fichier, retourne [path]
    2) Parse chaque path avec GPXCacheParser(gpx_file=Path)
    3) Insère caches (upsert par GC), puis found_caches si found=True & found_date
    """
    gpx_paths = _materialize_to_paths(payload, filename)

    caches_collection = get_collection("caches")
    found_caches_collection = get_collection("found_caches")

    nb_inserted_caches = 0
    nb_existing_caches = 0
    nb_inserted_found_caches = 0
    nb_updated_found_caches = 0
    all_countries_by_name = _get_all_countries_by_name()
    all_states_by_countryid_and_name = _get_all_states_by_countryid_and_name()
    all_types_by_name = _get_all_types_by_name()
    all_sizes_by_name = _get_all_sizes_by_name()
    all_attributes_by_id = _get_all_attributes_by_id()

    nb_countries_before = len(all_countries_by_name)
    nb_states_before = sum(len(states_country) for country_id, states_country in all_states_by_countryid_and_name.items())

    def _as_float(x, default=0.0):
        try:
            return float(x)
        except Exception:
            return default

    # Récupérer les GC connus
    known_gcs = get_column("caches", "GC")

    items = []
    for path in gpx_paths:
        parser = GPXCacheParser(gpx_file=path)
        items = parser.parse()

        all_caches_to_db = []
        for item in items:
            gc = item.get("GC")
            if not gc:
                continue

            if gc in known_gcs:
                nb_existing_caches += 1
                continue

            _, state_id = _ensure_country_state(item.get("country"), item.get("state"), all_countries_by_name, all_states_by_countryid_and_name)
            type_id, size_id, attr_refs = _map_type_size_attrs(
                item.get("cache_type"),
                item.get("cache_size"),
                item.get("attributes"),
                all_types_by_name,
                all_sizes_by_name,
                all_attributes_by_id
            )
            placed_dt = _parse_dt_iso8601(item.get("placed_date")) or None
            item_to_db = {
                "GC": gc,
                "title": item.get("title"),
                "description_html": item.get("description_html"),
                "cache_type": type_id,
                "size": size_id,
                "difficulty": _as_float(item.get("difficulty")),
                "terrain": _as_float(item.get("terrain")),
                "placed_date": placed_dt,
                "latitude": float(item.get("latitude")),
                "longitude": float(item.get("longitude")),
                "elevation": item.get("elevation"),
                "state_id": state_id,
                "location_more": None,
                "attributes": attr_refs,
                "owner": item.get("owner"),
                "favorites": item.get("favorites"),
                "created_at": now(),
            }
            all_caches_to_db.append(item_to_db)

        nb_items_to_db = len(all_caches_to_db)
        INSERTS_CHUNK_SIZE = 100
        nb_chunks = math.ceil(nb_items_to_db / INSERTS_CHUNK_SIZE)
        items_to_db_chunks = [all_caches_to_db[i * INSERTS_CHUNK_SIZE:min(nb_items_to_db, (i+1) * INSERTS_CHUNK_SIZE)] for i in range(nb_chunks)]
        for i, items_to_db_chunk in enumerate(items_to_db_chunks):
            result_chunk = caches_collection.insert_many(items_to_db_chunk)
            nb_inserted_caches+= len(result_chunk.inserted_ids)

    if found:
        founds_ops = []
        found_caches_by_gc = {}
        for item in items:
            found_date = _parse_dt_iso8601(item.get("found_date"))
            if found_date:
                found_cache_gc = item.get("GC")
                found_cache = {
                    "found_date": found_date,
                    "notes": item.get("notes")
                }
                found_caches_by_gc[found_cache_gc] = found_cache
        if found_caches_by_gc:
            found_caches_in_db_ids = {item["GC"]: item["_id"] for item in caches_collection.find(
                {"GC": {"$in": list(found_caches_by_gc.keys())}},
                {"_id": 1, "GC": 1}
            )}
            for gc, db_cache_id in found_caches_in_db_ids.items():
                found_caches_by_gc[gc].update({
                    "cache_id": db_cache_id,
                    "user_id": user["_id"],
                })
        found_caches_to_db = list(found_caches_by_gc.values())
        for item in found_caches_to_db:
            print("item", item)
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

            founds_ops.append(UpdateOne(q, update, upsert=True))

        result_found = found_caches_collection.bulk_write(founds_ops, ordered=False)
        nb_inserted_found_caches = result_found.upserted_count
        nb_updated_found_caches = result_found.modified_count

    nb_countries_after = get_collection("countries").count_documents({})
    nb_states_after = get_collection("states").count_documents({})

    return {
        "nb_gpx_files": len(gpx_paths),
        "nb_inserted_caches": nb_inserted_caches,
        "nb_existing_caches": nb_existing_caches,
        "nb_inserted_found_caches": nb_inserted_found_caches,
        "nb_updated_found_caches": nb_updated_found_caches,
        "nb_new_countries": nb_countries_after - nb_countries_before,
        "nb_new_states": nb_states_after - nb_states_before,
    }
