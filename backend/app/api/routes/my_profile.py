# app/api/routes/my_profile.py
from fastapi import APIRouter, Depends, HTTPException, status
from bson import ObjectId

from app.core.security import get_current_user
from app.core.utils import *
from app.models.user_profile_dto import UserLocationIn, UserLocationOut
from app.services.user_profile import *

router = APIRouter(prefix="/my/profile", tags=["my_profile"])

# --- ROUTES ---------------------------------------------------------------

@router.put("/location", status_code=status.HTTP_200_OK)
def put_my_location(
    payload: UserLocationIn,
    current_user=Depends(get_current_user),
):
    """
    Enregistre / met à jour la localisation de l'utilisateur courant.
    Accepte:
      - lat/lon numériques
      - ou position string en DD / DM / DMS, avec ° ' " optionnels, N/S/E/W optionnels,
        virgule décimale tolérée.
    """
    user_id = current_user["_id"] if isinstance(current_user.get("_id"), ObjectId) else ObjectId(str(current_user["_id"]))

    # Choix de la source : position string > lat/lon
    if payload.position:
        try:
            lon, lat = location_parse_to_lon_lat(payload.position)
        except ValueError as e:
            raise HTTPException(status_code=422, detail=str(e))
    else:
        if payload.lat is None or payload.lon is None:
            raise HTTPException(status_code=422, detail="Provide either 'position' or both 'lat' and 'lon'.")
        lat, lon = float(payload.lat), float(payload.lon)
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise HTTPException(status_code=422, detail="Coordinates out of range.")

    result = user_location_set(
        user_id=user_id,
        lon=lon,
        lat=lat
    )
    if result.modified_count > 0:
        return {"message": "Location updated successfully"}
    else:
        return {"message": "Location was not updated"}


@router.get("/location", response_model=UserLocationOut)
def get_my_location(current_user=Depends(get_current_user)):
    """
    Retourne la dernière localisation enregistrée de l'utilisateur.
    404 si aucune localisation n'est connue.
    """
    user_id = current_user["_id"] if isinstance(current_user.get("_id"), ObjectId) else ObjectId(str(current_user["_id"]))
    loc = user_location_get(user_id)
    if not loc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No location saved for this user.")
    
    lat = loc["coordinates"][1]
    lon = loc["coordinates"][0]
    return UserLocationOut(
        lat=lat,
        lon=lon,
        coords=coords_in_deg_min_mil(lat, lon),
        updated_at=loc.get("updated_at"),
    )
