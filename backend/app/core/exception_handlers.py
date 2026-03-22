from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.dto.response_format import ErrorResponse


def register_exception_handlers(app: FastAPI):
    """Registers global exception handlers to standardize responses."""

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Handler for standard HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse.from_detail(
                {"code": f"HTTP_{exc.status_code}", "message": exc.detail}
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handler for Pydantic validation errors."""
        # Extract validation error details
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

    # Handler for uncaught exceptions
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handler for uncaught exceptions."""
        return JSONResponse(
            status_code=500,
            content=ErrorResponse.from_detail(
                {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}
            ).model_dump(),
        )
