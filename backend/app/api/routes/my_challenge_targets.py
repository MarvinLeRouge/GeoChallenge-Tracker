# app/api/routes/targets.py
from __future__ import annotations

from typing import Any, Dict, List, Optional
from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_current_user
from app.core.utils import utcnow
from app.services import user_profile
from backend.app.services.targets import (
    evaluate_targets_for_user_challenge,
    list_targets_for_user,
    list_targets_for_user_challenge,
    list_targets_nearby_for_user_challenge,
    list_targets_nearby_for_user,
    delete_targets_for_user_challenge,
)

router = APIRouter(prefix="/my", tags=["targets"])


# ---------------------------
# Helpers
# ---------------------------

def _as_objid(v: Any) -> ObjectId:
    if isinstance(v, ObjectId):
        return v
    return ObjectId(str(v))


def _current_user_id(current_user: dict) -> ObjectId:
    uid = current_user.get("_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Unauthenticated.")
    return _as_objid(uid)


# ---------------------------
# Evaluate / refresh (per UserChallenge)
# ---------------------------

@router.post(
    "/challenges/{uc_id}/targets/evaluate",
    status_code=status.HTTP_200_OK,
)
def evaluate_targets(
    uc_id: str,
    limit_per_task: int = Query(500, ge=1, le=5000, description="Cap de calcul par tâche."),
    hard_limit_total: int = Query(2000, ge=1, le=20000, description="Cap global avant fusion/score."),
    include_geo_filter: bool = Query(False, description="Appliquer un filtre géographique pendant l'évaluation."),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    radius_km: Optional[float] = Query(None, gt=0, description="Rayon pour filtre géo si activé."),
    current_user=Depends(get_current_user),
):
    """
    Évalue et persiste les *targets* pour un UserChallenge donné (best-effort).
    - Agrège les caches non trouvées qui satisfont ≥ 1 tâche du challenge.
    - Déduplique, calcule un score simple, persiste (upsert) dans `targets`.
    - Optionnel : filtre géographique pendant le calcul.
    """
    user_id = _current_user_id(current_user)
    uc_oid = _as_objid(uc_id)

    geo_ctx = None
    if include_geo_filter:
        # si lat/lon non fournis, tenter depuis le profil
        if lat is None or lon is None:
            loc = user_profile.user_location_get(user_id)
            if not loc:
                raise HTTPException(status_code=422, detail="No user location found; provide lat/lon or save your location first.")
            lon, lat = loc["coordinates"][0], loc["coordinates"][1]
        if radius_km is None:
            raise HTTPException(status_code=422, detail="radius_km is required when include_geo_filter=true.")
        geo_ctx = {"lat": float(lat), "lon": float(lon), "radius_km": float(radius_km)}

    result = evaluate_targets_for_user_challenge(
        user_id=user_id,
        uc_id=uc_oid,
        limit_per_task=int(limit_per_task),
        hard_limit_total=int(hard_limit_total),
        geo_ctx=geo_ctx,
        evaluated_at=utcnow(),
    )
    # result attendu: {"ok": True, "inserted": int, "updated": int, "total": int}
    return result


# ---------------------------
# Listing (per UserChallenge)
# ---------------------------

@router.get("/challenges/{uc_id}/targets")
def list_targets_uc(
    uc_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("-score", description="Ex: '-score', 'distance', 'GC'"),
    current_user=Depends(get_current_user),
):
    """
    Liste paginée des targets pour un UserChallenge donné.
    Retourne un dict: { items, total, page, limit }.
    """
    user_id = _current_user_id(current_user)
    uc_oid = _as_objid(uc_id)
    return list_targets_for_user_challenge(
        user_id=user_id, uc_id=uc_oid, page=int(page), limit=int(limit), sort=sort
    )


@router.get("/challenges/{uc_id}/targets/nearby")
def list_targets_uc_nearby(
    uc_id: str,
    radius_km: float = Query(50.0, gt=0),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("distance", description="Tri par défaut: distance"),
    current_user=Depends(get_current_user),
):
    """
    Liste paginée des targets d'un UserChallenge proches d'un point.
    Si lat/lon non fournis, utilise la localisation sauvegardée de l'utilisateur.
    """
    user_id = _current_user_id(current_user)
    uc_oid = _as_objid(uc_id)

    if lat is None or lon is None:
        loc = user_profile.user_location_get(user_id)
        if not loc:
            raise HTTPException(status_code=422, detail="No user location found; provide lat/lon or save your location first.")
        lon, lat = loc["coordinates"][0], loc["coordinates"][1]

    return list_targets_nearby_for_user_challenge(
        user_id=user_id,
        uc_id=uc_oid,
        lat=float(lat),
        lon=float(lon),
        radius_km=float(radius_km),
        page=int(page),
        limit=int(limit),
        sort=sort,
    )


# ---------------------------
# Global listing (all accepted challenges of the user)
# ---------------------------

@router.get("/targets")
def list_targets_all(
    status_filter: Optional[str] = Query(None, description="Filtrer les UC (ex: 'accepted')."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("-score", description="Ex: '-score', 'distance', 'GC'"),
    current_user=Depends(get_current_user),
):
    """
    Liste paginée des targets pour l'utilisateur sur l'ensemble de ses challenges (optionnellement filtrés par statut UC).
    """
    user_id = _current_user_id(current_user)
    return list_targets_for_user(
        user_id=user_id,
        status_filter=(status_filter or None),
        page=int(page),
        limit=int(limit),
        sort=sort,
    )


@router.get("/targets/nearby")
def list_targets_all_nearby(
    radius_km: float = Query(50.0, gt=0),
    lat: Optional[float] = Query(None, ge=-90, le=90),
    lon: Optional[float] = Query(None, ge=-180, le=180),
    status_filter: Optional[str] = Query(None, description="Filtrer les UC (ex: 'accepted')."),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    sort: str = Query("distance", description="Tri par défaut: distance"),
    current_user=Depends(get_current_user),
):
    """
    Liste paginée des targets proches d'un point, sur l'ensemble des challenges (optionnellement filtrés par statut UC).
    Si lat/lon non fournis, utilise la localisation sauvegardée de l'utilisateur.
    """
    user_id = _current_user_id(current_user)
    if lat is None or lon is None:
        loc = user_profile.user_location_get(user_id)
        if not loc:
            raise HTTPException(status_code=422, detail="No user location found; provide lat/lon or save your location first.")
        lon, lat = loc["coordinates"][0], loc["coordinates"][1]

    return list_targets_nearby_for_user(
        user_id=user_id,
        lat=float(lat),
        lon=float(lon),
        radius_km=float(radius_km),
        status_filter=(status_filter or None),
        page=int(page),
        limit=int(limit),
        sort=sort,
    )


# ---------------------------
# Maintenance
# ---------------------------

@router.delete("/challenges/{uc_id}/targets", status_code=status.HTTP_200_OK)
def clear_targets_uc(
    uc_id: str,
    current_user=Depends(get_current_user),
):
    """
    Supprime tous les targets liés au UserChallenge indiqué.
    """
    user_id = _current_user_id(current_user)
    uc_oid = _as_objid(uc_id)
    result = delete_targets_for_user_challenge(user_id=user_id, uc_id=uc_oid)
    # result attendu: {"ok": True, "deleted": n}
    return result
