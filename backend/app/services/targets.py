
from __future__ import annotations
from typing import Dict, List, Tuple, Optional
from bson import ObjectId
from pymongo import ASCENDING
from datetime import datetime, timezone

from app.db.mongodb import get_collection
from app.models.target_dto import (
    LocOut, MatchRef, TargetOut, PerTaskBucket,
    TargetsPreviewPerTaskResponse, TargetsPreviewGlobalResponse, CoverageGap,
)

# --------------------------------------------------------------------------------------
# Utilities
# --------------------------------------------------------------------------------------

def _parse_center(s: Optional[str]) -> Optional[tuple[float,float]]:
    if not s:
        return None
    lat_str, lng_str = [x.strip() for x in s.split(",", 1)]
    return (float(lat_str), float(lng_str))

def _parse_bbox(s: Optional[str]) -> Optional[tuple[float,float,float,float]]:
    if not s:
        return None
    a,b,c,d = [float(x.strip()) for x in s.split(",", 3)]
    return (a,b,c,d)

def _year_range(year: int):
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end   = datetime(year+1, 1, 1, tzinfo=timezone.utc)
    return {"$gte": start, "$lt": end}

# --------------------------------------------------------------------------------------
# AST (AND-only) -> Mongo filter (no geo here; geo handled by $geoNear / $geoWithin)
# --------------------------------------------------------------------------------------

def _build_filter_from_task_expr(expr: dict) -> Dict:
    def leaf(node: dict) -> Optional[Dict]:
        k = node.get("kind")
        if k == "type_in":
            ids = node.get("type_ids") or node.get("values") or []
            return {"type_id": {"$in": [ObjectId(x) for x in ids]}}
        if k == "size_in":
            ids = node.get("size_ids") or node.get("values") or []
            return {"size_id": {"$in": [ObjectId(x) for x in ids]}}
        if k == "country_is":
            cid = node.get("country_id") or node.get("value")
            return {"country_id": ObjectId(cid)}
        if k == "state_in":
            ids = node.get("state_ids") or node.get("values") or []
            return {"state_id": {"$in": [ObjectId(x) for x in ids]}}
        if k == "placed_year":
            y = int(node.get("year") or node.get("value"))
            return {"placed_at": _year_range(y)}
        if k == "placed_before":
            # accepts either year or ISO date
            if "date" in node:
                dtv = datetime.fromisoformat(str(node["date"])).replace(tzinfo=timezone.utc)
                return {"placed_at": {"$lt": dtv}}
            y = int(node.get("value"))
            return {"placed_at": {"$lt": datetime(y,1,1,tzinfo=timezone.utc)}}
        if k == "placed_after":
            if "date" in node:
                dtv = datetime.fromisoformat(str(node["date"])).replace(tzinfo=timezone.utc)
                return {"placed_at": {"$gte": dtv}}
            y = int(node.get("value"))
            return {"placed_at": {"$gte": datetime(y,1,1,tzinfo=timezone.utc)}}
        if k == "difficulty_between":
            return {"difficulty": {"$gte": float(node["min"]), "$lte": float(node["max"])}}
        if k == "terrain_between":
            return {"terrain": {"$gte": float(node["min"]), "$lte": float(node["max"])}}
        if k == "attributes":
            ors = []
            for a in node.get("attributes", []):
                doc_id = a.get("attribute_doc_id") or a.get("cache_attribute_id")
                if not doc_id:
                    continue
                ors.append({"attributes": {"$elemMatch": {"attribute_doc_id": ObjectId(doc_id),
                                                          "is_positive": bool(a.get("is_positive", True))}}})
            if ors:
                return {"$and": ors}
            return None
        return None

    clauses: List[Dict] = []
    kind = expr.get("kind")
    if kind == "and":
        for n in expr.get("nodes", []):
            c = leaf(n)
            if c:
                clauses.append(c)
    else:
        c = leaf(expr)
        if c:
            clauses.append(c)
    return {"$and": clauses} if clauses else {}

# --------------------------------------------------------------------------------------
# Scope loaders
# --------------------------------------------------------------------------------------

async def _load_scope_for_uc(uc_id: str) -> List[dict]:
    tasks_coll = get_collection("user_challenge_tasks")
    tasks = list(tasks_coll.find({"user_challenge_id": ObjectId(uc_id)}, {
        "_id": 1, "expression": 1, "constraints": 1, "metrics": 1, "order": 1
    }).sort([("order", 1)]))
    scope: List[dict] = []
    for t in tasks:
        expr = t.get("expression") or {}
        if expr.get("kind") not in (None, "and", "leaf"):
            continue  # OR/NOT non supportés au MVP
        min_count = int((t.get("constraints") or {}).get("min_count", 1))
        current   = int((t.get("metrics") or {}).get("current_count", 0))
        needed = max(0, min_count - current)
        if needed <= 0:
            continue
        scope.append({
            "uc_id": str(ObjectId(uc_id)),
            "task_id": str(t["_id"]),
            "needed": needed,
            "expr": expr,
        })
    return scope

