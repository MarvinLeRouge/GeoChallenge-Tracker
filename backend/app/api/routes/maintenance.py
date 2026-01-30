# app/api/routes/maintenance.py

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping, Sequence
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from zipfile import ZIP_DEFLATED, ZipFile

from bson import ObjectId, json_util
from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
)
from fastapi.responses import FileResponse

from app.core.config_backup import BACKUP_ROOT_DIR, CLEANUP_BACKUP_DIR, FULL_BACKUP_DIR
from app.core.security import CurrentUserId, require_admin
from app.core.utils import utcnow
from app.db.mongodb import db, get_collection
from app.services.gpx_importer_service import import_gpx_payload

# Cache en mémoire
cleanup_cache: dict = {}
# Durée de validité de la clé de confirmation (en minutes)
CONFIRMATION_KEY_TTL = 10

# Order matters for deletion: most central to most dependent (to prevent creating new orphans during cleanup)
COLLECTION_DEPENDENCY_ORDER = [
    "countries",  # Level 0: no dependencies
    "cache_types",  # Level 0: no dependencies
    "cache_sizes",  # Level 0: no dependencies
    "cache_attributes",  # Level 0: no dependencies
    "users",  # Level 0: no dependencies
    "states",  # Level 1: depends on countries
    "caches",  # Level 1: depends on cache_types, cache_sizes, countries, states, cache_attributes (nested)
    "challenges",  # Level 2: depends on caches
    "user_challenges",  # Level 3: depends on users, challenges
    "found_caches",  # Level 3: depends on users, caches
    "user_challenge_tasks",  # Level 4: depends on user_challenges
    "progress",  # Level 4: depends on user_challenges
    "targets",  # Level 5: depends on users, user_challenges, caches, user_challenge_tasks
]

REFERENCES_MAP = {
    "caches": {
        "country_id": "countries",
        "state_id": "states",
        "type_id": "cache_types",  # Added: CacheType reference
        "size_id": "cache_sizes",  # Added: CacheSize reference
    },
    "challenges": {
        "cache_id": "caches",
    },
    "found_caches": {
        "cache_id": "caches",
        "user_id": "users",
    },
    "progress": {
        "user_challenge_id": "user_challenges",
    },
    "states": {
        "country_id": "countries",
    },
    "targets": {
        "user_id": "users",
        "user_challenge_id": "user_challenges",
        "cache_id": "caches",
        "primary_task_id": "user_challenge_tasks",
    },
    "user_challenge_tasks": {
        "user_challenge_id": "user_challenges",
    },
    "user_challenges": {
        "challenge_id": "challenges",
        "user_id": "users",
    },
}


async def find_nested_array_orphans(collection_name: str, field_path: str, ref_collection: str):
    """
    Find orphan references in nested arrays (like caches.attributes.attribute_doc_id -> cache_attributes)

    Args:
        collection_name: Source collection name
        field_path: Dot notation path to the nested field (e.g., "attributes.attribute_doc_id")
        ref_collection: Target collection name for reference check
    """
    # Split the field_path to get the array field and the nested reference field
    parts = field_path.split(".")
    if len(parts) < 2:
        return []

    array_field = ".".join(parts[:-1])  # "attributes"
    nested_field = parts[-1]  # "attribute_doc_id"

    # Get all valid IDs from the reference collection
    ref_collection_obj = await get_collection(ref_collection)
    valid_ids = await ref_collection_obj.distinct("_id")

    # Use aggregation to find documents with nested references that are not in valid_ids
    pipeline = [
        # Unwind the array to work with individual elements
        {"$unwind": f"${array_field}"},
        # Match where the nested field exists and is not in valid_ids
        {
            "$match": {
                f"{array_field}.{nested_field}": {"$exists": True, "$ne": None, "$nin": valid_ids}
            }
        },
        # Project the document _id and the problematic reference
        {
            "$project": {
                "_id": 1,
                "problematic_ref": f"${array_field}.{nested_field}",
                "full_array_item": f"${array_field}",
            }
        },
    ]

    collection_obj = await get_collection(collection_name)
    cursor = collection_obj.aggregate(cast(Sequence[Mapping[str, Any]], pipeline))
    orphan_docs = await cursor.to_list(length=None)

    # Extract unique document IDs that contain orphaned references
    orphan_ids = list(set(str(doc["_id"]) for doc in orphan_docs))
    return orphan_ids


# ============================================================================
# UTILITAIRES
# ============================================================================


