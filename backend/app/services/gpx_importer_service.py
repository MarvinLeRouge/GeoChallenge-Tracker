# backend/app/services/gpx_importer_service.py
# Fichier de compatibilité pour le nouveau système d'import GPX.

from __future__ import annotations

from typing import Any

from bson import ObjectId

from app.db.mongodb import db

from .gpx_import.gpx_import_service import GpxImportService

# Instance globale pour compatibilité
_gpx_import_service: GpxImportService | None = None


def get_gpx_import_service() -> GpxImportService:
    """Obtenir l'instance du service d'import GPX.

    Returns:
        GpxImportService: Instance configurée du service.
    """
    global _gpx_import_service
    if _gpx_import_service is None:
        _gpx_import_service = GpxImportService(db)
    return _gpx_import_service


# Fonction de compatibilité pour l'ancien API
async def import_gpx_payload(
    payload: bytes,
    filename: str | None = None,
    user_id: ObjectId | None = None,
    import_mode: str = "both",
    fetch_elevation: bool = False,
    request: Any = None,  # Paramètre de compatibilité
    source_type: str | None = None,  # Paramètre de compatibilité
    force_update_attributes: bool = False,  # Mise à jour forcée des attributs (admin seulement)
    **kwargs: Any,  # Autres paramètres de compatibilité
) -> dict[str, Any]:
    """Fonction de compatibilité - importer un payload GPX/ZIP.

    Args:
        payload: Données du fichier (GPX ou ZIP).
        filename: Nom de fichier optionnel.
        user_id: ID de l'utilisateur (pour les trouvailles).
        import_mode: Mode d'import ('both', 'caches', 'found').
        fetch_elevation: Enrichir avec les données d'élévation.

    Returns:
        dict: Statistiques d'import détaillées.
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
