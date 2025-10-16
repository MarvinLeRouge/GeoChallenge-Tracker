# app/api/routes/maintenance.py

from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from app.core.security import require_admin
from datetime import timedelta
import json, secrets
from bson import ObjectId, json_util
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from app.core.config_backup import BACKUP_ROOT_DIR, CLEANUP_BACKUP_DIR, FULL_BACKUP_DIR
from app.db.mongodb import db
from app.core.utils import utcnow

# Cache en mémoire
cleanup_cache: dict = {}
# Durée de validité de la clé de confirmation (en minutes)
CONFIRMATION_KEY_TTL = 10

REFERENCES_MAP = {
    "caches": {
        "country_id": "countries",
        "state_id": "states",
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
    }
}

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


@router.get("")
def maintenance_get_1() -> dict:
    result = {
        "status": "ok",
        "route": "/maintenance",
        "method": "GET",
        "function": "maintenance_get_1",
    }

    return result


@router.post("")
def maintenance_post_1() -> dict:
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

@router.get("/db_cleanup")
async def cleanup_analyze():
    """
    Analyse la base de données pour détecter les enregistrements orphelins.
    Retourne un rapport et une clé de confirmation pour le nettoyage.
    """
    clean_expired_keys()
    
    orphans = {}
    total_orphans = 0
    
    for collection, field_refs in REFERENCES_MAP.items():
        for field, ref_collection in field_refs.items():
            # Récupère tous les IDs valides de la collection référencée
            valid_ids = db.get_collection(ref_collection).distinct("_id")
            
            # Construit le pipeline d'agrégation pour trouver les orphelins
            pipeline = [
                {
                    "$match": {
                        field: {"$exists": True, "$ne": None}
                    }
                },
                {
                    "$match": {
                        field: {"$nin": valid_ids}
                    }
                },
                {
                    "$project": {"_id": 1}
                }
            ]
            
            orphan_docs = db.get_collection(collection).aggregate(pipeline).to_list(None)
            
            if orphan_docs:
                key = f"{collection}.{field}"
                orphan_ids = [str(doc["_id"]) for doc in orphan_docs]
                orphans[key] = orphan_ids
                total_orphans += len(orphan_ids)
    
    if not orphans:
        return {
            "message": "No orphans found. Database is clean!",
            "orphans_found": {},
            "total_orphans": 0
        }
    
    # Génère une clé de confirmation sécurisée
    confirmation_key = secrets.token_urlsafe(16)
    expires_at = utcnow() + timedelta(minutes=CONFIRMATION_KEY_TTL)
    
    # Stocke en cache
    cleanup_cache[confirmation_key] = {
        "orphans": orphans,
        "expires_at": expires_at
    }
    
    return {
        "orphans_found": orphans,
        "total_orphans": total_orphans,
        "confirmation_key": confirmation_key,
        "expires_at": expires_at.isoformat(),
        "message": f"Found {total_orphans} orphan(s). Use DELETE with this key to clean."
    }

@router.delete("/db_cleanup")
async def cleanup_execute(key: str):
    """
    Exécute le nettoyage des enregistrements orphelins après confirmation.
    Sauvegarde les données supprimées dans un fichier JSON horodaté.
    
    Args:
        key: Clé de confirmation obtenue via GET /db_cleanup
    """
    clean_expired_keys()
    
    # Vérifie la clé
    if key not in cleanup_cache:
        raise HTTPException(
            status_code=404,
            detail="Invalid or expired confirmation key"
        )
    
    cached_data = cleanup_cache[key]
    if utcnow() > cached_data["expires_at"]:
        del cleanup_cache[key]
        raise HTTPException(
            status_code=410,
            detail="Confirmation key expired. Please request a new analysis."
        )
    
    # Prépare les données de backup
    backup_data = {
        "timestamp": utcnow().isoformat(),
        "deleted_by_collection": {},
        "data": {}
    }
    
    deleted_count = {}
    
    # Pour chaque collection avec des orphelins
    for key_path, orphan_ids in cached_data["orphans"].items():
        collection, field = key_path.split(".", 1)
        
        # Convertit les IDs en ObjectId
        object_ids = [ObjectId(oid) for oid in orphan_ids]
        
        # Récupère les documents complets AVANT suppression
        docs_to_delete = db.get_collection(collection).find(
            {"_id": {"$in": object_ids}}
        ).to_list(None)
        
        # Ajoute au backup
        if collection not in backup_data["data"]:
            backup_data["data"][collection] = []
        
        backup_data["data"][collection].extend(
            [serialize_mongo_doc(doc) for doc in docs_to_delete]
        )
        
        # Supprime les documents
        result = db.get_collection(collection).delete_many(
            {"_id": {"$in": object_ids}}
        )
        
        # Agrège les compteurs par collection
        if collection not in deleted_count:
            deleted_count[collection] = 0
        deleted_count[collection] += result.deleted_count
        
        backup_data["deleted_by_collection"][collection] = deleted_count[collection]
    
    backup_data["total_deleted"] = sum(deleted_count.values())
    
    # Sauvegarde le fichier JSON avec horodatage
    timestamp_str = utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = CLEANUP_BACKUP_DIR
    base_name = f"{timestamp_str}_cleanup"
    backup_file = write_json_zip(backup_data=backup_data, output_dir=output_dir, base_name=base_name)
    
    file_size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)
    
    # Nettoie le cache
    del cleanup_cache[key]

    return {
        "message": f"Successfully deleted {backup_data['total_deleted']} orphan(s)",
        "backup_file": str(backup_file),
        "deleted": deleted_count,
        "total_deleted": backup_data["total_deleted"],
        "timestamp": backup_data["timestamp"]
    }


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
                    backups.append({
                        "filename": backup_file.name,
                        "timestamp": data.get("timestamp", "unknown"),
                        "total_deleted": data.get("total_deleted", 0),
                        "collections": list(data.get("deleted_by_collection", {}).keys()),
                        "size_kb": round(backup_file.stat().st_size / 1024, 2)
                    })
        except Exception as e:
            # En cas d'erreur de lecture, on l'indique mais on ne crash pas
            backups.append({
                "filename": backup_file.name,
                "error": str(e)
            })
    
    return {
        "backups": backups,
        "total_backups": len(backups)
    }


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