def serialize_mongo_doc(doc):
    """Convertit un document Mongo (avec ObjectId) en dict JSON-serializable"""
    return json.loads(json_util.dumps(doc))


def clean_expired_keys():
    """Nettoie les clés de confirmation expirées du cache"""
    now = utcnow()
    expired = [k for k, v in cleanup_cache.items() if v["expires_at"] < now]
    for key in expired:
        del cleanup_cache[key]


router = APIRouter(
    prefix="/maintenance", tags=["maintenance"], dependencies=[Depends(require_admin)]
)


# DONE: [BACKLOG] Route /maintenance (GET) à vérifier
@router.get("")
async def maintenance_get_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "GET",
        "function": "maintenance_get_1",
    }

    return result


# DONE: [BACKLOG] Route /maintenance (POST) à vérifier
@router.post("")
async def maintenance_post_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "POST",
        "function": "maintenance_post_1",
    }

    return result


# ============================================================================
# ROUTES
# ============================================================================

# ============================================================================
# ANALYSE DES ORPHELINS
# ============================================================================


# DONE: [BACKLOG] Route /maintenance/db_cleanup (GET) à vérifier
@router.get("/db_cleanup")
async def cleanup_analyze():
    """
    Analyse la base de données pour détecter les enregistrements orphelins.
    Analyse du plus central vers le plus périphérique pour détecter les orphelins directs et indirects.
    Simule le processus de suppression pour détecter tous les orphelins potentiels.
    Retourne un rapport et une clé de confirmation pour le nettoyage.
    """
    clean_expired_keys()

    # Create a map of all references in the system: target_collection -> [(source_collection, field), ...]
    collection_references = {}
    for ref_key, target_collection in {
        **{
            f"{coll}.{field}": ref_coll
            for coll, field_refs in REFERENCES_MAP.items()
            for field, ref_coll in field_refs.items()
        },
        "caches.attributes.attribute_doc_id": "cache_attributes",
    }.items():
        if target_collection not in collection_references:
            collection_references[target_collection] = []
        source_collection, field = ref_key.split(".", 1)
        collection_references[target_collection].append((source_collection, field))

    # Copy original collection contents to simulate removals
    # This is a simplified approach: we'll simulate by tracking what would be removed
    # and then calculate orphans based on that simulated state
    simulated_orphan_ids = {}  # collection_name -> set of ObjectId that would be removed

    # Initialize with empty sets
    for collection_name in COLLECTION_DEPENDENCY_ORDER:
        simulated_orphan_ids[collection_name] = set()

    orphans = {}

    # Process from most central to most dependent
    for collection_name in COLLECTION_DEPENDENCY_ORDER:
        # Check if this collection is a target of any references
        if collection_name in collection_references:
            for source_collection, field in collection_references[collection_name]:
                # Get all valid IDs in the target collection (excluding those already marked as orphans)
                target_collection_obj = await get_collection(collection_name)
                all_target_ids = set(await target_collection_obj.distinct("_id"))

                # Exclude any IDs that are already marked as orphans in this simulation
                current_target_ids = all_target_ids - simulated_orphan_ids[collection_name]

                # Find documents in source collection that reference invalid target IDs
                source_collection_obj = await get_collection(source_collection)

                # Check if field is nested (like attributes.attribute_doc_id)
                if "." in field:
                    if f"{source_collection}.{field}" == "caches.attributes.attribute_doc_id":
                        # Handle nested reference case
                        # This is complex - need to find cache documents where nested attribute references invalid cache_attribute
                        pipeline = [
                            {"$unwind": "$attributes"},
                            {
                                "$match": {
                                    "attributes.attribute_doc_id": {"$exists": True, "$ne": None}
                                }
                            },
                            {
                                "$lookup": {
                                    "from": "cache_attributes",
                                    "localField": "attributes.attribute_doc_id",
                                    "foreignField": "_id",
                                    "as": "valid_attribute",
                                }
                            },
                            {"$match": {"valid_attribute": {"$size": 0}}},  # No match found
                            {"$project": {"_id": 1}},
                            {"$group": {"_id": None, "orphan_ids": {"$addToSet": "$_id"}}},
                        ]

                        results = await source_collection_obj.aggregate(pipeline).to_list(
                            length=None
                        )
                        if results and results[0]["orphan_ids"]:
                            orphan_ids = [str(obj_id) for obj_id in results[0]["orphan_ids"]]
                        else:
                            orphan_ids = []
                    else:
                        orphan_ids = []
                else:
                    # Regular reference
                    pipeline = [
                        {"$match": {field: {"$exists": True, "$ne": None}}},
                        {"$match": {field: {"$nin": list(current_target_ids)}}},
                        {"$project": {"_id": 1}},
                    ]

                    cursor = source_collection_obj.aggregate(pipeline)
                    orphan_docs = await cursor.to_list(length=None)
                    orphan_ids = [str(doc["_id"]) for doc in orphan_docs]

                # Record the orphans found
                ref_key = f"{source_collection}.{field}"
                if orphan_ids:
                    if ref_key not in orphans:
                        orphans[ref_key] = []
                    orphans[ref_key].extend(orphan_ids)

                    # Add to simulated removals for this source collection
                    simulated_orphan_ids[source_collection].update(
                        [ObjectId(oid) for oid in orphan_ids]
                    )

    # Remove duplicates
    for key in orphans:
        orphans[key] = list(set(orphans[key]))

    total_orphans = sum(len(ids) for ids in orphans.values())

    if not orphans:
        return {
            "message": "No orphans found. Database is clean!",
            "orphans_found": {},
            "total_orphans": 0,
        }

    # Génère une clé de confirmation sécurisée
    confirmation_key = secrets.token_urlsafe(16)
    expires_at = utcnow() + timedelta(minutes=CONFIRMATION_KEY_TTL)

    # Stocke en cache
    cleanup_cache[confirmation_key] = {"orphans": orphans, "expires_at": expires_at}

    return {
        "orphans_found": orphans,
        "total_orphans": total_orphans,
        "confirmation_key": confirmation_key,
        "expires_at": expires_at.isoformat(),
        "message": f"Found {total_orphans} orphan(s). Use DELETE with this key to clean.",
    }


