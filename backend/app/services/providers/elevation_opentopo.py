# backend/app/services/providers/elevation_opentopo.py
# Provider OpenTopoData/Mapzen : récupération d’altitudes, découpage des requêtes (URL/compte),
# respect du quota quotidien via la collection `api_quotas`, et rate limiting côté client.

from __future__ import annotations
from typing import List, Optional, Tuple
import os
import asyncio
import datetime as dt
import httpx

from app.db.mongodb import get_collection
from app.core.settings import settings
from app.core.utils import *

# Config
ENDPOINT = settings.elevation_provider_endpoint
MAX_POINTS_PER_REQ = settings.elevation_provider_max_points_per_req
RATE_DELAY_S = settings.elevation_provider_rate_delay_s
URL_MAXLEN = 1800
ENABLED = settings.elevation_enabled

# Quota
PROVIDER_KEY = "opentopodata_mapzen"

def _quota_key_for_today() -> str:
    """Clé de quota journalière pour le provider.

    Description:
        Construit une clé unique pour la journée courante en UTC (via `utcnow()`),
        sous la forme `"opentopodata_mapzen:YYYY-MM-DD"`. Sert d’identifiant de
        document dans la collection `api_quotas`.

    Args:
        None

    Returns:
        str: Clé de quota du jour (ex. "opentopodata_mapzen:2025-08-27").
    """
    today = utcnow().date().isoformat()
    return f"{PROVIDER_KEY}:{today}"

def _read_quota() -> int:
    """Lire le compteur de requêtes du jour.

    Description:
        Lit le document `api_quotas[_id=_quota_key_for_today()]` et retourne le champ
        `count` s’il est présent ; sinon 0. Ce compteur représente le **nombre de requêtes
        HTTP** déjà effectuées vers le provider ce jour-là.

    Args:
        None

    Returns:
        int: Compteur courant de requêtes (≥ 0).
    """
    doc = get_collection("api_quotas").find_one({"_id": _quota_key_for_today()})
    return int(doc["count"]) if doc and "count" in doc else 0

def _inc_quota(n: int) -> None:
    """Incrémenter le compteur de quota du jour.

    Description:
        Applique un `update_one(..., {"$inc": {"count": int(n)}, "$setOnInsert": {"created_at": utcnow()}}, upsert=True)`
        sur `api_quotas` pour la clé journalière. Utilisé après **chaque** appel HTTP.

    Args:
        n (int): Nombre de requêtes à ajouter (converti en int).

    Returns:
        None
    """
    get_collection("api_quotas").update_one(
        {"_id": _quota_key_for_today()},
        {"$inc": {"count": int(n)}, "$setOnInsert": {"created_at": utcnow()}},
        upsert=True,
    )

def _build_param(points: List[tuple[float, float]]) -> str:
    """Construire le paramètre `locations` de l’API.

    Description:
        Sérialise la liste de points `(lat, lon)` au format attendu par l’API :
        `"lat,lon|lat,lon|..."`.

    Args:
        points (list[tuple[float, float]]): Coordonnées (latitude, longitude).

    Returns:
        str: Chaîne `locations` prête à concaténer dans l’URL.
    """
    return "|".join(f"{lat},{lon}" for (lat, lon) in points)

def _split_params_by_url_and_count(all_param: str) -> List[str]:
    """Découper `locations` en fragments compatibles URL et quota par requête.

    Description:
        Divise la grande chaîne `locations` en **morceaux** respectant :
        - la longueur maximale d’URL (~`URL_MAXLEN`) en tenant compte du préfixe `?locations=`
        - la limite `MAX_POINTS_PER_REQ` (nombre de points par appel)
        
        Heuristique :
        - coupe par la dernière barre verticale `|` pour ne pas séparer un couple lat/lon ;
        - si un fragment dépasse la limite de points, tronque au **nombre permis** et
          réinjecte l’excédent au début du reste.

    Args:
        all_param (str): Chaîne `locations` globale construite par `_build_param`.

    Returns:
        list[str]: Liste de fragments `locations` à appeler séquentiellement.
    """
    prefix_len = len(f"{ENDPOINT}?locations=")
    max_param_len = max(1, URL_MAXLEN - prefix_len)

    chunks: List[str] = []
    remaining = all_param
    while remaining:
        # take max slice by URL size
        take = remaining[:max_param_len]
        if len(take) == len(remaining):
            chunk = take
            remaining = ""
        else:
            # cut back to last '|' so we don't split a coordinate
            cut = take.rfind("|")
            if cut == -1:
                # no '|' found -> single coordinate longer than max? take it anyway
                chunk = take
                remaining = remaining[len(take):]
            else:
                chunk = take[:cut]
                remaining = remaining[cut+1:]  # drop the '|'

        # enforce MAX_POINTS_PER_REQ
        # number of points = number of pipes + 1 (unless chunk empty)
        if chunk:
            pipes = chunk.count("|")
            if pipes >= MAX_POINTS_PER_REQ:
                # keep only first MAX_POINTS_PER_REQ points (=> MAX_POINTS_PER_REQ-1 pipes)
                # find the index of the (MAX_POINTS_PER_REQ-1)-th '|' (0-based)
                keep_pipes = MAX_POINTS_PER_REQ - 1
                idx = -1
                count = 0
                for i, ch in enumerate(chunk):
                    if ch == "|":
                        count += 1
                        if count == keep_pipes:
                            idx = i
                            break
                if idx != -1:
                    extra = chunk[idx+1:]
                    chunk = chunk[:idx]
                    # prepend overflow back to remaining (with a '|' if needed)
                    remaining = (extra + ("|" + remaining if remaining else "")).lstrip("|")

        chunks.append(chunk)
    return [c for c in chunks if c]

