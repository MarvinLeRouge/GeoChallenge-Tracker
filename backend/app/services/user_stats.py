# backend/app/services/user_stats.py
# Service pour calculer les statistiques synthétiques d'un utilisateur

from typing import Optional

from bson import ObjectId
from pymongo import ASCENDING, DESCENDING

from app.api.dto.user_stats import UserStatsOut
from app.db.mongodb import get_collection


async def get_user_stats(user_id: ObjectId, target_username: Optional[str] = None) -> UserStatsOut:
    """Calculer les statistiques synthétiques d'un utilisateur.

    Description:
        Récupère les statistiques pour l'utilisateur courant ou un autre utilisateur
        (si target_username fourni et utilisateur courant admin).
        Réutilise les collections existantes pour calculer les métriques.

    Args:
        user_id (ObjectId): Identifiant de l'utilisateur courant.
        target_username (str | None): Username cible (nécessite droits admin).

    Returns:
        UserStatsOut: Statistiques calculées.

    Raises:
        PermissionError: Si target_username fourni sans droits admin.
        ValueError: Si target_username non trouvé.
    """
    users_coll = await get_collection("users")

    # Déterminer l'utilisateur cible
    if target_username:
        # Vérifier que l'utilisateur courant est admin
        current_user = await users_coll.find_one({"_id": user_id}, {"role": 1})
        if not current_user or current_user.get("role") != "admin":
            raise PermissionError("Admin rights required to view other users' stats")

        # Récupérer l'utilisateur cible
        target_user = await users_coll.find_one({"username": target_username})
        if not target_user:
            raise ValueError(f"User '{target_username}' not found")

        target_user_id = target_user["_id"]
        username = target_user["username"]
        created_at = target_user["created_at"]
    else:
        # Utilisateur courant
        current_user = await users_coll.find_one({"_id": user_id})
        if not current_user:
            raise ValueError("Current user not found")

        target_user_id = user_id
        username = current_user["username"]
        created_at = current_user["created_at"]

    # Calculer le nombre total de caches trouvées
    found_caches_coll = await get_collection("found_caches")
    total_caches_found = await found_caches_coll.count_documents({"user_id": target_user_id})

    # Dates de première et dernière cache trouvée
    first_cache = await found_caches_coll.find_one(
        {"user_id": target_user_id}, sort=[("found_date", ASCENDING)]
    )
    first_cache_found_at = first_cache["found_date"] if first_cache else None

    last_cache = await found_caches_coll.find_one(
        {"user_id": target_user_id}, sort=[("found_date", DESCENDING)]
    )
    last_cache_found_at = last_cache["found_date"] if last_cache else None

    # Statistiques des challenges
    user_challenges_coll = await get_collection("user_challenges")

    # Nombre total de challenges
    total_challenges = await user_challenges_coll.count_documents({"user_id": target_user_id})

    # Challenges actifs (status: accepted)
    active_challenges = await user_challenges_coll.count_documents(
        {"user_id": target_user_id, "status": "accepted"}
    )

    # Challenges terminés (status: completed OU computed_status: completed)
    completed_challenges = await user_challenges_coll.count_documents(
        {
            "user_id": target_user_id,
            "$or": [{"status": "completed"}, {"computed_status": "completed"}],
        }
    )

    # Dernière activité : max entre dernière cache trouvée et dernier challenge créé
    last_challenge = await user_challenges_coll.find_one(
        {"user_id": target_user_id}, sort=[("created_at", DESCENDING)]
    )
    last_challenge_created = last_challenge["created_at"] if last_challenge else None

    # Calculer last_activity_at
    last_activity_candidates = [
        dt for dt in [last_cache_found_at, last_challenge_created] if dt is not None
    ]
    last_activity_at = max(last_activity_candidates) if last_activity_candidates else None

    return UserStatsOut(
        user_id=target_user_id,
        username=username,
        total_caches_found=total_caches_found,
        total_challenges=total_challenges,
        active_challenges=active_challenges,
        completed_challenges=completed_challenges,
        first_cache_found_at=first_cache_found_at,
        last_cache_found_at=last_cache_found_at,
        created_at=created_at,
        last_activity_at=last_activity_at,
    )


async def get_user_by_username(username: str) -> Optional[dict]:
    """Récupérer un utilisateur par son username.

    Args:
        username (str): Nom d'utilisateur.

    Returns:
        dict | None: Document utilisateur ou None si non trouvé.
    """
    users_coll = await get_collection("users")
    return await users_coll.find_one({"username": username})