# DONE: [BACKLOG] Route /maintenance/db_cleanup (DELETE) à vérifier
@router.delete("/db_cleanup")
async def cleanup_execute(key: str):
    """
    Exécute le nettoyage des enregistrements orphelins après confirmation.
    Sauvegarde les données supprimées dans un fichier JSON horodaté.
    Process collections in dependency order (most central first) to prevent creating new orphans.

    Args:
        key: Clé de confirmation obtenue via GET /db_cleanup
    """
    clean_expired_keys()

    # Vérifie la clé
    if key not in cleanup_cache:
        raise HTTPException(status_code=404, detail="Invalid or expired confirmation key")

    cached_data = cleanup_cache[key]
    if utcnow() > cached_data["expires_at"]:
        del cleanup_cache[key]
        raise HTTPException(
            status_code=410, detail="Confirmation key expired. Please request a new analysis."
        )

    # Prépare les données de backup
    backup_data = {"timestamp": utcnow().isoformat(), "deleted_by_collection": {}, "data": {}}

    deleted_count = {}

    # Process collections in dependency order (most central first)
    # This ensures that when we remove items from central collections,
    # we process potential orphans in dependent collections appropriately
    for collection_name in COLLECTION_DEPENDENCY_ORDER:
        # Find all orphan references for documents in this collection
        collection_orphans = {}
        for key_path, orphan_ids in cached_data["orphans"].items():
            current_collection, field = key_path.split(".", 1)

            # Check if this orphan refers to documents in the current collection being processed
            if current_collection == collection_name:
                collection_orphans[key_path] = orphan_ids

        if not collection_orphans:
            continue

        # Collect all document IDs from all orphan references for this collection
        all_orphan_ids = set()
        for _, orphan_ids in collection_orphans.items():
            all_orphan_ids.update(orphan_ids)

        # Convertit les IDs en ObjectId
        object_ids = [ObjectId(oid) for oid in all_orphan_ids]

        # Récupère les documents complets AVANT suppression
        collection_obj = await get_collection(collection_name)
        docs_to_delete = await collection_obj.find({"_id": {"$in": object_ids}}).to_list(None)

        # Ajoute au backup
        if collection_name not in backup_data["data"]:
            backup_data["data"][collection_name] = []

        backup_data["data"][collection_name].extend(
            [serialize_mongo_doc(doc) for doc in docs_to_delete]
        )

        # Supprime les documents
        collection_obj = await get_collection(collection_name)
        result = await collection_obj.delete_many({"_id": {"$in": object_ids}})

        # Agrège les compteurs par collection
        if collection_name not in deleted_count:
            deleted_count[collection_name] = 0
        deleted_count[collection_name] += result.deleted_count

        backup_data["deleted_by_collection"][collection_name] = deleted_count[collection_name]

    backup_data["total_deleted"] = sum(deleted_count.values())

    # Sauvegarde le fichier JSON avec horodatage
    timestamp_str = utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = CLEANUP_BACKUP_DIR
    base_name = f"{timestamp_str}_cleanup"
    backup_file = write_json_zip(
        backup_data=backup_data, output_dir=output_dir, base_name=base_name
    )

    file_size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)

    # Nettoie le cache
    del cleanup_cache[key]

    return {
        "message": f"Successfully deleted {backup_data['total_deleted']} orphan(s)",
        "backup_file": str(backup_file),
        "backup_file_size": f"{file_size_mb} MB",
        "deleted": deleted_count,
        "total_deleted": backup_data["total_deleted"],
        "timestamp": backup_data["timestamp"],
    }


