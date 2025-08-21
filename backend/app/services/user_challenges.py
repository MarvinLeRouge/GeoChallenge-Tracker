
from __future__ import annotations

from typing import Any, Dict, List, Optional
from datetime import datetime
from bson import ObjectId
from pymongo import UpdateOne, ReturnDocument

from app.db.mongodb import get_collection

def _now() -> datetime:
    return datetime.utcnow()


def sync_user_challenges(user_id: ObjectId) -> Dict[str, int]:
    challenges = get_collection("challenges")
    ucs = get_collection("user_challenges")
    found = get_collection("found_caches")

    # 1) Créer les UC manquants (status=pending)
    challenge_ids = list(challenges.distinct("_id"))
    if not challenge_ids:
        return {"created": 0, "existing": 0, "total_user_challenges": 0}

    known = set(ucs.distinct("challenge_id", {"user_id": user_id}))
    missing = [cid for cid in challenge_ids if cid not in known]

    ops: List[UpdateOne] = []
    for cid in missing:
        ops.append(
            UpdateOne(
                {"user_id": user_id, "challenge_id": cid},
                {
                    "$setOnInsert": {
                        "user_id": user_id,
                        "challenge_id": cid,
                        "status": "pending",
                        "created_at": _now(),
                    },
                    "$set": {"updated_at": _now()},
                },
                upsert=True,
            )
        )
    created = 0
    if ops:
        res = ucs.bulk_write(ops, ordered=False)
        created = len(res.upserted_ids) if getattr(res, "upserted_ids", None) else 0

    # 2) Marquer comme completed (computed) les UC dont la cache mère a été trouvée
    #    - On récupère les cache_id trouvés par l'utilisateur
    found_cache_ids = set(found.distinct("cache_id", {"user_id": user_id}))
    if found_cache_ids:
        # Map cache_id -> (challenge_id)
        cache_to_challenge = {
            doc["cache_id"]: doc["_id"]
            for doc in challenges.find({"cache_id": {"$in": list(found_cache_ids)}}, {"_id": 1, "cache_id": 1})
        }
        if cache_to_challenge:
            # Pour associer la bonne date à chaque UC, on lit found_caches (user_id, cache_id, found_date)
            cur = found.find(
                {"user_id": user_id, "cache_id": {"$in": list(cache_to_challenge.keys())}},
                {"cache_id": 1, "found_date": 1, "_id": 0},
            )
            updates: List[UpdateOne] = []
            now = _now()
            for fc in cur:
                ch_id = cache_to_challenge.get(fc["cache_id"])
                if not ch_id:
                    continue
                # Snapshot de progression à 100% à la date du find
                progress = {
                    "percent": 100,
                    "tasks_done": None,
                    "tasks_total": None,
                    "checked_at": fc.get("found_date") or now,
                }
                updates.append(
                    UpdateOne(
                        {"user_id": user_id, "challenge_id": ch_id},
                        {
                            "$set": {
                                "computed_status": "completed",
                                "progress": progress,
                                "updated_at": now,
                                "manual_override": False,
                            },
                            "$unset": {"override_reason": "", "overridden_at": ""},
                        },
                        upsert=False,
                    )
                )
            if updates:
                ucs.bulk_write(updates, ordered=False)

    total = ucs.count_documents({"user_id": user_id})
    existing = total - created
    return {"created": created, "existing": existing, "total_user_challenges": total}

def list_user_challenges(
    user_id: ObjectId,
    status: Optional[str],
    page: int,
    limit: int,
) -> Dict[str, Any]:
    ucs = get_collection("user_challenges")
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"user_id": user_id}},
    ]
    if status:
        if status == "completed":
            # Effectif: completed si statut manuel OU calculé
            pipeline.append({
                "$match": {
                    "$or": [
                        {"status": "completed"},
                        {"computed_status": "completed"},
                    ]
                }
            })
        elif status == "dismissed":
            # dismissed effectif = statut utilisateur (hors completed)
            pipeline.append({
                "$match": {
                    "status": "dismissed",
                    "computed_status": {"$ne": "completed"},
                }
            })
        elif status == "accepted":
            # accepted effectif = statut utilisateur (hors completed)
            pipeline.append({
                "$match": {
                    "status": "accepted",
                    "computed_status": {"$ne": "completed"},
                }
            })
        elif status == "pending":
            # pending effectif = ni accepted, ni dismissed, ni completed (manuel ou calculé)
            pipeline.append({
                "$match": {
                    "status": {"$nin": ["accepted", "dismissed", "completed"]},
                    "computed_status": {"$ne": "completed"},
                }
            })
    pipeline += [
        {"$lookup": {
            "from": "challenges",
            "localField": "challenge_id",
            "foreignField": "_id",
            "as": "challenge"
        }},
        {"$unwind": "$challenge"},
        {"$sort": {"updated_at": -1, "_id": 1}},
        {"$facet": {
            "items": [
                {"$skip": max(0, (page - 1) * limit)},
                {"$limit": limit},
                {"$project": {
                    "_id": 1,
                    "status": 1,
                    "computed_status": 1,
                    "manual_override": 1,
                    "progress": 1,
                    "updated_at": 1,
                    "challenge": {"id": "$challenge._id", "name": "$challenge.name"},
                }},
            ],
            "total": [{"$count": "value"}],
        }},
        {"$project": {
            "items": 1,
            "total": {"$ifNull": [{"$arrayElemAt": ["$total.value", 0]}, 0]}
        }}
    ]

    out = list(ucs.aggregate(pipeline))
    if not out:
        return {"items": [], "page": page, "limit": limit, "total": 0}

    result = out[0]
    items = result["items"]

    def effective_status(it: Dict[str, Any]) -> str:
        cs = it.get("computed_status")
        st = it.get("status")
        if st == "completed" or cs == "completed":
            return "completed"
        return st

    for it in items:
        it["id"] = str(it.pop("_id"))
        if isinstance(it.get("challenge", {}).get("id"), ObjectId):
            it["challenge"]["id"] = str(it["challenge"]["id"])
        it["effective_status"] = effective_status(it)

    return {"items": items, "page": page, "limit": limit, "total": result["total"]}

