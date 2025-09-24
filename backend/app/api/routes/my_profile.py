# backend/app/api/routes/my_profile.py
# Routes "mon profil" : lecture/écriture de la localisation utilisateur (coordonnées ou expression textuelle).

from typing import Annotated

from bson import ObjectId
from fastapi import APIRouter, Body, Depends, HTTPException, status

from app.core.security import get_current_user, get_current_user_id
from app.models.user_profile_dto import UserLocationIn, UserLocationOut
from app.services.user_profile import (
    coords_in_deg_min_mil,
    location_parse_to_lon_lat,
    user_location_get,
    user_location_set,
)

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
def put_my_location(
    payload: Annotated[
        UserLocationIn,
        Body(..., description="Localisation sous forme de `position` (texte) ou `lat`/`lon`."),
    ],
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
    user_id = get_current_user_id()

    # Choix de la source : position string > lat/lon
    if payload.position:
        try:
            lon, lat = location_parse_to_lon_lat(payload.position)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e)) from e
    else:
        if payload.lat is None or payload.lon is None:
            raise HTTPException(
                status_code=422,
                detail="Provide either 'position' or both 'lat' and 'lon'.",
            )
        lat, lon = float(payload.lat), float(payload.lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise HTTPException(status_code=422, detail="Coordinates out of range.")

    result = user_location_set(user_id=user_id, lon=lon, lat=lat)
    if result.modified_count > 0:
        return {"message": "Location updated successfully"}
    else:
        return {"message": "Location was not updated"}


@router.get(
    "/location",
    response_model=UserLocationOut,
    summary="Obtenir ma dernière localisation",
    description="Retourne la **dernière localisation** enregistrée (lat/lon, format DM, date de mise à jour).",
)
def get_my_location():
    """Obtenir ma dernière localisation.

    Description:
        Récupère la dernière localisation sauvegardée pour l’utilisateur courant. Renvoie 404 si aucune n’existe.

    Args:

    Returns:
        UserLocationOut: Coordonnées, représentation en degrés/minutes, et timestamp de mise à jour.
    """

    current_user = get_current_user()
    user_id = (
        current_user["_id"]
        if isinstance(current_user.get("_id"), ObjectId)
        else ObjectId(str(current_user["_id"]))
    )
    loc = user_location_get(user_id)
    if not loc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No location saved for this user.",
        )

    lat = loc["coordinates"][1]
    lon = loc["coordinates"][0]
    return UserLocationOut(
        lat=lat,
        lon=lon,
        coords=coords_in_deg_min_mil(lat, lon),
        updated_at=loc.get("updated_at"),
    )