# DONE: [BACKLOG] Route /maintenance/db_cleanup/backups (GET) à vérifier
@router.get("/db_cleanup/backups")
async def cleanup_list_backups():
    """Liste tous les fichiers de backup disponibles"""
    backups = []

    for backup_file in sorted(CLEANUP_BACKUP_DIR.glob("*_cleanup.zip"), reverse=True):
        try:
            with ZipFile(backup_file, "r") as zf:
                # le JSON interne s’appelle f"{base_name}.json"
                # si tu ne connais pas le nom, prends le premier .json
                json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
                if json_name:
                    data = json.loads(zf.read(json_name).decode("utf-8"))
                    backups.append(
                        {
                            "filename": backup_file.name,
                            "timestamp": data.get("timestamp", "unknown"),
                            "total_deleted": data.get("total_deleted", 0),
                            "collections": list(data.get("deleted_by_collection", {}).keys()),
                            "size_kb": round(backup_file.stat().st_size / 1024, 2),
                        }
                    )
        except Exception as e:
            # En cas d'erreur de lecture, on l'indique mais on ne crash pas
            backups.append({"filename": backup_file.name, "error": str(e)})

    return {"backups": backups, "total_backups": len(backups)}


# DONE: [BACKLOG] Route /maintenance/backups/{filepath:path} (GET) à vérifier
@router.get("/backups/{filepath:path}")
async def get_backup_file(filepath: str):
    """Télécharge un fichier de backup (db_cleanup, full_backup, etc.)."""
    requested_path = (BACKUP_ROOT_DIR / filepath).resolve()

    # 🔒 Sécurité : empêche toute sortie du répertoire racine
    if not str(requested_path).startswith(str(BACKUP_ROOT_DIR)):
        raise HTTPException(status_code=400, detail="Invalid file path")

    if not requested_path.exists() or not requested_path.is_file():
        raise HTTPException(status_code=404, detail="Backup file not found")

    # 🔍 Détection du type de fichier
    ext = requested_path.suffix.lower()
    media_type = {
        ".zip": "application/zip",
        ".json": "application/json",
        ".gz": "application/gzip",
    }.get(ext, "application/octet-stream")

    # 📦 Renvoi du fichier avec headers corrects
    return FileResponse(
        path=str(requested_path),
        media_type=media_type,
        filename=requested_path.name,
    )


# DONE: [BACKLOG] Route /maintenance/db_full_backup (POST) à vérifier
@router.post("/db_full_backup")
async def full_backup_create():
    """
    Crée un backup complet de toute la base de données.
    Sauvegarde toutes les collections dans un fichier JSON horodaté.

    ⚠️ Attention : peut être lourd sur de grosses bases de données.
    """
    backup_data = {"timestamp": utcnow().isoformat(), "database": db.name, "collections": {}}

    total_documents = 0

    # Récupère la liste de toutes les collections
    collection_names = await db.list_collection_names()

    # Pour chaque collection
    for collection_name in collection_names:
        # Skip les collections système de MongoDB
        if collection_name.startswith("system."):
            continue

        # Récupère tous les documents de la collection
        cursor = db[collection_name].find()
        docs = await cursor.to_list(length=None)

        if docs:
            # Sérialise les documents (gère les ObjectId)
            backup_data["collections"][collection_name] = [serialize_mongo_doc(doc) for doc in docs]
            total_documents += len(docs)

    backup_data["total_collections"] = len(backup_data["collections"])
    backup_data["total_documents"] = total_documents

    # Crée le fichier de backup
    timestamp_str = utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = FULL_BACKUP_DIR
    base_name = f"{timestamp_str}_full_backup"
    backup_file = write_json_zip(
        backup_data=backup_data, output_dir=output_dir, base_name=base_name
    )

    file_size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)

    return {
        "message": "Full backup created successfully",
        "backup_file": str(backup_file),
        "total_collections": backup_data["total_collections"],
        "total_documents": total_documents,
        "size_mb": file_size_mb,
        "timestamp": backup_data["timestamp"],
    }


