# backend/app/services/targets.py
# Calcule des caches candidates par UserChallenge (anti-join des trouvailles, scoring, géo), et listings.
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from math import asin, cos, radians, sin, sqrt
from typing import Any

from bson import ObjectId

from app.core.utils import utcnow
from app.db.mongodb import get_collection
from app.services.query_builder import compile_and_only  # <- brique commune

# ------------------------------------------------------------
# utilitaires
# ------------------------------------------------------------


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance Haversine en kilomètres.

    Args:
        lat1: Latitude point A.
        lon1: Longitude point A.
        lat2: Latitude point B.
        lon2: Longitude point B.

    Returns:
        float: Distance en kilomètres.
    """
    R = 6371.0
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return 2 * R * asin(sqrt(a))


async def _get_username(user_id: ObjectId) -> str | None:
    """Obtenir le username d’un utilisateur.

    Args:
        user_id: Identifiant utilisateur.

    Returns:
        str | None: `username` ou None si absent.
    """
    coll_users = await get_collection("users")
    u = await coll_users.find_one({"_id": user_id}, {"username": 1})
    return (u or {}).get("username")


async def _get_user_location(user_id: ObjectId) -> tuple[float, float] | None:
    """Obtenir la dernière position utilisateur (lat, lon).

    Returns:
        tuple[float, float] | None: (lat, lon) si disponible, sinon None.
    """
    coll_users = await get_collection("users")
    u = await coll_users.find_one({"_id": user_id}, {"location": 1})
    loc = (u or {}).get("location")
    if loc and isinstance(loc, dict) and (loc.get("type") == "Point"):
        lon, lat = loc.get("coordinates") or [None, None]
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return (lat, lon)
    return None


async def _latest_progress_task_map(uc_id: ObjectId) -> dict[ObjectId, dict[str, Any]]:
    """Index des métriques par tâche depuis le dernier snapshot.

    Description:
        Retourne `{task_id: {'min_count': int, 'current_count': int}}` pour l’UC.

    Args:
        uc_id: Id du UserChallenge.

    Returns:
        dict: Carte `task_id -> {min_count, current_count}`.
    """
    coll_progress = await get_collection("progress")
    p = await coll_progress.find_one(
        {"user_challenge_id": uc_id}, sort=[("checked_at", -1), ("created_at", -1)]
    )
    out: dict[ObjectId, dict[str, Any]] = {}
    if not p:
        return out
    for t in p.get("tasks") or []:
        tid = t.get("task_id")
        if tid:
            out[tid] = {
                "min_count": int(t.get("min_count") or 0),
                "current_count": int(t.get("current_count") or 0),
            }
    return out


def _task_constraints_min_count(task_doc: dict[str, Any]) -> int:
    """Extraire `min_count` des contraintes d’une tâche.

    Args:
        task_doc: Document tâche.

    Returns:
        int: Valeur `min_count` (défaut 0).
    """
    return int((task_doc.get("constraints") or {}).get("min_count") or 0)


def _choose_primary_task_by_ratio(task_matches: list[dict[str, Any]]) -> ObjectId | None:
    """Choisir la tâche primaire par ratio d’urgence.

    Description:
        Trie par `remaining/min_count` décroissant, puis `min_count` décroissant, puis id.

    Args:
        task_matches: Liste d’items `{_id, min_count, current_count, remaining, ratio}`.

    Returns:
        ObjectId | None: `task_id` primaire ou None.
    """
    if not task_matches:
        return None

    def key(d: dict[str, Any]):
        mc = int(d.get("min_count", 0))
        cur = int(d.get("current_count", 0))
        remaining = max(0, mc - cur)
        ratio = (remaining / max(1, mc)) if mc > 0 else (1.0 if remaining > 0 else 0.0)
        return (-ratio, -mc, str(d.get("_id")))

    return sorted(task_matches, key=key)[0]["_id"]


def _score_cache(
    match_count: int,
    total_tasks_not_done: int,
    max_ratio: float,
    geo_factor: float,
    alpha=1.0,
    beta=1.0,
    gamma=1.0,
) -> float:
    """Calculer un score multiplicatif (tâches × urgence × géo).

    Args:
        match_count: Nombre de tâches couvertes.
        total_tasks_not_done: Tâches restantes au global.
        max_ratio: Urgence max parmi les matches.
        geo_factor: Facteur ∈ [0,1] dérivé de la distance.
        alpha: Poids S_tasks.
        beta: Poids S_urgency.
        gamma: Poids S_geo.

    Returns:
        float: Score final.
    """
    if total_tasks_not_done <= 0:
        s_tasks = 0.0
    else:
        s_tasks = max(0.0, min(1.0, float(match_count) / float(total_tasks_not_done)))
    s_urg = max(0.0, min(1.0, max_ratio))
    s_geo = max(0.0, min(1.0, geo_factor))
    return (s_tasks**alpha) * (s_urg**beta) * (s_geo**gamma)


# ------------------------------------------------------------
# évaluation
# ------------------------------------------------------------


async def evaluate_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    limit_per_task: int = 200,
    hard_limit_total: int = 2000,
    geo_ctx: dict[str, Any] | None = None,
    evaluated_at: datetime | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Évaluer/persister les targets d’un UserChallenge.

    Description:
        - Anti-join des caches déjà trouvées par l’utilisateur.
        - Exclusion des caches posées par le user (`owner != username`).
        - Filtre géo optionnel (via `$geoNear`) + calcul d’un score.
        - Upsert par `(user_id, user_challenge_id, cache_id)`.

    Args:
        user_id: Utilisateur propriétaire.
        uc_id: UserChallenge ciblé.
        limit_per_task: Cap par tâche.
        hard_limit_total: Cap global d’agrégation.
        geo_ctx: Contexte géo `{lat, lon, radius_km}`.
        evaluated_at: Timestamp d’évaluation (défaut: maintenant).
        force: Ne pas court-circuiter si suffisamment de targets existent.

    Returns:
        dict: `{ok, inserted, updated, total, skipped?}`.
    """
    coll_uc = await get_collection("user_challenges")
    uc = await coll_uc.find_one({"_id": uc_id, "user_id": user_id}, {"_id": 1})
    if not uc:
        raise PermissionError("UserChallenge not found or not owned by user")

    # "ne pas recalculer si on en a assez" : soft cap simple
    coll_targets = await get_collection("targets")
    existing = await coll_targets.count_documents({"user_id": user_id, "user_challenge_id": uc_id})
    if (not force) and existing >= min(hard_limit_total, limit_per_task * 5):
        return {
            "ok": True,
            "inserted": 0,
            "updated": 0,
            "total": existing,
            "skipped": True,
        }

    # Récup params utilisateur
    username = await _get_username(user_id)
    user_loc = await _get_user_location(user_id)
    ref_latlon = None
    if geo_ctx and "lat" in geo_ctx and "lon" in geo_ctx:
        ref_latlon = (float(geo_ctx["lat"]), float(geo_ctx["lon"]))
    elif user_loc:
        ref_latlon = user_loc  # (lat, lon)

    # Tasks canonisées (déjà en base via put_tasks) :contentReference[oaicite:4]{index=4}
    coll_uctasks = await get_collection("user_challenge_tasks")
    cursor = coll_uctasks.find({"user_challenge_id": uc_id}).sort([("order", 1), ("_id", 1)])
    tasks = await cursor.to_list(length=None)

    # Progrès courant (pour récupérer min_count/current_count) :contentReference[oaicite:5]{index=5}
    prog_map = await _latest_progress_task_map(uc_id)
    not_done_task_ids: list[ObjectId] = []
    for t in tasks:
        mc = _task_constraints_min_count(t)
        cur = int((prog_map.get(t["_id"]) or {}).get("current_count", 0))
        if mc == 0 or cur < mc:
            not_done_task_ids.append(t["_id"])

    # Collecte candidates par task
    unique_by_cache: dict[ObjectId, dict[str, Any]] = {}
    total_seen = 0

    coll_caches = await get_collection("caches")
    for t in tasks:
        expr = t.get("expression") or {}
        # and-only
        sig, match_caches, supported, notes, agg_spec = compile_and_only(expr)
        if not supported:
            continue  # on ignore OR/NOT pour le MVP

        # pipeline sur caches
        pipeline: list[Mapping[str, Any]] = []

        # $geoNear en tête si geo_ctx avec radius_km
        use_geo = False
        if geo_ctx and ("lat" in geo_ctx) and ("lon" in geo_ctx) and ("radius_km" in geo_ctx):
            use_geo = True
            pipeline.append(
                {
                    "$geoNear": {
                        "near": {
                            "type": "Point",
                            "coordinates": [
                                float(geo_ctx["lon"]),
                                float(geo_ctx["lat"]),
                            ],
                        },
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
                        },  # filtre grossier déjà là
                    }
                }
            )
        else:
            pipeline.append(
                {
                    "$match": {
                        "$or": [
                            {"status": "active"},
                            {"status": {"$exists": False}},
                            {"status": None},
                            # (optionnel) autoriser "enabled"/"available" si tu en as :
                            {"status": "enabled"},
                            {"status": "available"},
                        ]
                    }
                }
            )

        # appliquer match_caches
        and_conds: list[dict[str, Any]] = []
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
            {
                "$lookup": {
                    "from": "found_caches",
                    "let": {"cache_id": "$_id"},
                    "pipeline": [
                        {
                            "$match": {
                                "$expr": {
                                    "$and": [
                                        {"$eq": ["$cache_id", "$$cache_id"]},
                                        {"$eq": ["$user_id", user_id]},
                                    ]
                                }
                            }
                        }
                    ],
                    "as": "found",
                }
            },
            {"$match": {"found": {"$size": 0}}},
        ]

        # projection minimale
        pipeline.append(
            {
                "$project": {
                    "_id": 1,
                    "GC": 1,
                    "title": 1,
                    "loc": 1,
                    "owner": 1,
                    "difficulty": 1,
                    "terrain": 1,
                    **({"distance_m": 1} if use_geo else {}),
                }
            }
        )

        pipeline.append({"$limit": int(limit_per_task)})

        aggregate_cursor = coll_caches.aggregate(pipeline, allowDiskUse=False)
        rows = await aggregate_cursor.to_list(length=None)

        # Pour chaque cache candidate, attacher la task couverte
        for r in rows:
            cid = r["_id"]
            entry = unique_by_cache.get(cid)
            if not entry:
                entry = {
                    "cache": r,
                    "matched_tasks": [],  # [{_id, min_count, current_count, remaining, ratio}]
                }
                unique_by_cache[cid] = entry
                total_seen += 1
                if total_seen >= hard_limit_total:
                    break

            mc = _task_constraints_min_count(t)
            cur = int((prog_map.get(t["_id"]) or {}).get("current_count", 0))
            remaining = max(0, mc - cur)
            ratio = (remaining / max(1, mc)) if mc > 0 else (1.0 if remaining > 0 else 0.0)
            entry["matched_tasks"].append(
                {
                    "_id": t["_id"],
                    "min_count": mc,
                    "current_count": cur,
                    "remaining": remaining,
                    "ratio": ratio,
                }
            )
        if total_seen >= hard_limit_total:
            break

    # Upserts
    inserted = 0
    updated = 0
    now = evaluated_at or utcnow()

    # total de tasks non terminées (pour S_tasks)
    total_tasks_not_done = len(not_done_task_ids) if not_done_task_ids else max(1, len(tasks))

    coll_targets = await get_collection("targets")
    for cid, data in unique_by_cache.items():
        matched = data["matched_tasks"]
        if not matched:
            continue

        # primary task selon ratio
        primary_task_id = _choose_primary_task_by_ratio(matched)

        # S_geo
        s_geo = 1.0
        dist_km = None
        if (
            ref_latlon
            and data["cache"].get("loc")
            and isinstance(data["cache"]["loc"].get("coordinates"), list)
        ):
            lon, lat = data["cache"]["loc"]["coordinates"]
            dist_km = _haversine_km(ref_latlon[0], ref_latlon[1], lat, lon)
            # fonction lissée ~ 10km
            s_geo = 1.0 / (1.0 + (dist_km / 10.0))

        # S_urgency = max ratio des tasks couvertes
        max_ratio = max((m.get("ratio", 0.0) for m in matched), default=0.0)

        # S_tasks = nb tasks correspondantes / nb tasks non-done
        score = _score_cache(len(matched), total_tasks_not_done, max_ratio, s_geo)

        # raisons & diag
        reasons = [f"covers {len(matched)} task(s); max_ratio={round(max_ratio, 2)}"] + (
            [f"dist≈{round(dist_km, 1)}km"] if dist_km is not None else []
        )

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
        res = await coll_targets.update_one(
            {"user_id": user_id, "user_challenge_id": uc_id, "cache_id": cid},
            {"$set": doc, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
        if res.upserted_id:
            inserted += 1
        elif res.modified_count > 0:
            updated += 1

    total = await coll_targets.count_documents({"user_id": user_id, "user_challenge_id": uc_id})
    return {"ok": True, "inserted": inserted, "updated": updated, "total": int(total)}


# ------------------------------------------------------------
# listings
# ------------------------------------------------------------


async def list_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    page: int = 1,
    page_size: int = 50,
    sort: str = "-score",
) -> dict[str, Any]:
    """Lister les targets d’un UserChallenge (paginé).

    Args:
        user_id: Utilisateur.
        uc_id: UserChallenge.
        page: Numéro de page.
        page_size: Taille de page.
        sort: Clé de tri (ex. `-score`).

    Returns:
        dict: `{items, nb_items, page, page_size, nb_pages}`.
    """
    coll_targets = await get_collection("targets")
    q = {"user_id": user_id, "user_challenge_id": uc_id}
    sort_spec = [("score", -1)] if sort == "-score" else [("updated_at", -1)]
    skip = max(0, (page - 1) * page_size)
    cursor = coll_targets.find(q).sort(sort_spec).skip(skip).limit(page_size)
    rows = await cursor.to_list(length=page_size)
    items = []
    for d in rows:
        items.append(
            {
                "id": str(d.get("_id")),
                "user_challenge_id": str(d.get("user_challenge_id")),
                "cache_id": str(d.get("cache_id")),
                "GC": None,  # join côté front si besoin; on peut aussi enrichir via lookup si nécessaire
                "name": None,
                "loc": (
                    lambda loc: (
                        {"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]}
                        if loc
                        else None
                    )
                )(d.get("loc")),
                "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
                "primary_task_id": (
                    str(d.get("primary_task_id")) if d.get("primary_task_id") else None
                ),
                "score": float(d.get("score") or 0),
                "reasons": d.get("reasons") or [],
                "pinned": bool(d.get("pinned") or False),
            }
        )
    nb_items = await coll_targets.count_documents(q)
    nb_pages = nb_items // page_size + (1 if nb_items % page_size != 0 else 0)

    return {
        "items": items,
        "nb_items": nb_items,
        "page": page,
        "page_size": page_size,
        "nb_pages": nb_pages,
    }


async def list_targets_nearby_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    lat: float,
    lon: float,
    radius_km: float,
    page: int = 1,
    page_size: int = 50,
    sort: str = "distance",
) -> dict[str, Any]:
    """Lister les targets proches (par UC) via `$geoNear`.

    Args:
        user_id: Utilisateur.
        uc_id: UserChallenge.
        lat: Latitude de référence.
        lon: Longitude de référence.
        radius_km: Rayon en kilomètres.
        page: Page (≥1).
        page_size: Taille de page.
        sort: `distance` (asc) ou `-distance` (desc).

    Returns:
        dict: `{items, nb_items, page, page_size, nb_pages}` avec `distance_km`.
    """
    coll_targets = await get_collection("targets")
    pipeline: list[Mapping[str, Any]] = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "distanceField": "distance_m",
                "maxDistance": float(radius_km) * 1000.0,
                "spherical": True,
                "key": "loc",
                "query": {"user_id": user_id, "user_challenge_id": uc_id},
            }
        },
        {"$sort": {"distance_m": 1 if sort == "distance" else -1}},
        {"$skip": max(0, (page - 1) * page_size)},
        {"$limit": page_size},
        {
            "$project": {
                "_id": 1,
                "user_challenge_id": 1,
                "cache_id": 1,
                "score": 1,
                "pinned": 1,
                "reasons": 1,
                "loc": 1,
                "distance_m": 1,
                "satisfies_task_ids": 1,
                "primary_task_id": 1,
            }
        },
    ]
    cursor = coll_targets.aggregate(pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    items = []
    for d in rows:
        loc = d.get("loc")
        items.append(
            {
                "id": str(d.get("_id")),
                "user_challenge_id": str(d.get("user_challenge_id")),
                "cache_id": str(d.get("cache_id")),
                "GC": None,
                "name": None,
                "loc": (
                    {"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]} if loc else None
                ),
                "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
                "primary_task_id": (
                    str(d.get("primary_task_id")) if d.get("primary_task_id") else None
                ),
                "score": float(d.get("score") or 0),
                "reasons": d.get("reasons") or [],
                "pinned": bool(d.get("pinned") or False),
                "distance_km": round(float(d.get("distance_m") or 0) / 1000.0, 3),
            }
        )
    nb_items = await coll_targets.count_documents({"user_id": user_id, "user_challenge_id": uc_id})
    nb_pages = nb_items // page_size + (1 if nb_items % page_size != 0 else 0)

    return {
        "items": items,
        "nb_items": nb_items,
        "page": page,
        "page_size": page_size,
        "nb_pages": nb_pages,
    }


async def list_targets_for_user(
    user_id: ObjectId,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort: str = "-score",
) -> dict[str, Any]:
    """Lister toutes les targets de l’utilisateur (tous challenges).

    Args:
        user_id: Utilisateur.
        status_filter: Filtre sur le statut UC (ex. 'accepted').
        page: Page (≥1).
        page_size: Taille de page.
        sort: `-score` ou `updated_at`.

    Returns:
        dict: `{items, nb_items, page, page_size, nb_pages}`.
    """
    coll_targets = await get_collection("targets")
    pipeline: list[Mapping[str, Any]] = [
        {"$match": {"user_id": user_id}},
        {
            "$lookup": {
                "from": "user_challenges",
                "localField": "user_challenge_id",
                "foreignField": "_id",
                "as": "uc",
            }
        },
        {"$unwind": "$uc"},
    ]
    if status_filter:
        pipeline.append({"$match": {"uc.status": status_filter}})
    pipeline += [
        {"$sort": {"score": -1} if sort == "-score" else {"updated_at": -1}},
        {"$skip": max(0, (page - 1) * page_size)},
        {"$limit": page_size},
        {
            "$project": {
                "_id": 1,
                "user_challenge_id": 1,
                "cache_id": 1,
                "score": 1,
                "pinned": 1,
                "reasons": 1,
                "loc": 1,
                "satisfies_task_ids": 1,
                "primary_task_id": 1,
            }
        },
    ]
    cursor = coll_targets.aggregate(pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    items = []
    for d in rows:
        loc = d.get("loc")
        items.append(
            {
                "id": str(d.get("_id")),
                "user_challenge_id": str(d.get("user_challenge_id")),
                "cache_id": str(d.get("cache_id")),
                "GC": None,
                "name": None,
                "loc": (
                    {"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]} if loc else None
                ),
                "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
                "primary_task_id": (
                    str(d.get("primary_task_id")) if d.get("primary_task_id") else None
                ),
                "score": float(d.get("score") or 0),
                "reasons": d.get("reasons") or [],
                "pinned": bool(d.get("pinned") or False),
            }
        )
    nb_items = await coll_targets.count_documents({"user_id": user_id})
    nb_pages = nb_items // page_size + (1 if nb_items % page_size != 0 else 0)

    return {
        "items": items,
        "nb_items": nb_items,
        "page": page,
        "page_size": page_size,
        "nb_pages": nb_pages,
    }


async def list_targets_nearby_for_user(
    user_id: ObjectId,
    lat: float,
    lon: float,
    radius_km: float,
    status_filter: str | None = None,
    page: int = 1,
    page_size: int = 50,
    sort: str = "distance",
) -> dict[str, Any]:
    """Lister les targets proches (tous challenges) via `$geoNear`.

    Args:
        user_id: Utilisateur.
        lat: Latitude de référence.
        lon: Longitude de référence.
        radius_km: Rayon en kilomètres.
        status_filter: Filtre statut UC (optionnel).
        page: Page (≥1).
        page_size: Taille de page.
        sort: `distance` (asc) ou `-distance` (desc).

    Returns:
        dict: `{items, nb_items, page, page_size, nb_pages}` avec `distance_km`.
    """
    coll_targets = await get_collection("targets")
    pipeline: list[Mapping[str, Any]] = [
        {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "distanceField": "distance_m",
                "maxDistance": float(radius_km) * 1000.0,
                "spherical": True,
                "key": "loc",
                "query": {"user_id": user_id},
            }
        },
        {
            "$lookup": {
                "from": "user_challenges",
                "localField": "user_challenge_id",
                "foreignField": "_id",
                "as": "uc",
            }
        },
        {"$unwind": "$uc"},
    ]
    if status_filter:
        pipeline.append({"$match": {"uc.status": status_filter}})

    pipeline += [
        {"$sort": {"distance_m": 1 if sort == "distance" else -1}},
        {"$skip": max(0, (page - 1) * page_size)},
        {"$limit": page_size},
        {
            "$project": {
                "_id": 1,
                "user_challenge_id": 1,
                "cache_id": 1,
                "score": 1,
                "pinned": 1,
                "reasons": 1,
                "loc": 1,
                "distance_m": 1,
                "satisfies_task_ids": 1,
                "primary_task_id": 1,
            }
        },
    ]
    cursor = coll_targets.aggregate(pipeline, allowDiskUse=False)
    rows = await cursor.to_list(length=None)
    items = []
    for d in rows:
        loc = d.get("loc")
        items.append(
            {
                "id": str(d.get("_id")),
                "user_challenge_id": str(d.get("user_challenge_id")),
                "cache_id": str(d.get("cache_id")),
                "GC": None,
                "name": None,
                "loc": (
                    {"lat": loc["coordinates"][1], "lng": loc["coordinates"][0]} if loc else None
                ),
                "matched_task_ids": [str(x) for x in (d.get("satisfies_task_ids") or [])],
                "primary_task_id": (
                    str(d.get("primary_task_id")) if d.get("primary_task_id") else None
                ),
                "score": float(d.get("score") or 0),
                "reasons": d.get("reasons") or [],
                "pinned": bool(d.get("pinned") or False),
                "distance_km": round(float(d.get("distance_m") or 0) / 1000.0, 3),
            }
        )
    nb_items = await coll_targets.count_documents({"user_id": user_id})
    nb_pages = nb_items // page_size + (1 if nb_items % page_size != 0 else 0)

    return {
        "items": items,
        "nb_items": nb_items,
        "page": page,
        "page_size": page_size,
        "nb_pages": nb_pages,
    }


async def delete_targets_for_user_challenge(user_id: ObjectId, uc_id: ObjectId) -> dict[str, Any]:
    """Supprimer toutes les targets d’un UserChallenge.

    Args:
        user_id: Utilisateur.
        uc_id: UserChallenge.

    Returns:
        dict: `{ok, deleted}`.
    """
    coll_targets = await get_collection("targets")
    res = await coll_targets.delete_many({"user_challenge_id": uc_id, "user_id": user_id})
    return {"ok": True, "deleted": int(res.deleted_count)}
