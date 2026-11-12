from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):  # noqa: UP046 - PEP 695 rewrite is an unsafe fix, left as-is
    """Standardized format for success responses."""

    success: bool = True
    data: T | None = None
    message: str | None = None


class ErrorResponse(BaseModel):
    """Standardized format for error responses."""

    success: bool = False
    error: dict[str, Any]

    @classmethod
    def from_detail(cls, detail: str | dict[str, Any], code: str = "VALIDATION_ERROR"):
        """Create an error response from a detail value."""
        if isinstance(detail, str):
            return cls(error={"code": code, "message": detail})
        return cls(error={"code": code, **detail})