# DONE: [BACKLOG] Route /maintenance/db_full_restore/{filename} (POST) à vérifier
@router.post("/db_full_restore/{filename}")
async def full_backup_restore(filename: str, dry_run: bool = True, drop_existing: bool = False):
    """
    Restaure une base de données complète depuis un backup.

    Args:
        filename: Nom du fichier de backup complet
        dry_run: Si True, simule la restauration sans insérer (défaut: True)
        drop_existing: Si True, vide les collections avant restauration (défaut: False)

    ⚠️ DANGER : drop_existing=True supprime toutes les données existantes !
    """
    # Sécurité
    if ".." in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    backup_file = CLEANUP_BACKUP_DIR.parent / filename

    if not backup_file.exists():
        raise HTTPException(status_code=404, detail="Backup file not found")

    with open(backup_file, encoding="utf-8") as f:
        backup_data = json.load(f)

    restored = {}
    dropped = []

    for collection_name, docs in backup_data.get("collections", {}).items():
        # Reconvertit les _id en ObjectId
        for doc in docs:
            if "_id" in doc and isinstance(doc["_id"], dict) and "$oid" in doc["_id"]:
                doc["_id"] = ObjectId(doc["_id"]["$oid"])

        if not dry_run:
            # Supprime la collection existante si demandé
            if drop_existing:
                await db[collection_name].delete_many({})
                dropped.append(collection_name)

            # Insertion réelle
            if docs:
                result = await db[collection_name].insert_many(docs)
                restored[collection_name] = len(result.inserted_ids)
        else:
            # Simulation
            restored[collection_name] = len(docs)

    response = {
        "restored": restored,
        "total_restored": sum(restored.values()),
        "dry_run": dry_run,
        "backup_timestamp": backup_data.get("timestamp"),
        "message": "Simulation only - no data inserted"
        if dry_run
        else "Full backup restored successfully",
    }

    if dropped:
        response["dropped_collections"] = dropped

    return response


# DONE: [BACKLOG] Route /maintenance/db_backups (GET) à vérifier
@router.get("/db_backups")
async def list_all_backups():
    """Liste tous les fichiers de backup (cleanup + full)"""
    backups = {"cleanup_backups": [], "full_backups": []}

    # Backups de cleanup
    for backup_file in sorted(CLEANUP_BACKUP_DIR.glob("*.zip"), reverse=True):
        try:
            with ZipFile(backup_file, "r") as zf:
                # le JSON interne s’appelle f"{base_name}.json"
                # si tu ne connais pas le nom, prends le premier .json
                json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
                if json_name:
                    data = json.loads(zf.read(json_name).decode("utf-8"))
                    backups["cleanup_backups"].append(
                        {
                            "filename": backup_file.name,
                            "timestamp": data.get("timestamp", "unknown"),
                            "total_deleted": data.get("total_deleted", 0),
                            "collections": list(data.get("deleted_by_collection", {}).keys()),
                            "size_kb": round(backup_file.stat().st_size / 1024, 2),
                            "type": "cleanup",
                        }
                    )
        except Exception as e:
            backups["cleanup_backups"].append({"filename": backup_file.name, "error": str(e)})

    # Backups complets
    for backup_file in sorted(FULL_BACKUP_DIR.glob("*.zip"), reverse=True):
        try:
            with ZipFile(backup_file, "r") as zf:
                # le JSON interne s'appelle f"{base_name}.json"
                # si tu ne connais pas le nom, prends le premier .json
                json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
                if json_name:
                    data = json.loads(zf.read(json_name).decode("utf-8"))
                    backups["full_backups"].append(
                        {
                            "filename": backup_file.name,
                            "timestamp": data.get("timestamp", "unknown"),
                            "total_collections": data.get("total_collections", 0),
                            "total_documents": data.get("total_documents", 0),
                            "size_mb": round(backup_file.stat().st_size / (1024 * 1024), 2),
                            "type": "full",
                        }
                    )
                else:
                    # Si aucun fichier JSON n'est trouvé dans le ZIP
                    backups["full_backups"].append(
                        {
                            "filename": backup_file.name,
                            "error": "No JSON metadata file found in archive",
                        }
                    )
        except Exception as e:
            backups["full_backups"].append({"filename": backup_file.name, "error": str(e)})

    return {
        "backups": backups,
        "total_cleanup_backups": len(backups["cleanup_backups"]),
        "total_full_backups": len(backups["full_backups"]),
    }


