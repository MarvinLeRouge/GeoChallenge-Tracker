# app/services/targets.py
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from math import radians, sin, cos, asin, sqrt
from datetime import datetime

from app.db.mongodb import get_collection
from app.services.query_builder import compile_and_only  # <- brique commune
from app.core.utils import utcnow

# ------------------------------------------------------------
# utilitaires
# ------------------------------------------------------------

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)
    a = sin(dlat/2)**2 + cos(radians(lat1))*cos(radians(lat2))*sin(dlon/2)**2
    return 2 * R * asin(sqrt(a))

def _get_username(user_id: ObjectId) -> Optional[str]:
    u = get_collection("users").find_one({"_id": user_id}, {"username": 1})
    return (u or {}).get("username")

def _get_user_location(user_id: ObjectId) -> Optional[Tuple[float, float]]:
    u = get_collection("users").find_one({"_id": user_id}, {"location": 1})
    loc = (u or {}).get("location")
    if loc and isinstance(loc, dict) and (loc.get("type") == "Point"):
        lon, lat = (loc.get("coordinates") or [None, None])
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return (lat, lon)
    return None

def _latest_progress_task_map(uc_id: ObjectId) -> Dict[ObjectId, Dict[str, Any]]:
    """
    Retourne {task_id: {min_count, current_count}} depuis le dernier snapshot progress,
    s'il existe; sinon {}. :contentReference[oaicite:3]{index=3}
    """
    p = get_collection("progress").find_one(
        {"user_challenge_id": uc_id},
        sort=[("checked_at", -1), ("created_at", -1)]
    )
    out: Dict[ObjectId, Dict[str, Any]] = {}
    if not p:
        return out
    for t in (p.get("tasks") or []):
        tid = t.get("task_id")
        if tid:
            out[tid] = {
                "min_count": int(t.get("min_count") or 0),
                "current_count": int(t.get("current_count") or 0),
            }
    return out

def _task_constraints_min_count(task_doc: Dict[str, Any]) -> int:
    return int(((task_doc.get("constraints") or {}).get("min_count") or 0))

def _choose_primary_task_by_ratio(task_matches: List[Dict[str, Any]]) -> Optional[ObjectId]:
    """
    Sélection par RATIO (remaining / max(1,min_count)), puis min_count desc, puis tid asc.
    """
    if not task_matches:
        return None

    def key(d: Dict[str, Any]):
        mc = int(d.get("min_count", 0))
        cur = int(d.get("current_count", 0))
        remaining = max(0, mc - cur)
        ratio = (remaining / max(1, mc)) if mc > 0 else (1.0 if remaining > 0 else 0.0)
        return (-ratio, -mc, str(d.get("_id")))

    return sorted(task_matches, key=key)[0]["_id"]

def _score_cache(match_count: int, total_tasks_not_done: int, max_ratio: float, geo_factor: float,
                 alpha=1.0, beta=1.0, gamma=1.0) -> float:
    """
    S_tasks = match_count / total_tasks_not_done (si 0 -> 0)
    S_urgency = max_ratio (déjà ∈ [0,1])
    S_geo = geo_factor (∈ [0,1])
    score = produit géométrique pondéré
    """
    if total_tasks_not_done <= 0:
        s_tasks = 0.0
    else:
        s_tasks = max(0.0, min(1.0, float(match_count) / float(total_tasks_not_done)))
    s_urg = max(0.0, min(1.0, max_ratio))
    s_geo = max(0.0, min(1.0, geo_factor))
    return (s_tasks ** alpha) * (s_urg ** beta) * (s_geo ** gamma)

# ------------------------------------------------------------
# évaluation
# ------------------------------------------------------------

