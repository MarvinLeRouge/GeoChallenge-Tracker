# backend/app/api/routes/caches.py

from fastapi import APIRouter, UploadFile, File, HTTPException, status, Depends, Query
from app.core.security import get_current_user
from app.services.gpx_importer import import_gpx_payload

router = APIRouter(prefix="/caches", tags=["caches"])

@router.post("/upload-gpx")
async def upload_gpx(
    file: UploadFile = File(...),
    found: bool = Query(False, description="Si true, crée aussi des found_caches en fonction des found_date"),
    current_user: dict = Depends(get_current_user),
):
    payload = await file.read()
    await file.close()

    try:
        summary = import_gpx_payload(
            payload=payload,
            filename=file.filename or "upload.gpx",
            user=current_user,
            found=found,
        )
        return summary
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid GPX/ZIP: {e}")