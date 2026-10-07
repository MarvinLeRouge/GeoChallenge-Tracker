# backend/app/api/routes/caches.py
# Routes related to geocaches: GPX upload and import.

from __future__ import annotations

import asyncio
import logging
from typing import Annotated, Any, Literal

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile

from app.api.deps import CurrentUserId
from app.core.security import get_current_user
from app.core.settings import get_settings
from app.db.mongodb import get_collection
from app.services.challenge_autocreate import create_new_challenges_from_caches
from app.services.gpx_importer_service import import_gpx_payload
from app.services.progress import evaluate_progress
from app.services.user_challenges_service import sync_user_challenges

log = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/caches", tags=["Caches"], dependencies=[Depends(get_current_user)])


async def _read_upload_with_size_limit(file: UploadFile) -> bytes:
    """Stream-read an upload file, enforcing the configured size limit.

    Args:
        file (UploadFile): The uploaded file.

    Returns:
        bytes: The full file content.

    Raises:
        HTTPException: 413 if the content exceeds `settings.max_upload_bytes`.
    """
    read_bytes = 0
    chunks: list[bytes] = []
    while True:
        chunk = await file.read(settings.one_mb)
        if not chunk:
            break
        read_bytes += len(chunk)
        if read_bytes > settings.max_upload_bytes:
            # Important: close the file and return 413
            await file.close()
            raise HTTPException(
                status_code=413,
                detail=f"Fichier trop volumineux (>{settings.max_upload_mb} Mo).",
            )
        chunks.append(chunk)

    await file.close()
    return b"".join(chunks)


async def _import_gpx_or_raise(
    payload: bytes,
    filename: str | None,
    import_mode: str,
    user_id: ObjectId,
    request: Request,
    source_type: str,
) -> dict[str, Any]:
    """Import a GPX/ZIP payload, converting any failure to a 400 HTTPException.

    Args:
        payload (bytes): Raw file content.
        filename (str | None): Original filename, if any.
        import_mode (str): 'all' | 'found'.
        user_id (ObjectId): Importing user.
        request (Request): The current request (forwarded to the importer).
        source_type (str): 'auto' | 'cgeo' | 'pocket_query'.

    Returns:
        dict: Import summary.

    Raises:
        HTTPException: 400 on any import failure.
    """
    try:
        return await import_gpx_payload(
            payload=payload,
            filename=filename or "upload.gpx",
            import_mode=import_mode,
            user_id=user_id,
            request=request,
            source_type=source_type,
            force_update_attributes=False,  # Always False in the standard version
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX/ZIP: {e}") from e


async def _create_challenges_after_import() -> dict[str, Any]:
    """Create new challenges from newly imported caches, swallowing errors into the result.

    Returns:
        dict: Challenge creation stats, or `{"error": ...}` on failure.
    """
    try:
        # Simple variant (optimized global scan: only processes new challenge caches)
        return await create_new_challenges_from_caches()
        # Optimized variant if you have the list of imported cache _ids:
        # challenge_stats = create_new_challenges_from_caches(cache_ids=upserted_cache_ids)
    except Exception as e:
        return {"error": str(e)}


async def _sync_user_challenges_after_import(user_id: ObjectId) -> dict[str, Any]:
    """Sync the user's challenges after import, swallowing errors into the result.

    Args:
        user_id (ObjectId): Importing user.

    Returns:
        dict: Sync stats, or `{"error": ...}` on failure.
    """
    try:
        return await sync_user_challenges(user_id)
    except Exception as e:
        return {"error": str(e)}


async def _evaluate_progress_for_accepted_ucs(user_id: ObjectId) -> dict[str, Any]:
    """Re-evaluate progress for all of the user's accepted UserChallenges after a 'found' import.

    Args:
        user_id (ObjectId): Importing user.

    Returns:
        dict: `{"evaluated": int, "total": int}`, or `{"error": ...}` on failure.
    """
    try:
        coll_uc = await get_collection("user_challenges")
        accepted_docs = await coll_uc.find(
            {"user_id": user_id, "status": "accepted"},
            {"_id": 1},
        ).to_list(length=None)

        log.info("[progress] GPX found import — evaluating %d accepted UC(s)", len(accepted_docs))

        eval_results = await asyncio.gather(
            *(evaluate_progress(user_id, doc["_id"]) for doc in accepted_docs),
            return_exceptions=True,
        )

        evaluated = 0
        for doc, res in zip(accepted_docs, eval_results):
            uc_id_str = str(doc["_id"])
            if isinstance(res, BaseException):
                log.warning("[progress] UC %s — evaluation failed: %s", uc_id_str, res)
            else:
                pct = res.get("percent", "?")
                done = res.get("tasks_done", "?")
                total = res.get("tasks_total", "?")
                log.info("[progress] UC %s — %s%% (%s/%s tasks done)", uc_id_str, pct, done, total)
                evaluated += 1

        return {
            "evaluated": evaluated,
            "total": len(accepted_docs),
        }
    except Exception as e:
        log.exception("[progress] Unexpected error during post-import evaluation")
        return {"error": str(e)}


# DONE: [BACKLOG] Route /caches/upload-gpx (POST) verified
@router.post(
    "/upload-gpx",
    summary="Import caches from a GPX/ZIP file",
    description=(
        "Loads a GPX file (or a ZIP containing a GPX) and imports the associated geocaches.\n\n"
        "- Optionally marks caches as found (creates `found_caches` records)\n"
        "- Then attempts to auto-create challenges from the imported caches\n"
        f"- **Size limit**: {settings.max_upload_mb} MB\n"
        "- Supports multiple GPX formats (cgeo, pocket_query)\n"
        "- Returns an import summary and challenge-related statistics"
    ),
    responses={
        200: {"description": "GPX import successful"},
        400: {"description": "Invalid GPX/ZIP file"},
        401: {"description": "Unauthenticated"},
        413: {"description": "Payload too large"},
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
        description="Import mode: ‘all’ (all caches) or ‘found’ (my finds)",
    ),
    source_type: Literal["auto", "cgeo", "pocket_query"] = Query(
        "auto",
        description="GPX source type: ‘auto’ (auto-detect), ‘cgeo’, ‘pocket_query’",
    ),
):
    """Imports a GPX/ZIP file and triggers challenge creation.

    Description:
        Reads a GPX file (or a ZIP containing a GPX), imports the caches into the database,
        then triggers processing to auto-create challenges from the newly imported caches.

    Args:
        file (UploadFile): GPX or ZIP file to process.
        import_mode (str): Import mode - ‘all’ to import all caches, ‘found’ to mark as found.
        source_type (str): GPX file format - ‘auto’ for auto-detection, ‘cgeo’, or ‘pocket_query’.

    Returns:
        dict: Object containing the import summary (`summary`) and challenge-related statistics (`challenges_stats`).
    """
    payload = await _read_upload_with_size_limit(file)

    uid = ObjectId(str(user_id))
    result: dict[str, Any] = {}
    result["summary"] = await _import_gpx_or_raise(
        payload, file.filename, import_mode, uid, request, source_type
    )

    result["challenges_stats"] = await _create_challenges_after_import()
    result["sync_stats"] = await _sync_user_challenges_after_import(uid)

    if import_mode == "found":
        result["progress_stats"] = await _evaluate_progress_for_accepted_ucs(uid)

    return result