async def fetch(points: List[tuple[float, float]]) -> List[Optional[int]]:
    """Récupérer les altitudes pour une liste de points (alignées sur l’entrée).

    Description:
        - Si le provider est désactivé (`settings.elevation_enabled=False`) **ou** si la liste
          `points` est vide, retourne une liste de `None` de même taille.
        - Respecte un **quota quotidien** en nombre d’appels HTTP, basé sur la collection
          `api_quotas` et la variable d’environnement `ELEVATION_DAILY_LIMIT` (défaut 1000).
          Si le quota est atteint, retourne des `None` pour les points restants.
        - Construit une chaîne `locations` puis la **découpe** via `_split_params_by_url_and_count`
          en respectant `URL_MAXLEN` et `MAX_POINTS_PER_REQ`.
        - Pour chaque fragment :
            * effectue un `GET` sur `ENDPOINT?locations=...` (timeout configurable par
              `ELEVATION_TIMEOUT_S`, défaut "5.0")
            * parse la réponse JSON et extrait `results[*].elevation`
            * mappe chaque altitude (arrondie à l’entier) au **bon index d’origine**
            * en cas d’erreur HTTP/JSON, laisse les valeurs correspondantes à `None`
            * incrémente le quota et respecte un **rate delay** (`RATE_DELAY_S`) entre appels
              (sauf après le dernier)
        - Ne lève **jamais** d’exception ; toute erreur réseau/parse entraîne des `None` localisés.

    Args:
        points (list[tuple[float, float]]): Liste `(lat, lon)` pour lesquelles obtenir l’altitude.

    Returns:
        list[Optional[int]]: Liste des altitudes en mètres (ou `None` sur échec), **alignée** sur `points`.
    """
    if not ENABLED or not points:
        return [None] * len(points)

    # Respect daily quota (1000 calls/day), counting *requests*, not points
    daily_count = _read_quota()
    DAILY_LIMIT = int(os.getenv("ELEVATION_DAILY_LIMIT", "1000"))
    if daily_count >= DAILY_LIMIT:
        return [None] * len(points)

    # We keep a parallel index list to map back results to original points
    # Build one big param string then split smartly
    param_all = _build_param(points)
    param_chunks = _split_params_by_url_and_count(param_all)

    results: List[Optional[int]] = [None] * len(points)
    # We need to also split the original points list in the same way to keep indices aligned.
    # We'll reconstruct chunk-wise indices by counting commas/pipes.
    idx_start = 0
    async with httpx.AsyncClient(timeout=float(os.getenv("ELEVATION_TIMEOUT_S", "5.0"))) as client:
        for i, param in enumerate(param_chunks):
            # Determine how many points are in this chunk
            n_pts = 1 if param and "|" not in param else (param.count("|") + 1 if param else 0)
            pts_slice = points[idx_start: idx_start + n_pts]

            # Quota guard: stop if next request would exceed
            if daily_count >= DAILY_LIMIT:
                break

            url = f"{ENDPOINT}?locations={param}"
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json() or {}
                    arr = data.get("results") or []
                    for j, rec in enumerate(arr[:n_pts]):
                        elev = rec.get("elevation", None)
                        if isinstance(elev, (int, float)):
                            results[idx_start + j] = int(round(elev))
                        else:
                            results[idx_start + j] = None
                else:
                    # leave None for this slice
                    pass
            except Exception:
                # leave None for this slice
                pass

            # update quota & delay
            daily_count += 1
            _inc_quota(1)
            idx_start += n_pts

            # Rate-limit (skip after the last chunk)
            if i < len(param_chunks) - 1:
                await asyncio.sleep(RATE_DELAY_S)

    return results