async def _load_scope_multi_uc(user_id: str) -> List[dict]:
    """All accepted UCs of the user, tasks incomplete, AND-only."""
    uc_coll = get_collection("user_challenges")
    uct_coll = get_collection("user_challenge_tasks")

    ucs = list(uc_coll.find({"user_id": ObjectId(user_id), "status": "accepted"}, {"_id": 1}))
    if not ucs:
        return []
    uc_ids = [u["_id"] for u in ucs]
    tasks = list(uct_coll.find({"user_challenge_id": {"$in": uc_ids}}, {
        "_id": 1, "user_challenge_id": 1, "expression": 1, "constraints": 1, "metrics": 1, "order": 1
    }).sort([("user_challenge_id", 1), ("order", 1)]))

    scope: List[dict] = []
    for t in tasks:
        expr = t.get("expression") or {}
        if expr.get("kind") not in (None, "and", "leaf"):
            continue
        min_count = int((t.get("constraints") or {}).get("min_count", 1))
        current   = int((t.get("metrics") or {}).get("current_count", 0))
        needed = max(0, min_count - current)
        if needed <= 0:
            continue
        scope.append({
            "uc_id": str(t["user_challenge_id"]),
            "task_id": str(t["_id"]),
            "needed": needed,
            "expr": expr,
        })
    return scope

# --------------------------------------------------------------------------------------
# Found caches helper
# --------------------------------------------------------------------------------------

def _user_found_cache_ids(user_id: str) -> set[str]:
    coll = get_collection("found_caches")
    return { str(x["cache_id"]) for x in coll.find({"user_id": ObjectId(user_id)}, {"cache_id":1}) }

# --------------------------------------------------------------------------------------
# DB readers: $geoNear when center is present
# --------------------------------------------------------------------------------------

def _find_caches(filter_doc: Dict, limit: int,
                 geo_center: Optional[tuple[float,float]] = None,
                 geo_radius_km: Optional[float] = None,
                 bbox: Optional[tuple[float,float,float,float]] = None) -> List[dict]:
    """
    - If geo_center -> $geoNear pipeline with distance_km.
    - Else if bbox -> find() with $geoWithin.
    - Else -> simple find().
    """
    coll = get_collection("caches")
    base_filter = dict(filter_doc or {})
    proj = {"GC":1,"title":1,"type_id":1,"size_id":1,"difficulty":1,"terrain":1,"loc":1}

    if geo_center:
        lat, lng = geo_center
        near_stage = {
            "$geoNear": {
                "near": {"type": "Point", "coordinates": [lng, lat]},
                "distanceField": "distance_m",
                "spherical": True,
            }
        }
        if geo_radius_km:
            near_stage["$geoNear"]["maxDistance"] = int(geo_radius_km * 1000)
        if base_filter:
            near_stage["$geoNear"]["query"] = base_filter
        pipeline = [
            near_stage,
            {"$project": {**proj, "distance_km": {"$divide": ["$distance_m", 1000.0]}}},
            {"$limit": int(limit)},
        ]
        return list(coll.aggregate(pipeline))

    f = dict(base_filter)
    if bbox:
        minLng, minLat, maxLng, maxLat = bbox
        f["loc"] = {"$geoWithin": {"$box": [[minLng, minLat], [maxLng, maxLat]]}}
    return list(coll.find(f, proj).limit(int(limit)))

# --------------------------------------------------------------------------------------
# Matching & scoring
# --------------------------------------------------------------------------------------

def _compute_matches_for_cache(cache_doc: dict, compiled_filters: List[Tuple[str,str,Dict]]) -> List[Tuple[str,str]]:
    """
    MVP heuristic: assume the candidate stems from one of the compiled task filters;
    we return all (uc_id, task_id) present in compiled_filters. For strict correctness,
    you could recheck each filter with a round-trip: find_one({'_id': cache_id, **filter}).
    """
    return [(uc, task) for (uc, task, _f) in compiled_filters]

def _score(multi: int, distance_km: Optional[float]) -> float:
    base = 1.0 + 0.5 * max(0, multi-1)
    penalty = 0.0 if distance_km is None else min(0.8, distance_km/100.0)
    return max(0.0, base - penalty)

