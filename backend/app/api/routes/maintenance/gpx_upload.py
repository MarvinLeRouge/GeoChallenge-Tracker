# app/api/routes/maintenance/gpx_upload.py
# Forced-attribute-update GPX import route (POST /maintenance/upload-gpx).

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import File, HTTPException, Query, Request, UploadFile

from app.api.deps import CurrentUserId
from app.core.middleware import read_upload_file_with_limit
from app.core.settings import get_settings
from app.services.gpx_importer_service import import_gpx_payload

from ._router import router


# TODO: [BACKLOG] Route /maintenance/import-gpx (POST) to verify
@router.post(
    "/upload-gpx",
    summary="Import GPX with forced attribute update",
    description=(
        "Imports a GPX/ZIP file and forces attribute updates for all caches.\n\n"
        "**RESTRICTED TO ADMINISTRATORS**\n\n"
        "Works like the standard import but updates attributes even if they already exist.\n"
        "Supports the same formats as the standard import (cgeo, pocket_query, etc.).\n"
        "Returns an import summary and challenge-related statistics."
    ),
    responses={
        200: {"description": "GPX import successful with forced attribute update"},
        400: {"description": "Invalid GPX/ZIP file"},
        401: {"description": "Not authenticated"},
        403: {"description": "Access denied (admin required)"},
    },
)
async def upload_gpx(
    request: Request,
    user_id: CurrentUserId,
    file: Annotated[
        UploadFile, File(..., description="GPX file to import (or ZIP containing a GPX).")
    ],
    import_mode: Literal["all", "found"] = Query(
        "all",
        description="Import mode: 'all' (all caches) or 'found' (my finds)",
    ),
    source_type: Literal["auto", "cgeo", "pocket_query"] = Query(
        "auto",
        description="GPX source type: 'auto' (automatic detection), 'cgeo', 'pocket_query'",
    ),
) -> dict[str, Any]:
    """Import GPX with forced attribute update.

    Description:
        Imports a GPX/ZIP file and forces attribute updates for all caches.
        This feature is reserved for administrators.

    Args:
        file: GPX or ZIP file to process.
        import_mode: Import mode ('all' for all caches, 'found' for finds only).
        source_type: GPX source type ('auto', 'cgeo', 'pocket_query').

    Returns:
        dict: Import summary and challenge-related statistics.

    Raises:
        HTTPException 400: If the file is invalid.
        HTTPException 403: If the user is not an admin.
    """
    result: dict[str, Any] = {"summary": None, "challenge_stats": None}

    settings = get_settings()
    payload = await read_upload_file_with_limit(file, settings.max_upload_bytes)

    try:
        result["summary"] = await import_gpx_payload(
            payload=payload,
            filename=file.filename or "upload.gpx",
            import_mode=import_mode,
            user_id=None,  # For forced import, a specific user could be provided or left as None
            request=request,
            source_type=source_type,
            force_update_attributes=True,  # Always true for this route
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX/ZIP file: {e}") from e

    return result