def write_json_zip(backup_data: dict, output_dir: str | Path, base_name: str) -> Path:
    """
    Écrit un fichier ZIP contenant un JSON unique directement depuis un objet Python.

    Args:
        backup_data: Données à sauvegarder (dict, list, etc.)
        output_dir: Dossier de destination.
        base_name: Nom de base du fichier (sans extension).

    Returns:
        Path: chemin complet du fichier ZIP créé.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    zip_path = output_dir / f"{base_name}.zip"
    json_name_in_zip = f"{base_name}.json"

    # Convertir les données en JSON (en mémoire)
    payload = json.dumps(backup_data, ensure_ascii=False, indent=2)

    # Écrire directement le ZIP
    with ZipFile(zip_path, mode="w", compression=ZIP_DEFLATED) as zf:
        zf.writestr(json_name_in_zip, payload)

    return zip_path


# TODO: [BACKLOG] Route /maintenance/import-gpx (POST) à vérifier
@router.post(
    "/upload-gpx",
    summary="Import GPX avec mise à jour forcée des attributs",
    description=(
        "Importe un fichier GPX/ZIP et force la mise à jour des attributs pour toutes les caches.\n\n"
        "**⚠️ RESTREINT AUX ADMINISTRATEURS**\n\n"
        "Fonctionne comme l'import standard mais met à jour les attributs même s'ils existent déjà.\n"
        "Supporte les mêmes formats que l'import standard (cgeo, pocket_query, etc.).\n"
        "Retourne un résumé d'import et des statistiques liées aux challenges."
    ),
    responses={
        200: {"description": "Import GPX réussi avec mise à jour forcée des attributs"},
        400: {"description": "Fichier GPX/ZIP invalide"},
        401: {"description": "Non authentifié"},
        403: {"description": "Accès refusé (admin requis)"},
    },
)
async def upload_gpx(
    request: Request,
    user_id: CurrentUserId,
    file: Annotated[
        UploadFile, File(..., description="Fichier GPX à importer (ou ZIP contenant un GPX).")
    ],
    import_mode: Literal["all", "found"] = Query(
        "all",
        description="Mode d'import: 'all' (toutes les caches) ou 'found' (mes trouvailles)",
    ),
    source_type: Literal["auto", "cgeo", "pocket_query"] = Query(
        "auto",
        description="Type de source GPX: 'auto' (détection automatique), 'cgeo', 'pocket_query'",
    ),
) -> dict[str, Any]:
    """Import GPX avec mise à jour forcée des attributs.

    Description:
        Importe un fichier GPX/ZIP et force la mise à jour des attributs pour toutes les caches.
        Cette fonctionnalité est réservée aux administrateurs.

    Args:
        file: Fichier GPX ou ZIP à traiter.
        import_mode: Mode d'import ('all' pour toutes les caches, 'found' pour les trouvailles).
        source_type: Type de source GPX ('auto', 'cgeo', 'pocket_query').

    Returns:
        dict: Résumé d'import et statistiques liées aux challenges.

    Raises:
        HTTPException 400: Si le fichier est invalide.
        HTTPException 403: Si l'utilisateur n'est pas admin.
    """
    result: dict[str, Any] = {"summary": None, "challenge_stats": None}

    # Lecture du fichier
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(1024 * 1024)  # 1MB chunks
        if not chunk:
            break
        chunks.append(chunk)

    await file.close()
    payload = b"".join(chunks)

    try:
        result["summary"] = await import_gpx_payload(
            payload=payload,
            filename=file.filename or "upload.gpx",
            import_mode=import_mode,
            user_id=None,  # Pour l'import forcé, on pourrait spécifier un utilisateur spécifique ou laisser à None
            request=request,
            source_type=source_type,
            force_update_attributes=True,  # Toujours vrai pour cette route
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Fichier GPX/ZIP invalide: {e}") from e

    return result