def _target_from_doc(c: dict, matched_pairs: List[Tuple[str,str]]) -> TargetOut:
    lat = c.get("loc", {}).get("coordinates", [None, None])[1]
    lng = c.get("loc", {}).get("coordinates", [None, None])[0]
    dist = c.get("distance_km")
    matched = [MatchRef(uc_id=uc, task_id=task) for (uc, task) in matched_pairs]
    reasons = []
    if len(matched) > 1:
        reasons.append(f"multi-cover: {len(matched)} tasks")
    if dist is not None:
        reasons.append(f"distance: {dist:.1f} km")
    return TargetOut(
        cache_id=str(c["_id"]),
        name=c.get("title") or c.get("GC") or "",
        loc=LocOut(lat=lat or 0.0, lng=lng or 0.0),
        type_id=str(c.get("type_id") or ""),
        difficulty=float(c.get("difficulty") or 0.0),
        terrain=float(c.get("terrain") or 0.0),
        matched=matched,
        score=_score(len(matched), dist),
        reasons=reasons,
        distance_km=dist,
        already_found=False,
        pinned=False,
    )

# --------------------------------------------------------------------------------------
# Public services
# --------------------------------------------------------------------------------------

async def preview_targets_for_uc(
    user_id: str,
    uc_id: str,
    mode: str,
    k: int,
    geo_center: Optional[str],
    geo_radius_km: Optional[float],
    bbox: Optional[str],
    max_candidates_pool: int,
):
    scope = await _load_scope_for_uc(uc_id)
    if not scope:
        if mode == "per_task":
            return TargetsPreviewPerTaskResponse(buckets=[], meta={"k": k, "scope_size": 0, "uc_id": uc_id})
        return TargetsPreviewGlobalResponse(mode="global", selection=[], covered_pairs=0, remaining=[], meta={"k": k, "pool": 0, "scope_size": 0, "uc_id": uc_id})

    center = _parse_center(geo_center); box = _parse_bbox(bbox)
    found = _user_found_cache_ids(user_id)

    compiled: List[Tuple[str,str,Dict]] = []
    for t in scope:
        f = _build_filter_from_task_expr(t["expr"])
        if found:
            f["_id"] = {"$nin": [ObjectId(x) for x in found]}
        compiled.append((t["uc_id"], t["task_id"], f))

    if mode == "per_task":
        buckets: List[PerTaskBucket] = []
        for t in scope:
            f = next(f for (u,task,f) in compiled if task==t["task_id"])
            raw = _find_caches(f, limit=max(1, k*3), geo_center=center, geo_radius_km=geo_radius_km, bbox=box)
            targets = []
            for c in raw:
                matched_pairs = _compute_matches_for_cache(c, compiled)
                if not matched_pairs:
                    continue
                targets.append(_target_from_doc(c, matched_pairs))
            targets.sort(key=lambda x: x.score, reverse=True)
            buckets.append(PerTaskBucket(
                uc_id=t["uc_id"], task_id=t["task_id"], needed=t["needed"],
                candidates=targets[:k]
            ))
        return TargetsPreviewPerTaskResponse(buckets=buckets, meta={"k": k, "scope_size": len(scope), "uc_id": uc_id})

    # global (UC unique) set-cover
    pool_map: Dict[str, dict] = {}
    per_task_top = max(1, min(k*5, 100))
    for (_uc, _task, f) in compiled:
        for c in _find_caches(f, limit=per_task_top, geo_center=center, geo_radius_km=geo_radius_km, bbox=box):
            pool_map[str(c["_id"])] = c
            if len(pool_map) >= max_candidates_pool: break
        if len(pool_map) >= max_candidates_pool: break

    pool = list(pool_map.values())
    cache_matches: Dict[str, List[Tuple[str,str]]] = {}
    for c in pool:
        cache_matches[str(c["_id"])] = _compute_matches_for_cache(c, compiled)

    targets = [_target_from_doc(c, cache_matches[str(c["_id"])]) for c in pool if cache_matches[str(c["_id"])]]

    remaining: Dict[str, int] = { t["task_id"]: t["needed"] for t in scope }
    selection: List[TargetOut] = []
    while len(selection) < k:
        best = None; best_gain = 0
        for tg in targets:
            gain = sum(1 for m in tg.matched if remaining[m.task_id] > 0)
            if gain > best_gain or (gain == best_gain and best and tg.score > best.score):
                best, best_gain = tg, gain
        if not best or best_gain == 0: break
        selection.append(best)
        for m in best.matched:
            if remaining[m.task_id] > 0:
                remaining[m.task_id] -= 1
        targets = [t for t in targets if t.cache_id != best.cache_id]

    covered_pairs = 0
    remaining_list: List[CoverageGap] = []
    for t in scope:
        rem = remaining[t["task_id"]]
        covered_pairs += (t["needed"] - rem)
        if rem > 0:
            remaining_list.append(CoverageGap(uc_id=t["uc_id"], task_id=t["task_id"], remaining=rem))

    return TargetsPreviewGlobalResponse(
        selection=selection,
        covered_pairs=covered_pairs,
        remaining=remaining_list,
        meta={"k": k, "pool": len(pool), "scope_size": len(scope), "uc_id": uc_id}
    )

