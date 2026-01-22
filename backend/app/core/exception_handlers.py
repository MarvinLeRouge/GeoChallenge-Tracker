from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dto.response_format import ErrorResponse


def register_exception_handlers(app: FastAPI):
    """Enregistre les gestionnaires d'exceptions globaux pour standardiser les réponses."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Gestionnaire pour les exceptions HTTP standards."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse.from_detail(
                {"code": f"HTTP_{exc.status_code}", "message": exc.detail}
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Gestionnaire pour les erreurs de validation Pydantic."""
        # Extraire les détails des erreurs de validation
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "field": " -> ".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"],
                }
            )

        return JSONResponse(
            status_code=422,
            content=ErrorResponse.from_detail(
                {"code": "VALIDATION_ERROR", "message": "Validation failed", "details": errors}
            ).model_dump(),
        )

    # Gestionnaire pour les exceptions non capturées
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Gestionnaire pour les exceptions non capturées."""
        return JSONResponse(
            status_code=500,
            content=ErrorResponse.from_detail(
                {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
            ).model_dump(),
        )
