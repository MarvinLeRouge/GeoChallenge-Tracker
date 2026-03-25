# backend/app/api/routes/my_profile.py
# "My profile" routes: read/write user location (coordinates or textual expression).

from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status

from app.api.deps import CurrentUser, CurrentUserId
from app.api.dto.user_profile import UserLocationIn, UserLocationOut
from app.api.dto.user_stats import UserStatsOut
from app.core.security import get_current_user
from app.db.mongodb import get_db
from app.domain.models.user import UserOut
from app.services.found_caches_sync import extract_gc_codes, sync_found_caches
from app.services.user_profile_service import UserProfileService
from app.services.user_stats import get_user_stats

router = APIRouter(
    prefix="/my/profile", tags=["My profile"], dependencies=[Depends(get_current_user)]
)

# --- ROUTES ---------------------------------------------------------------


# TODO: [BACKLOG] Route /my/profile/location (PUT) to verify
@router.put(
    "/location",
    status_code=status.HTTP_200_OK,
    summary="Save or update my location",
    description=(
        "Saves the user’s location using **either**:\n"
        "- **Textual position** (`position`, e.g. DM coordinates)\n"
        "- **Numeric coordinates** (`lat`, `lon`)\n\n"
        "Validates the input and returns a message indicating whether an update occurred."
    ),
)
async def put_my_location(
    payload: Annotated[
        UserLocationIn,
        Body(..., description="Location as a `position` string (text) or `lat`/`lon` numbers."),
    ],
    user_id: CurrentUserId,
):
    """Save or update location.

    Description:
        Saves the location by parsing a string (`position`) or directly via `lat`/`lon`.
        Validates geographic bounds and returns a status message.

    Args:
        payload (UserLocationIn): Textual position or numeric coordinates.

    Returns:
        dict: Status message (updated or unchanged).
    """
    # Use the service to handle location
    db = get_db()
    user_profile_service = UserProfileService(db)

    try:
        await user_profile_service.set_user_location(user_id, payload)
        updated = True
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    if updated:
        return {"message": "Location updated successfully"}
    return {"message": "No change (same location)"}


# TODO: [BACKLOG] Route /my/profile/location (GET) to verify
@router.get(
    "/location",
    response_model=UserLocationOut,
    summary="Get my last saved location",
    description="Returns the **last saved location** (lat/lon, DM format, update timestamp).",
)
async def get_my_location(user_id: CurrentUserId):
    """Get my last saved location.

    Description:
        Retrieves the last saved location for the current user. Returns 404 if none exists.

    Returns:
        UserLocationOut: Coordinates, degrees/minutes representation, and update timestamp.
    """
    db = get_db()
    user_profile_service = UserProfileService(db)

    location_data = await user_profile_service.get_user_location_formatted(user_id)

    if location_data is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No location found for this user.",
        )

    return location_data


@router.post(
    "/found-caches/sync",
    status_code=status.HTTP_200_OK,
    summary="Sync found caches from a text file",
    description=(
        "Uploads a plain-text file and extracts every GC code it contains.\n\n"
        "The extracted list is treated as the **complete and authoritative** found-cache list "
        "for the current user:\n"
        "- Found caches **not in the list** are deleted.\n"
        "- GC codes **not yet in found caches** are inserted.\n"
        "- GC codes not matched to any known cache are reported as `unknown_gc_codes`."
    ),
)
async def sync_my_found_caches(
    user_id: CurrentUserId,
    file: Annotated[UploadFile, File(..., description="Plain-text file containing GC codes.")],
):
    """Sync found caches from a canonical text file.

    Args:
        file (UploadFile): Text file whose content will be scanned for GC codes.

    Returns:
        dict: {nb_provided, nb_deleted, nb_added, nb_unknown_gc, unknown_gc_codes}.
    """
    content = await file.read()
    await file.close()

    try:
        text = content.decode("utf-8", errors="replace")
    except Exception as err:
        raise HTTPException(status_code=400, detail="Unable to decode file content.") from err

    gc_codes = extract_gc_codes(text)
    db = get_db()
    return await sync_found_caches(db=db, user_id=user_id, gc_codes=gc_codes)


@router.get(
    "/stats",
    response_model=UserStatsOut,
    summary="Get my statistics",
    description="Returns summary statistics for the current user.",
)
async def get_my_stats(user_id: CurrentUserId) -> UserStatsOut:
    """Get statistics for the current user.

    Returns:
        UserStatsOut: Computed statistics.
    """
    try:
        return await get_user_stats(user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e


# TODO: [BACKLOG] Route /my/profile (GET) to verify
@router.get(
    "",
    response_model=UserOut,
    summary="Get my profile",
    description="Returns the profile of the current user.",
)
async def get_my_profile(user: CurrentUser):
    """Get my profile.

    Description:
        Retrieves the profile for the current user.

    Args:

    Returns:
        UserOut: Public user profile data.
    """

    return user
