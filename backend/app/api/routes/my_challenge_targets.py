# backend/app/api/routes/my_challenge_targets.py
# Routes "targets" : évaluation/rafraîchissement des cibles par challenge, listings paginés (globaux/proches), suppression.

from __future__ import annotations

from typing import Any

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status

from app.api.dto.target import TargetListResponse
from app.core.security import CurrentUserId, get_current_user
from app.core.utils import utcnow
from app.services.targets import (
    delete_targets_for_user_challenge,
    evaluate_targets_for_user_challenge,
    list_targets_for_user,
    list_targets_for_user_challenge,
    list_targets_nearby_for_user,
    list_targets_nearby_for_user_challenge,
)
from app.services.user_profile import user_location_get

router = APIRouter(prefix="/my", tags=["targets"], dependencies=[Depends(get_current_user)])


# ---------------------------
# Helpers
# ---------------------------


def _as_objid(v: Any) -> ObjectId:
    """Convertit une valeur en ObjectId (en conservant l’ObjectId s’il est déjà typé).

    Args:
        v (Any): Valeur à convertir.

    Returns:
        ObjectId: Identifiant MongoDB.
    """
    if isinstance(v, ObjectId):
        return v
    return ObjectId(str(v))


def _current_user_id(current_user: dict) -> ObjectId:
    """Extrait l’ObjectId de l’utilisateur courant ou lève 401 si absent.

    Args:
        current_user (dict): Utilisateur authentifié.

    Returns:
        ObjectId: Identifiant de l’utilisateur.
    """
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
    summary="Évaluer et persister les targets d’un UserChallenge",
    description=(
        "Calcule les **targets** pour un UserChallenge en agrégeant les caches non trouvées qui satisfont ≥1 tâche,\n"
        "déduplique, score, puis upsert en base.\n\n"
        "- Caps contrôlables (`limit_per_task`, `hard_limit_total`)\n"
        "- Filtre géographique optionnel (`include_geo_filter` + `lat`/`lon`/`radius_km`)\n"
        "- Option `force` pour recalculer même si des targets existent"
    ),
)
async def evaluate_targets(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="Identifiant du UserChallenge."),
    limit_per_task: int = Query(500, ge=1, le=5000, description="Cap de calcul par tâche."),
    hard_limit_total: int = Query(
        2000, ge=1, le=20000, description="Cap global avant fusion/score."
    ),
    include_geo_filter: bool = Query(
        False, description="Activer un filtre géographique pendant l’évaluation."
    ),
    lat: float | None = Query(
        None, ge=-90, le=90, description="Latitude pour filtre géo (si activé)."
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Longitude pour filtre géo (si activé)."
    ),
    radius_km: float | None = Query(
        None, gt=0, description="Rayon (km) requis si `include_geo_filter=true`."
    ),
    force: bool = Query(False, description="Forcer le recalcul même si des targets existent déjà."),
):
    """Évaluer et persister les targets d’un UserChallenge.

    Description:
        Construit la liste des caches cibles (targets) en fonction des tâches du challenge, applique un score, et
        enregistre le résultat. Peut restreindre l’évaluation à une zone géographique.

    Args:
        uc_id (str): Identifiant du UserChallenge.
        limit_per_task (int): Cap par tâche lors de l’évaluation.
        hard_limit_total (int): Cap global avant fusion/score.
        include_geo_filter (bool): Activer le filtre géographique.
        lat (float | None): Latitude si filtre géo.
        lon (float | None): Longitude si filtre géo.
        radius_km (float | None): Rayon (km) requis si filtre géo actif.
        force (bool): Recalcul même si des targets existent.

    Returns:
        dict: Compte-rendu `{ok, inserted, updated, total}`.
    """
    uc_oid = _as_objid(uc_id)

    geo_ctx = None
    if include_geo_filter:
        # si lat/lon non fournis, tenter depuis le profil
        if lat is None or lon is None:
            loc = await user_location_get(user_id)
            if not loc:
                raise HTTPException(
                    status_code=422,
                    detail="No user location found; provide lat/lon or save your location first.",
                )
            lon, lat = loc["coordinates"][0], loc["coordinates"][1]
        if radius_km is None:
            raise HTTPException(
                status_code=422,
                detail="radius_km is required when include_geo_filter=true.",
            )
        geo_ctx = {"lat": lat, "lon": lon, "radius_km": radius_km}

    result = await evaluate_targets_for_user_challenge(
        user_id=user_id,
        uc_id=uc_oid,
        limit_per_task=int(limit_per_task),
        hard_limit_total=int(hard_limit_total),
        geo_ctx=geo_ctx,
        evaluated_at=utcnow(),
        force=force,
    )
    # result attendu: {"ok": True, "inserted": int, "updated": int, "total": int}
    return result