@router.post("/db_full_backup")
async def full_backup_create():
    """
    Crée un backup complet de toute la base de données.
    Sauvegarde toutes les collections dans un fichier JSON horodaté.
    
    ⚠️ Attention : peut être lourd sur de grosses bases de données.
    """
    backup_data = {
        "timestamp": utcnow().isoformat(),
        "database": db.name,
        "collections": {}
    }
    
    total_documents = 0
    
    # Récupère la liste de toutes les collections
    collection_names = db.list_collection_names()
    
    # Pour chaque collection
    for collection_name in collection_names:
        # Skip les collections système de MongoDB
        if collection_name.startswith("system."):
            continue
        
        # Récupère tous les documents de la collection
        docs = db[collection_name].find().to_list(None)
        
        if docs:
            # Sérialise les documents (gère les ObjectId)
            backup_data["collections"][collection_name] = [
                serialize_mongo_doc(doc) for doc in docs
            ]
            total_documents += len(docs)
    
    backup_data["total_collections"] = len(backup_data["collections"])
    backup_data["total_documents"] = total_documents
    
    # Crée le fichier de backup
    timestamp_str = utcnow().strftime("%Y-%m-%d_%H-%M-%S")
    output_dir = FULL_BACKUP_DIR
    base_name = f"{timestamp_str}_full_backup"
    backup_file = write_json_zip(backup_data=backup_data, output_dir=output_dir, base_name=base_name)
    
    file_size_mb = round(backup_file.stat().st_size / (1024 * 1024), 2)
    
    return {
        "message": "Full backup created successfully",
        "backup_file": str(backup_file),
        "total_collections": backup_data["total_collections"],
        "total_documents": total_documents,
        "size_mb": file_size_mb,
        "timestamp": backup_data["timestamp"]
    }


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
    
    with open(backup_file, "r", encoding="utf-8") as f:
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
        "message": "Simulation only - no data inserted" if dry_run else "Full backup restored successfully"
    }
    
    if dropped:
        response["dropped_collections"] = dropped
    
    return response


@router.get("/db_backups")
async def list_all_backups():
    """Liste tous les fichiers de backup (cleanup + full)"""
    backups = {
        "cleanup_backups": [],
        "full_backups": []
    }
    
    # Backups de cleanup
    for backup_file in sorted(CLEANUP_BACKUP_DIR.glob("*.zip"), reverse=True):
        try:
            with ZipFile(backup_file, "r") as zf:
                # le JSON interne s’appelle f"{base_name}.json"
                # si tu ne connais pas le nom, prends le premier .json
                json_name = next((n for n in zf.namelist() if n.endswith(".json")), None)
                if json_name:
                    data = json.loads(zf.read(json_name).decode("utf-8"))
                    backups["cleanup_backups"].append({
                        "filename": backup_file.name,
                        "timestamp": data.get("timestamp", "unknown"),
                        "total_deleted": data.get("total_deleted", 0),
                        "collections": list(data.get("deleted_by_collection", {}).keys()),
                        "size_kb": round(backup_file.stat().st_size / 1024, 2),
                        "type": "cleanup"
                    })
        except Exception as e:
            backups["cleanup_backups"].append({
                "filename": backup_file.name,
                "error": str(e)
            })
    
    # Backups complets
    for backup_file in sorted(FULL_BACKUP_DIR.glob("*.zip"), reverse=True):
        try:
            with open(backup_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            backups["full_backups"].append({
                "filename": backup_file.name,
                "timestamp": data.get("timestamp", "unknown"),
                "total_collections": data.get("total_collections", 0),
                "total_documents": data.get("total_documents", 0),
                "size_mb": round(backup_file.stat().st_size / (1024 * 1024), 2),
                "type": "full"
            })
        except Exception as e:
            backups["full_backups"].append({
                "filename": backup_file.name,
                "error": str(e)
            })
    
    return {
        "backups": backups,
        "total_cleanup_backups": len(backups["cleanup_backups"]),
        "total_full_backups": len(backups["full_backups"])
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
