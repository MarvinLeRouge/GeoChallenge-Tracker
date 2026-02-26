from datetime import datetime

from pydantic import BaseModel, Field

from app.core.utils import utcnow


class HealthCheck(BaseModel):
    """Modèle de réponse health check"""

    status: str = Field(..., description="Overall status: ok, degraded, error")
    timestamp: datetime = Field(default_factory=utcnow)
    version: str = Field(..., description="API version")
    checks: dict[str, str] = Field(..., description="Individual service checks")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "ok",
                "timestamp": "2026-02-26T10:30:00Z",
                "version": "0.1.0",
                "checks": {"database": "ok", "email": "ok"},
            }
        }