# ---------------------------
# Listing (per UserChallenge)
# ---------------------------


@router.get(
    "/challenges/{uc_id}/targets",
    response_model=TargetListResponse,
    summary="Lister les targets d’un UserChallenge",
    description=(
        "Retourne la liste **paginée** des targets d’un UserChallenge.\n"
        "- Tri paramétrable (ex. `-score`, `distance`, `GC`)\n"
        "- Pagination `page`/`limit` (max 200)"
    ),
)
async def list_targets_uc(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="Identifiant du UserChallenge."),
    page: int = Query(1, ge=1, description="Numéro de page."),
    page_size: int = Query(50, ge=1, le=200, description="Taille de page (1–200)."),
    sort: str = Query("-score", description="Clé de tri (ex. '-score', 'distance', 'GC')."),
):
    """Lister les targets d’un UserChallenge (paginé).

    Description:
        Affiche les targets associées au UserChallenge avec pagination et tri.

    Args:
        uc_id (str): Identifiant du UserChallenge.
        page (int): Page (≥1).
        page_size (int): Taille de page (1–200).
        sort (str): Clé de tri.

    Returns:
        TargetListResponse: Items et pagination.
    """
    uc_oid = _as_objid(uc_id)
    return await list_targets_for_user_challenge(
        user_id=user_id, uc_id=uc_oid, page=page, page_size=page_size, sort=sort
    )


@router.get(
    "/challenges/{uc_id}/targets/nearby",
    response_model=TargetListResponse,
    summary="Lister les targets proches d’un point (par UC)",
    description=(
        "Liste **paginée** des targets d’un UserChallenge proches d’un point (`lat`/`lon`) dans un rayon (km).\n"
        "- Si `lat`/`lon` absents, utilise la **dernière localisation** enregistrée de l’utilisateur\n"
        "- Tri par défaut: `distance`"
    ),
)
async def list_targets_uc_nearby(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="Identifiant du UserChallenge."),
    radius_km: float = Query(50.0, gt=0, description="Rayon de recherche (km)."),
    lat: float | None = Query(
        None, ge=-90, le=90, description="Latitude ; sinon localisation enregistrée."
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Longitude ; sinon localisation enregistrée."
    ),
    page: int = Query(1, ge=1, description="Numéro de page."),
    page_size: int = Query(50, ge=1, le=200, description="Taille de page (1–200)."),
    sort: str = Query("distance", description="Clé de tri (défaut: 'distance')."),
):
    """Lister les targets proches d’un point (par UC).

    Description:
        Retourne les targets du UserChallenge situées à proximité d’un point, avec pagination et tri.

    Args:
        uc_id (str): Identifiant du UserChallenge.
        radius_km (float): Rayon (km).
        lat (float | None): Latitude ou localisation enregistrée.
        lon (float | None): Longitude ou localisation enregistrée.
        page (int): Page (≥1).
        page_size (int): Taille de page (1–200).
        sort (str): Clé de tri.

    Returns:
        TargetListResponse: Items et pagination.
    """
    uc_oid = _as_objid(uc_id)

    final_lat: float
    final_lon: float

    if lat is None or lon is None:
        loc = await user_location_get(user_id)
        if not loc:
            raise HTTPException(
                status_code=422,
                detail="No user location found; provide lat/lon or save your location first.",
            )
        final_lon, final_lat = loc["coordinates"][0], loc["coordinates"][1]
    else:
        final_lat = lat
        final_lon = lon

    return await list_targets_nearby_for_user_challenge(
        user_id=user_id,
        uc_id=uc_oid,
        lat=final_lat,
        lon=final_lon,
        radius_km=radius_km,
        page=int(page),
        page_size=int(page_size),
        sort=sort,
    )


# ---------------------------
# Global listing (all accepted challenges of the user)
# ---------------------------


