from typing import Any, Generic, Optional, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Standardized format for success responses."""

    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Standardized format for error responses."""

    success: bool = False
    error: dict[str, Any]

    @classmethod
    def from_detail(cls, detail: Union[str, dict[str, Any]], code: str = "VALIDATION_ERROR"):
        """Create an error response from a detail value."""
        if isinstance(detail, str):
            return cls(error={"code": code, "message": detail})
        return cls(error={"code": code, **detail})