async def preview_targets_multi_uc(
    user_id: str,
    mode: str,
    k: int,
    geo_center: Optional[str],
    geo_radius_km: Optional[float],
    bbox: Optional[str],
    max_candidates_pool: int,
):
    """Cross-challenges preview: find caches that advance multiple accepted UCs at once."""
    scope = await _load_scope_multi_uc(user_id)
    if not scope:
        if mode == "per_task":
            return TargetsPreviewPerTaskResponse(buckets=[], meta={"k": k, "scope_size": 0})
        return TargetsPreviewGlobalResponse(mode="global", selection=[], covered_pairs=0, remaining=[], meta={"k": k, "pool": 0, "scope_size": 0})

    center = _parse_center(geo_center); box = _parse_bbox(bbox)
    found = _user_found_cache_ids(user_id)

    compiled: List[Tuple[str,str,Dict]] = []
    for t in scope:
        f = _build_filter_from_task_expr(t["expr"])
        if found:
            f["_id"] = {"$nin": [ObjectId(x) for x in found]}
        compiled.append((t["uc_id"], t["task_id"], f))

    if mode == "per_task":
        buckets: List[PerTaskBucket] = []
        for t in scope:
            f = next(f for (u,task,f) in compiled if u==t["uc_id"] and task==t["task_id"])
            raw = _find_caches(f, limit=max(1, k*3), geo_center=center, geo_radius_km=geo_radius_km, bbox=box)
            targets = []
            for c in raw:
                matched_pairs = _compute_matches_for_cache(c, compiled)
                if not matched_pairs:
                    continue
                targets.append(_target_from_doc(c, matched_pairs))
            targets.sort(key=lambda x: x.score, reverse=True)
            buckets.append(PerTaskBucket(
                uc_id=t["uc_id"], task_id=t["task_id"], needed=t["needed"],
                candidates=targets[:k]
            ))
        return TargetsPreviewPerTaskResponse(buckets=buckets, meta={"k": k, "scope_size": len(scope)})

    # global: true set-cover across ALL remaining tasks of ALL accepted UCs
    pool_map: Dict[str, dict] = {}
    per_task_top = max(1, min(k*5, 100))
    for (_uc, _task, f) in compiled:
        for c in _find_caches(f, limit=per_task_top, geo_center=center, geo_radius_km=geo_radius_km, bbox=box):
            pool_map[str(c["_id"])] = c
            if len(pool_map) >= max_candidates_pool: break
        if len(pool_map) >= max_candidates_pool: break

    pool = list(pool_map.values())
    cache_matches: Dict[str, List[Tuple[str,str]]] = {}
    for c in pool:
        cache_matches[str(c["_id"])] = _compute_matches_for_cache(c, compiled)

    targets = [_target_from_doc(c, cache_matches[str(c["_id"])]) for c in pool if cache_matches[str(c["_id"])]]

    remaining: Dict[Tuple[str,str], int] = {(t["uc_id"], t["task_id"]): t["needed"] for t in scope}
    selection: List[TargetOut] = []
    while len(selection) < k:
        best = None; best_gain = 0
        for tg in targets:
            gain = sum(1 for m in tg.matched if remaining[(m.uc_id, m.task_id)] > 0)
            if gain > best_gain or (gain == best_gain and best and tg.score > best.score):
                best, best_gain = tg, gain
        if not best or best_gain == 0: break
        selection.append(best)
        for m in best.matched:
            key = (m.uc_id, m.task_id)
            if remaining[key] > 0:
                remaining[key] -= 1
        targets = [t for t in targets if t.cache_id != best.cache_id]

    covered_pairs = 0
    remaining_list: List[CoverageGap] = []
    for t in scope:
        key = (t["uc_id"], t["task_id"])
        rem = remaining[key]
        covered_pairs += (t["needed"] - rem)
        if rem > 0:
            remaining_list.append(CoverageGap(uc_id=t["uc_id"], task_id=t["task_id"], remaining=rem))

    return TargetsPreviewGlobalResponse(
        selection=selection,
        covered_pairs=covered_pairs,
        remaining=remaining_list,
        meta={"k": k, "pool": len(pool), "scope_size": len(scope)}
    )