def get_user_challenge_detail(user_id: ObjectId, uc_id: ObjectId) -> Optional[Dict[str, Any]]:
    ucs = get_collection("user_challenges")
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"_id": uc_id, "user_id": user_id}},
        {"$lookup": {
            "from": "challenges",
            "localField": "challenge_id",
            "foreignField": "_id",
            "as": "challenge"
        }},
        {"$unwind": "$challenge"},
        {"$project": {
            "_id": 1,
            "status": 1,
            "computed_status": 1,
            "manual_override": 1,
            "override_reason": 1,
            "overridden_at": 1,
            "notes": 1,
            "progress": 1,
            "updated_at": 1,
            "created_at": 1,
            "challenge": {
                "id": "$challenge._id",
                "name": "$challenge.name",
                "description": "$challenge.description",
            }
        }},
    ]
    rows = list(ucs.aggregate(pipeline, allowDiskUse=False))
    if not rows:
        return None
    doc = rows[0]
    cs = doc.get("computed_status")
    st = doc.get("status")
    doc["effective_status"] = "completed" if (st == "completed" or cs == "completed") else st
    doc["id"] = str(doc.pop("_id"))
    if isinstance(doc.get("challenge", {}).get("id"), ObjectId):
        doc["challenge"]["id"] = str(doc["challenge"]["id"])
    return doc

def patch_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    *,
    status: Optional[str],
    notes: Optional[str],
    override_reason: Optional[str],
) -> Optional[Dict[str, Any]]:
    """
    Met à jour le statut/notes d'un UserChallenge.
    - status: pending|accepted|dismissed|completed (optionnel)
    - notes: texte libre (optionnel)
    - override: si status=completed, marque manual_override=True et trace overridden_at/override_reason
    Retourne le document mis à jour (dict) ou None si introuvable.
    """
    ucs = get_collection("user_challenges")

    update: Dict[str, Any] = {"updated_at": _now()}
    unset: Dict[str, ""] = {}

    if status is not None:
        update["status"] = status
        if status == "completed":
            update["manual_override"] = True
            update["overridden_at"] = _now()
            if override_reason is not None:
                update["override_reason"] = override_reason
            # Progression instantanée à 100% lors d'un override manuel
            update["progress"] = {"percent": 100, "tasks_done": None, "tasks_total": None, "checked_at": _now()}
        else:
            update["manual_override"] = False
            unset["override_reason"] = ""
            unset["overridden_at"] = ""

    if notes is not None:
        update["notes"] = notes

    update_doc: Dict[str, Any] = {"$set": update}
    if unset:
        update_doc["$unset"] = unset

    res = ucs.find_one_and_update(
        {"_id": uc_id, "user_id": user_id},
        update_doc,
        return_document=ReturnDocument.AFTER,
    )
    if not res:
        return None


    # Trigger progress evaluation when status switches to 'accepted'
    try:
        if status == "accepted":
            from app.services.progress import evaluate_progress
            progress_coll = get_collection("progress")
            has_snapshot = progress_coll.find_one({"user_challenge_id": uc_id}, {"_id": 1}) is not None
            if not has_snapshot:
                evaluate_progress(user_id, uc_id)
    except Exception:
        # best-effort: do not block patch if evaluation fails
        pass

    cs = res.get("computed_status")
    st = res.get("status")
    res["effective_status"] = "completed" if (st == "completed" or cs == "completed") else st
    res["id"] = str(res.pop("_id"))
    return res
