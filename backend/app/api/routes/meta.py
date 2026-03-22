from datetime import datetime

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.core.meta import check_email, check_mongodb
from app.core.settings import get_settings
from app.domain.models.meta import APIInfo, HealthCheck, VersionInfo

settings = get_settings()

router = APIRouter(tags=["Meta"])


@router.get(
    "/health",
    response_model=HealthCheck,
    summary="API health check",
    description="Returns the API status and its dependencies (database, email, etc.)",
)
async def health() -> JSONResponse:
    """
    Standard health check endpoint.

    Checks:
    - MongoDB
    - Email (optional)

    Returns:
        200 if everything is OK, 503 if a service is down.
    """
    # Run all checks
    checks = {
        "database": await check_mongodb(),
        "email": await check_email(),
    }

    # Determine overall status
    has_errors = any(check != "ok" for check in checks.values())
    overall_status = "degraded" if has_errors else "ok"

    # HTTP status code
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE if has_errors else status.HTTP_200_OK

    # Response
    response = HealthCheck(
        status=overall_status,
        timestamp=datetime.utcnow(),
        version=settings.api_version if hasattr(settings, "api_version") else "0.1.0",
        checks=checks,
    )

    return JSONResponse(status_code=status_code, content=response.model_dump(mode="json"))


@router.get("/version", response_model=VersionInfo)
async def version():
    """
    API version.
    """
    return {
        "version": settings.api_version,
        "environment": settings.environment,
        "build_date": settings.build_date if hasattr(settings, "build_date") else None,
    }


@router.get("/info", response_model=APIInfo)
async def api_info():
    """
    General API information (optional).
    """
    return {
        "name": settings.app_name + " API",
        "version": settings.api_version,
        "build_date": settings.build_date if hasattr(settings, "build_date") else None,
        "documentation": "/documentation",
        "support": settings.support_url if hasattr(settings, "support_url") else None,
    }
