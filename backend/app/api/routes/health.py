from datetime import datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.health_checks import check_email, check_mongodb
from app.core.settings import get_settings
from app.models.base.health import HealthCheck

settings = get_settings()

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthCheck,
    summary="Health check de l'API",
    description="Retourne le statut de l'API et de ses dépendances (BDD, email, etc.)",
)
async def health() -> JSONResponse:
    """
    Health check endpoint standard

    Vérifie :
    - MongoDB
    - Email (optionnel)

    Returns:
        200 si tout OK, 503 si un service est down
    """
    # Exécuter tous les checks
    checks = {
        "database": await check_mongodb(),
        "email": await check_email(),
    }

    # Déterminer le statut global
    has_errors = any(check != "ok" for check in checks.values())
    overall_status = "degraded" if has_errors else "ok"

    # Code HTTP
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE if has_errors else status.HTTP_200_OK

    # Réponse
    response = HealthCheck(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=settings.api_version if hasattr(settings, "api_version") else "0.1.0",
        checks=checks,
    )

    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))
