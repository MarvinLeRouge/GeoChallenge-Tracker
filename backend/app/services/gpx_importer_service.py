# backend/app/services/gpx_importer_service.py
# Compatibility shim for the new GPX import system.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.mongodb import get_db

from .gpx_import.gpx_import_service import GpxImportService

# Global instance for backward compatibility
_gpx_import_service: GpxImportService | None = None


def get_gpx_import_service() -> GpxImportService:
    """Return the GPX import service instance.

    Returns:
        GpxImportService: Configured service instance.
    """
    global _gpx_import_service
    if _gpx_import_service is None:
        db = get_db()
        _gpx_import_service = GpxImportService(db)
    return _gpx_import_service


# Compatibility function for the legacy API
async def import_gpx_payload(
    payload: bytes,
    filename: str | None = None,
    user_id: ObjectId | None = None,
    import_mode: str = "both",
    fetch_elevation: bool = False,
    request: Any = None,  # compatibility parameter
    source_type: str | None = None,  # compatibility parameter
    force_update_attributes: bool = False,  # forced attribute update (admin only)
    **kwargs: Any,  # additional compatibility parameters
) -> dict[str, Any]:
    """Compatibility wrapper — import a GPX/ZIP payload.

    Args:
        payload: File data (GPX or ZIP).
        filename: Optional filename.
        user_id: User ID (for found caches).
        import_mode: Import mode ('both', 'caches', 'found').
        fetch_elevation: Enrich with elevation data.

    Returns:
        dict: Detailed import statistics.
    """
    service = get_gpx_import_service()
    return await service.import_gpx_payload(
        payload=payload,
        filename=filename,
        user_id=user_id,
        import_mode=import_mode,
        fetch_elevation=fetch_elevation,
        force_update_attributes=force_update_attributes,
    )
