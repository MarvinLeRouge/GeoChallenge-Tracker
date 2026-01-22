from typing import Any, Generic, Optional, TypeVar, Union

from pydantic import BaseModel

T = TypeVar("T")


class SuccessResponse(BaseModel, Generic[T]):
    """Format standardisé pour les réponses de succès."""

    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None


class ErrorResponse(BaseModel):
    """Format standardisé pour les réponses d'erreur."""

    success: bool = False
    error: dict[str, Any]

    @classmethod
    def from_detail(cls, detail: Union[str, dict[str, Any]], code: str = "VALIDATION_ERROR"):
        """Créer une réponse d'erreur à partir d'un détail."""
        if isinstance(detail, str):
            return cls(error={"code": code, "message": detail})
        return cls(error={"code": code, **detail})