@router.get(
    "/targets",
    response_model=TargetListResponse,
    summary="Lister toutes mes targets (tous challenges)",
    description=(
        "Liste **paginée** des targets sur l’ensemble des challenges de l’utilisateur.\n"
        "- Filtre optionnel `status_filter` (ex. 'accepted')\n"
        "- Tri (ex. `-score`, `distance`, `GC`)"
    ),
)
async def list_targets_all(
    user_id: CurrentUserId,
    status_filter: str | None = Query(None, description="Filtrer les UC (ex. 'accepted')."),
    page: int = Query(1, ge=1, description="Numéro de page."),
    page_size: int = Query(50, ge=1, le=200, description="Taille de page (1–200)."),
    sort: str = Query("-score", description="Clé de tri (ex. '-score', 'distance', 'GC')."),
):
    """Lister toutes mes targets (paginé).

    Description:
        Retourne les targets agrégées de tous les challenges de l’utilisateur, avec pagination et tri.

    Args:
        status_filter (str | None): Filtre de statut des UC.
        page (int): Page (≥1).
        page_size (int): Taille de page (1–200).
        sort (str): Clé de tri.

    Returns:
        TargetListResponse: Items et pagination.
    """
    return await list_targets_for_user(
        user_id=user_id,
        status_filter=(status_filter or None),
        page=int(page),
        page_size=int(page_size),
        sort=sort,
    )


@router.get(
    "/targets/nearby",
    response_model=TargetListResponse,
    summary="Lister les targets proches d’un point (tous challenges)",
    description=(
        "Liste **paginée** des targets proches d’un point (`lat`/`lon`) pour **tous** les challenges.\n"
        "- Si `lat`/`lon` absents, utilise la localisation enregistrée\n"
        "- Filtre de statut UC disponible (`status_filter`)"
    ),
)
async def list_targets_all_nearby(
    user_id: CurrentUserId,
    radius_km: float = Query(50.0, gt=0, description="Rayon (km)."),
    lat: float | None = Query(
        None, ge=-90, le=90, description="Latitude ; sinon localisation enregistrée."
    ),
    lon: float | None = Query(
        None, ge=-180, le=180, description="Longitude ; sinon localisation enregistrée."
    ),
    status_filter: str | None = Query(None, description="Filtrer les UC (ex. 'accepted')."),
    page: int = Query(1, ge=1, description="Numéro de page."),
    page_size: int = Query(50, ge=1, le=200, description="Taille de page (1–200)."),
    sort: str = Query("distance", description="Clé de tri (défaut: 'distance')."),
):
    """Lister les targets proches (tous challenges).

    Description:
        Agrège les targets à proximité d’un point pour l’ensemble des challenges de l’utilisateur.

    Args:
        radius_km (float): Rayon (km).
        lat (float | None): Latitude ou localisation enregistrée.
        lon (float | None): Longitude ou localisation enregistrée.
        status_filter (str | None): Filtre de statut UC.
        page (int): Page (≥1).
        page_size (int): Taille de page (1–200).
        sort (str): Clé de tri.

    Returns:
        TargetListResponse: Items et pagination.
    """
    final_lat: float
    final_lon: float

    if lat is None or lon is None:
        loc = await user_location_get(user_id)
        if not loc:
            raise HTTPException(
                status_code=422,
                detail="No user location found; provide lat/lon or save your location first.",
            )
        final_lon, final_lat = loc["coordinates"][0], loc["coordinates"][1]
    else:
        final_lat = lat
        final_lon = lon

    return await list_targets_nearby_for_user(
        user_id=user_id,
        lat=final_lat,
        lon=final_lon,
        radius_km=radius_km,
        status_filter=(status_filter or None),
        page=int(page),
        page_size=int(page_size),
        sort=sort,
    )


# ---------------------------
# Maintenance
# ---------------------------


@router.delete(
    "/challenges/{uc_id}/targets",
    status_code=status.HTTP_200_OK,
    summary="Supprimer toutes les targets d’un UserChallenge",
    description="Efface toutes les targets associées au UserChallenge fourni.",
)
async def clear_targets_uc(
    user_id: CurrentUserId,
    uc_id: str = Path(..., description="Identifiant du UserChallenge."),
):
    """Supprimer les targets d’un UserChallenge.

    Description:
        Supprime l’ensemble des targets rattachées au UserChallenge pour l’utilisateur courant.

    Args:
        uc_id (str): Identifiant du UserChallenge.

    Returns:
        dict: Résultat `{ok, deleted}`.
    """
    uc_oid = _as_objid(uc_id)
    result = await delete_targets_for_user_challenge(user_id=user_id, uc_id=uc_oid)
    # result attendu: {"ok": True, "deleted": n}
    return result
