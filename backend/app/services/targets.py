# app/services/targets.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from bson import ObjectId
from datetime import datetime

from app.db.mongodb import get_collection


def evaluate_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    limit_per_task: int = 500,
    hard_limit_total: int = 2000,
    geo_ctx: Optional[Dict[str, Any]] = None,
    evaluated_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Calcule les targets pour un UserChallenge donné.
    - Évalue chaque tâche -> liste de caches candidates.
    - Déduplique par cache_id, compile satisfies_task_ids.
    - Calcule un score global par cache.
    - Persiste en base (upsert) dans la collection `targets`.

    :param user_id: identifiant de l'utilisateur
    :param uc_id: identifiant du user_challenge
    :param limit_per_task: limite max de caches évaluées par tâche
    :param hard_limit_total: limite max globale de caches avant fusion
    :param geo_ctx: contexte géographique optionnel (lat/lon/radius)
    :param evaluated_at: horodatage du calcul
    :return: dict {"ok": True, "inserted": n, "updated": m, "total": t}
    """
    # TODO: implémenter la logique
    return {"ok": True, "inserted": 0, "updated": 0, "total": 0}


def list_targets_for_user_challenge(
    user_id: ObjectId,
    uc_id: ObjectId,
    page: int = 1,
    limit: int = 50,
    sort: str = "-score",
) -> Dict[str, Any]:
    """
    Liste paginée des targets pour un UserChallenge donné.
    :return: dict {items, total, page, limit}
    """
    # TODO: query sur coll = get_collection("targets")
    return {"items": [], "total": 0, "page": page, "limit": limit}


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
    """
    Liste paginée des targets proches d'un point pour un UserChallenge donné.
    """
    # TODO: query avec $near
    return {"items": [], "total": 0, "page": page, "limit": limit}


def list_targets_for_user(
    user_id: ObjectId,
    status_filter: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    sort: str = "-score",
) -> Dict[str, Any]:
    """
    Liste paginée des targets sur l'ensemble des UserChallenges de l'utilisateur.
    Optionnellement filtrés par status UC.
    """
    # TODO: aggregation sur targets + filtre user_id (+status_filter via join UC si besoin)
    return {"items": [], "total": 0, "page": page, "limit": limit}


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
    """
    Liste paginée des targets proches d'un point, tous challenges confondus.
    """
    # TODO: aggregation avec $near
    return {"items": [], "total": 0, "page": page, "limit": limit}


def delete_targets_for_user_challenge(user_id: ObjectId, uc_id: ObjectId) -> Dict[str, Any]:
    """
    Supprime tous les targets liés à un UserChallenge pour l'utilisateur.
    """
    coll = get_collection("targets")
    res = coll.delete_many({"user_challenge_id": uc_id})
    return {"ok": True, "deleted": int(res.deleted_count)}

def choose_primary_task(task_matches: list[dict]) -> Optional[ObjectId]:
    """
    Sélectionne la primary task parmi une liste de tâches satisfaites par une même cache.
    Règle :
      1) max(remaining = min_count - current_count)
      2) puis max(min_count)
      3) puis min(_id) pour stabilité déterministe
    """
    if not task_matches:
        return None

    def sort_key(t: dict):
        remaining = int(t.get("min_count", 0)) - int(t.get("current_count", 0))
        min_count = int(t.get("min_count", 0))
        tid = str(t.get("_id"))  # stable et comparable
        return (-remaining, -min_count, tid)

    best = sorted(task_matches, key=sort_key)[0]
    return best["_id"]
