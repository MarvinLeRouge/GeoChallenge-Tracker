# backend/app/api/routes/caches_elevation.py
# Routes admin pour enrichir les caches avec l'altitude (appel fournisseur externe).

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.security import get_current_user, require_admin
from app.db.mongodb import get_collection
from app.domain.models.user import User
from app.services.elevation_retrieval import fetch as fetch_elevations

router = APIRouter(
    prefix="/caches_elevation",
    tags=["caches_elevation"],
    dependencies=[Depends(get_current_user)],
)


@router.post(
    "/caches/elevation/backfill",
    summary="Backfill de l’altitude manquante (admin)",
    description=(
        "Complète l’altitude des caches dépourvues de valeur, par lots, en respectant les quotas du fournisseur.\n\n"
        "- Parcours paginé de la collection\n"
        "- Mode `dry_run` pour simuler sans écrire en base\n"
        "- Réservé aux administrateurs"
    ),
)
async def backfill_elevation(
    admin: Annotated[User, Depends(require_admin)],
    limit: int = Query(1000, ge=1, le=20000, description="Nombre maximum de caches à traiter."),
    page_size: int = Query(
        500, ge=10, le=1000, description="Taille de lot pour les lectures/écritures."
    ),
    dry_run: bool = Query(
        False, description="Si vrai, ne persiste pas les mises à jour (simulation)."
    ),
):
    """Backfill d’altitude (admin).

    Description:
        Sélectionne les caches sans altitude (mais avec lat/lon valides), récupère l’altitude via un provider externe
        et applique des mises à jour par lots. Peut fonctionner en mode simulation.

    Args:
        limit (int): Nombre maximum de caches à traiter.
        page_size (int): Taille des lots.
        dry_run (bool): Si vrai, exécute sans écrire en base.

    Returns:
        dict: Statistiques de traitement (scanned, updated, failed, batches, requests_used, dry_run).
    """

    coll = await get_collection("caches")

    # Build cursor for missing elevation but with valid lat/lon
    filt = {
        "$and": [
            {"$or": [{"elevation": {"$exists": False}}, {"elevation": None}]},
            {"lat": {"$ne": None}},
            {"lon": {"$ne": None}},
        ]
    }

    scanned = updated = failed = requests_used = 0
    batches = 0
    docs_buffer: list[dict] = []

    while scanned < limit:
        cursor = (
            coll.find(filt, {"_id": 1, "lat": 1, "lon": 1})
            .skip(scanned)
            .limit(min(page_size, limit - scanned))
        )
        docs_buffer = await cursor.to_list(length=page_size)

        if not docs_buffer:
            break
        batches += 1
        scanned += len(docs_buffer)

        if dry_run:
            # simulate work but do not write
            requests_used += 1
            continue

        pts = [(float(d["lat"]), float(d["lon"])) for d in docs_buffer]
        elevs = await fetch_elevations(pts)

        # Apply updates in bulk
        ops = []
        for d, ev in zip(docs_buffer, elevs):
            if ev is None:
                failed += 1
                continue
            ops.append(
                {
                    "filter": {"_id": d["_id"]},
                    "update": {"$set": {"elevation": int(ev)}},
                }
            )

        if ops:
            # manual bulk since we can't import UpdateOne here safely in routes
            bulk_ops = []
            from pymongo import UpdateOne

            for op in ops:
                bulk_ops.append(UpdateOne(op["filter"], op["update"]))
            await coll.bulk_write(bulk_ops, ordered=False)
            updated += len(bulk_ops)

        # simple estimate of requests used: provider increments in its own quota; we expose batches as proxy
        requests_used += 1

    return {
        "scanned": scanned,
        "updated": updated,
        "failed": failed,
        "batches": batches,
        "requests_used": requests_used,
        "dry_run": dry_run,
    }