def evaluate_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    limit_per_task: int = 200,
    hard_limit_total: int = 2000,
    geo_ctx: Optional[Dict[str, Any]] = None,  # {"lat":..,"lon":..,"radius_km":..}
    evaluated_at: Optional[datetime] = None,
    force: bool = False,   # <-- ajouté
) -> Dict[str, Any]:
    """
    Calcule et persiste les targets pour un UC.
    - Anti-join caches non trouvées
    - Exclut caches posées par l'utilisateur (owner == username)
    - Géo optionnelle
    - Fusion multi-tâches, scoring, upserts
    """
    coll_uc = get_collection("user_challenges")
    uc = coll_uc.find_one({"_id": uc_id, "user_id": user_id}, {"_id": 1})
    if not uc:
        raise PermissionError("UserChallenge not found or not owned by user")

    # "ne pas recalculer si on en a assez" : soft cap simple
    coll_targets = get_collection("targets")
    existing = coll_targets.count_documents({"user_id": user_id, "user_challenge_id": uc_id})
    if (not force) and existing >= min(hard_limit_total, limit_per_task * 5):
        return {"ok": True, "inserted": 0, "updated": 0, "total": existing, "skipped": True}

    # Récup params utilisateur
    username = _get_username(user_id)
    user_loc = _get_user_location(user_id)
    ref_latlon = None
    if geo_ctx and "lat" in geo_ctx and "lon" in geo_ctx:
        ref_latlon = (float(geo_ctx["lat"]), float(geo_ctx["lon"]))
    elif user_loc:
        ref_latlon = user_loc  # (lat, lon)

    # Tasks canonisées (déjà en base via put_tasks) :contentReference[oaicite:4]{index=4}
    tasks = list(get_collection("user_challenge_tasks").find(
        {"user_challenge_id": uc_id}
    ).sort([("order", 1), ("_id", 1)]))

    # Progrès courant (pour récupérer min_count/current_count) :contentReference[oaicite:5]{index=5}
    prog_map = _latest_progress_task_map(uc_id)
    not_done_task_ids: List[ObjectId] = []
    for t in tasks:
        mc = _task_constraints_min_count(t)
        cur = int((prog_map.get(t["_id"]) or {}).get("current_count", 0))
        if mc == 0 or cur < mc:
            not_done_task_ids.append(t["_id"])

    # Collecte candidates par task
    unique_by_cache: Dict[ObjectId, Dict[str, Any]] = {}
    total_seen = 0

    for t in tasks:
        expr = t.get("expression") or {}
        # and-only
        sig, match_caches, supported, notes, agg_spec = compile_and_only(expr)
        if not supported:
            continue  # on ignore OR/NOT pour le MVP

        # pipeline sur caches
        pipeline: List[Dict[str, Any]] = []

        # $geoNear en tête si geo_ctx avec radius_km
        use_geo = False
        if geo_ctx and ("lat" in geo_ctx) and ("lon" in geo_ctx) and ("radius_km" in geo_ctx):
            use_geo = True
            pipeline.append({
                "$geoNear": {
                    "near": {"type": "Point", "coordinates": [float(geo_ctx["lon"]), float(geo_ctx["lat"])]},
                    "distanceField": "distance_m",
                    "maxDistance": float(geo_ctx["radius_km"]) * 1000.0,
                    "spherical": True,
                    "key": "loc",
                    "query": {
                        "$or": [
                            {"status": "active"},
                            {"status": {"$exists": False}},
                            {"status": None},
                            # (optionnel) autoriser "enabled"/"available" si tu en as :
                            {"status": "enabled"},
                            {"status": "available"},
                        ]
                    }  # filtre grossier déjà là
                }
            })
        else:
            pipeline.append({"$match": {
                "$or": [
                    {"status": "active"},
                    {"status": {"$exists": False}},
                    {"status": None},
                    # (optionnel) autoriser "enabled"/"available" si tu en as :
                    {"status": "enabled"},
                    {"status": "available"},
                ]
            }})

        # appliquer match_caches
        and_conds: List[Dict[str, Any]] = []
        for field, cond in (match_caches or {}).items():
            if isinstance(cond, list):
                for c in cond:
                    and_conds.append({field: c})
            else:
                and_conds.append({field: cond})

        if and_conds:
            pipeline.append({"$match": {"$and": and_conds}})

        # exclure caches posées par le user courant (si username connu) :contentReference[oaicite:6]{index=6}
        if username:
            pipeline.append({"$match": {"owner": {"$ne": username}}})

        # anti-join found_caches de ce user :contentReference[oaicite:7]{index=7}
        pipeline += [
            {"$lookup": {
                "from": "found_caches",
                "let": {"cache_id": "$_id"},
                "pipeline": [
                    {"$match": {
                        "$expr": {"$and": [
                            {"$eq": ["$cache_id", "$$cache_id"]},
                            {"$eq": ["$user_id", user_id]},
                        ]}
                    }}
                ],
                "as": "found"
            }},
            {"$match": {"found": {"$size": 0}}},
        ]

        # projection minimale
        pipeline.append({"$project": {
            "_id": 1, "GC": 1, "title": 1, "loc": 1, "owner": 1,
            "difficulty": 1, "terrain": 1,
            **({"distance_m": 1} if use_geo else {})
        }})

        pipeline.append({"$limit": int(limit_per_task)})

        rows = list(get_collection("caches").aggregate(pipeline, allowDiskUse=False))

        # Pour chaque cache candidate, attacher la task couverte
        for r in rows:
            cid = r["_id"]
            entry = unique_by_cache.get(cid)
            if not entry:
                entry = {
                    "cache": r,
                    "matched_tasks": [],   # [{_id, min_count, current_count, remaining, ratio}]
                }
                unique_by_cache[cid] = entry
                total_seen += 1
                if total_seen >= hard_limit_total:
                    break

            mc = _task_constraints_min_count(t)
            cur = int((prog_map.get(t["_id"]) or {}).get("current_count", 0))
            remaining = max(0, mc - cur)
            ratio = (remaining / max(1, mc)) if mc > 0 else (1.0 if remaining > 0 else 0.0)
            entry["matched_tasks"].append({
                "_id": t["_id"],
                "min_count": mc,
                "current_count": cur,
                "remaining": remaining,
                "ratio": ratio,
            })
        if total_seen >= hard_limit_total:
            break

    # Upserts
    inserted = 0; updated = 0
    now = evaluated_at or utcnow()

    # total de tasks non terminées (pour S_tasks)
    total_tasks_not_done = len(not_done_task_ids) if not_done_task_ids else max(1, len(tasks))

    for cid, data in unique_by_cache.items():
        matched = data["matched_tasks"]
        if not matched:
            continue

        # primary task selon ratio
        primary_task_id = _choose_primary_task_by_ratio(matched)

        # S_geo
        s_geo = 1.0
        dist_km = None
        if ref_latlon and data["cache"].get("loc") and isinstance(data["cache"]["loc"].get("coordinates"), list):
            lon, lat = data["cache"]["loc"]["coordinates"]
            dist_km = _haversine_km(ref_latlon[0], ref_latlon[1], lat, lon)
            # fonction lissée ~ 10km
            s_geo = 1.0 / (1.0 + (dist_km / 10.0))

        # S_urgency = max ratio des tasks couvertes
        max_ratio = max((m.get("ratio", 0.0) for m in matched), default=0.0)

        # S_tasks = nb tasks correspondantes / nb tasks non-done
        score = _score_cache(len(matched), total_tasks_not_done, max_ratio, s_geo)

        # raisons & diag
        reasons = [f"covers {len(matched)} task(s); max_ratio={round(max_ratio,2)}"] + \
                  ([f"dist≈{round(dist_km,1)}km"] if dist_km is not None else [])

        doc = {
            "user_id": user_id,
            "user_challenge_id": uc_id,
            "cache_id": cid,
            "primary_task_id": primary_task_id,
            "satisfies_task_ids": [m["_id"] for m in matched],
            "score": float(score),
            "reasons": reasons,
            "pinned": False,
            "loc": data["cache"].get("loc"),
            "diagnostics": {
                "matched": matched,
                "subscores": {
                    "tasks": len(matched) / float(total_tasks_not_done or 1),
                    "urgency": max_ratio,
                    "geo": s_geo,
                },
                "evaluated_at": now,
            },
            "updated_at": now,
        }

        # upsert par (user_id, uc_id, cache_id)
        res = get_collection("targets").update_one(
            {"user_id": user_id, "user_challenge_id": uc_id, "cache_id": cid},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        if res.upserted_id:
            inserted += 1
        elif res.modified_count > 0:
            updated += 1

    total = get_collection("targets").count_documents({"user_id": user_id, "user_challenge_id": uc_id})
    return {"ok": True, "inserted": inserted, "updated": updated, "total": int(total)}

# ------------------------------------------------------------
# listings
# ------------------------------------------------------------

def list_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    page: int = 1,
    limit: int = 50,
    sort: str = "-score",
) -> Dict[str, Any]:
    coll = get_collection("targets")
    q = {"user_id": user_id, "user_challenge_id": uc_id}
    sort_spec = [("score", -1)] if sort == "-score" else [("updated_at", -1)]
    skip = max(0, (int(page) - 1) * int(limit))
    cur = coll.find(q).sort(sort_spec).skip(skip).limit(int(limit))
    items = []
    for d in cur:
        items.append({
            "id": str(d.get("_id")),
            "user_challenge_id": str(d.get("user_challenge_id")),
            "cache_id": str(d.get("cache_id")),
            "GC": None,  # join côté front si besoin; on peut aussi enrichir via lookup si nécessaire
            "name": None,
            "loc": (lambda loc: {"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]} if loc else None)(d.get("loc")),
            "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
            "primary_task_id": str(d.get("primary_task_id")) if d.get("primary_task_id") else None,
            "score": float(d.get("score") or 0),
            "reasons": d.get("reasons") or [],
            "pinned": bool(d.get("pinned") or False),
        })
    total = coll.count_documents(q)
    return {"items": items, "total": int(total), "page": int(page), "limit": int(limit)}

def list_targets_nearby_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    lat: float,
    lon: float,
    radius_km: float,
    page: int = 1,
    limit: int = 50,
    sort: str = "distance",
) -> Dict[str, Any]:
    coll = get_collection("targets")
    pipeline: List[Dict[str, Any]] = [
        {"$geoNear": {
            "near": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "distanceField": "distance_m",
            "maxDistance": float(radius_km) * 1000.0,
            "spherical": True,
            "key": "loc",
            "query": {"user_id": user_id, "user_challenge_id": uc_id},
        }},
        {"$sort": {"distance_m": 1 if sort == "distance" else -1}},
        {"$skip": max(0, (int(page)-1) * int(limit))},
        {"$limit": int(limit)},
        {"$project": {
            "_id": 1, "user_challenge_id": 1, "cache_id": 1, "score": 1, "pinned": 1,
            "reasons": 1, "loc": 1, "distance_m": 1, "satisfies_task_ids": 1, "primary_task_id": 1,
        }},
    ]
    rows = list(coll.aggregate(pipeline, allowDiskUse=False))
    items = []
    for d in rows:
        loc = d.get("loc")
        items.append({
            "id": str(d.get("_id")),
            "user_challenge_id": str(d.get("user_challenge_id")),
            "cache_id": str(d.get("cache_id")),
            "GC": None, "name": None,
            "loc": ({"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]} if loc else None),
            "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
            "primary_task_id": str(d.get("primary_task_id")) if d.get("primary_task_id") else None,
            "score": float(d.get("score") or 0),
            "reasons": d.get("reasons") or [],
            "pinned": bool(d.get("pinned") or False),
            "distance_km": round(float(d.get("distance_m") or 0)/1000.0, 3),
        })
    total = coll.count_documents({"user_id": user_id, "user_challenge_id": uc_id})
    return {"items": items, "total": int(total), "page": int(page), "limit": int(limit)}

def list_targets_for_user(
    user_id: ObjectId,
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    sort: str = "-score",
) -> Dict[str, Any]:
    # Optionnel: filtrer par status UC via $lookup user_challenges
    pipeline: List[Dict[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {"$lookup": {
            "from": "user_challenges",
            "localField": "user_challenge_id",
            "foreignField": "_id",
            "as": "uc"
        }},
        {"$unwind": "$uc"},
    ]
    if status_filter:
        pipeline.append({"$match": {"uc.status": status_filter}})
    pipeline += [
        {"$sort": {"score": -1} if sort == "-score" else {"updated_at": -1}},
        {"$skip": max(0, (int(page)-1) * int(limit))},
        {"$limit": int(limit)},
        {"$project": {
            "_id": 1, "user_challenge_id": 1, "cache_id": 1, "score": 1, "pinned": 1,
            "reasons": 1, "loc": 1, "satisfies_task_ids": 1, "primary_task_id": 1,
        }},
    ]
    rows = list(get_collection("targets").aggregate(pipeline, allowDiskUse=False))
    items = []
    for d in rows:
        loc = d.get("loc")
        items.append({
            "id": str(d.get("_id")),
            "user_challenge_id": str(d.get("user_challenge_id")),
            "cache_id": str(d.get("cache_id")),
            "GC": None, "name": None,
            "loc": ({"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]} if loc else None),
            "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
            "primary_task_id": str(d.get("primary_task_id")) if d.get("primary_task_id") else None,
            "score": float(d.get("score") or 0),
            "reasons": d.get("reasons") or [],
            "pinned": bool(d.get("pinned") or False),
        })
    total = get_collection("targets").count_documents({"user_id": user_id})
    return {"items": items, "total": int(total), "page": int(page), "limit": int(limit)}

def list_targets_nearby_for_user(
    user_id: ObjectId,
    lat: float,
    lon: float,
    radius_km: float,
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    sort: str = "distance",
) -> Dict[str, Any]:
    pipeline: List[Dict[str, Any]] = [
        {"$geoNear": {
            "near": {"type": "Point", "coordinates": [float(lon), float(lat)]},
            "distanceField": "distance_m",
            "maxDistance": float(radius_km) * 1000.0,
            "spherical": True,
            "key": "loc",
            "query": {"user_id": user_id},
        }},
        {"$lookup": {
            "from": "user_challenges",
            "localField": "user_challenge_id",
            "foreignField": "_id",
            "as": "uc"
        }},
        {"$unwind": "$uc"},
    ]
    if status_filter:
        pipeline.append({"$match": {"uc.status": status_filter}})

    pipeline += [
        {"$sort": {"distance_m": 1 if sort == "distance" else -1}},
        {"$skip": max(0, (int(page)-1) * int(limit))},
        {"$limit": int(limit)},
        {"$project": {
            "_id": 1, "user_challenge_id": 1, "cache_id": 1, "score": 1, "pinned": 1,
            "reasons": 1, "loc": 1, "distance_m": 1, "satisfies_task_ids": 1, "primary_task_id": 1,
        }},
    ]
    rows = list(get_collection("targets").aggregate(pipeline, allowDiskUse=False))
    items = []
    for d in rows:
        loc = d.get("loc")
        items.append({
            "id": str(d.get("_id")),
            "user_challenge_id": str(d.get("user_challenge_id")),
            "cache_id": str(d.get("cache_id")),
            "GC": None, "name": None,
            "loc": ({"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]} if loc else None),
            "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
            "primary_task_id": str(d.get("primary_task_id")) if d.get("primary_task_id") else None,
            "score": float(d.get("score") or 0),
            "reasons": d.get("reasons") or [],
            "pinned": bool(d.get("pinned") or False),
            "distance_km": round(float(d.get("distance_m") or 0)/1000.0, 3),
        })
    total = get_collection("targets").count_documents({"user_id": user_id})
    return {"items": items, "total": int(total), "page": int(page), "limit": int(limit)}

def delete_targets_for_user_challenge(user_id: ObjectId, uc_id: ObjectId) -> Dict[str, Any]:
    res = get_collection("targets").delete_many({"user_challenge_id": uc_id, "user_id": user_id})
    return {"ok": True, "deleted": int(res.deleted_count)}
