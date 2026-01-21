# backend/app/api/routes/my_profile.py
# Routes "mon profil" : lecture/écriture de la localisation utilisateur (coordonnées ou expression textuelle).

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.api.dto.user_profile import UserLocationIn, UserLocationOut
from app.core.security import CurrentUser, CurrentUserId, get_current_user
from app.db.mongodb import db
from app.domain.models.user import UserOut
from app.services.user_profile_service import UserProfileService

router = APIRouter(
    prefix="/my/profile", tags=["my_profile"], dependencies=[Depends(get_current_user)]
)

# --- ROUTES ---------------------------------------------------------------


@router.put(
    "/location",
    status_code=status.HTTP_200_OK,
    summary="Enregistrer ou mettre à jour ma localisation",
    description=(
        "Enregistre la localisation de l’utilisateur **au choix** :\n"
        "- **Position textuelle** (`position`, ex. coordonnées DM)\n"
        "- **Coordonnées numériques** (`lat`, `lon`)\n\n"
        "Valide l’input et renvoie un message indiquant si une mise à jour a eu lieu."
    ),
)
async def put_my_location(
    payload: Annotated[
        UserLocationIn,
        Body(..., description="Localisation sous forme de `position` (texte) ou `lat`/`lon`."),
    ],
    user_id: CurrentUserId,
):
    """Enregistrer ou mettre à jour la localisation.

    Description:
        Sauvegarde la localisation via parsing d’une chaîne (`position`) ou directement via `lat`/`lon`.
        Valide les bornes géographiques et renvoie un message d’état.

    Args:
        payload (UserLocationIn): Position textuelle ou coordonnées numériques.

    Returns:
        dict: Message d’état (modifiée ou non).
    """
    # Utiliser le service pour gérer la localisation
    user_profile_service = UserProfileService(db)

    try:
        await user_profile_service.set_user_location(user_id, payload)
        updated = True
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if updated:
        return {"message": "Location updated successfully"}
    return {"message": "No change (same location)"}


@router.get(
    "/location",
    response_model=UserLocationOut,
    summary="Obtenir ma dernière localisation",
    description="Retourne la **dernière localisation** enregistrée (lat/lon, format DM, date de mise à jour).",
)
async def get_my_location(user_id: CurrentUserId):
    """Obtenir ma dernière localisation.

    Description:
        Récupère la dernière localisation sauvegardée pour l'utilisateur courant. Renvoie 404 si aucune n'existe.

    Returns:
        UserLocationOut: Coordonnées, représentation en degrés/minutes, et timestamp de mise à jour.
    """
    user_profile_service = UserProfileService(db)

    location_data = await user_profile_service.get_user_location_formatted(user_id)

    if location_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No location found for this user.",
        )

    return location_data


@router.get(
    "",
    response_model=UserOut,
    summary="Obtenir mon profil",
    description="Retourne le profil de l'utilisateur courant.",
)
async def get_my_profile(user: CurrentUser):
    """Obtenir mon profil.

    Description:
        Récupère le profil pour l’utilisateur courant.

    Args:

    Returns:
        UserLocationOut: Coordonnées, représentation en degrés/minutes, et timestamp de mise à jour.
    """

    return user
