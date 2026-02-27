from datetime import datetime
from typing import Optional

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


class VersionInfo(BaseModel):
    """Informations de version"""

    version: str = Field(..., description="Version de l'API (semver)")
    environment: str = Field(..., description="Environnement (dev, staging, prod)")
    build_date: Optional[datetime] = Field(None, description="Date de build")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "0.1.0",
                "environment": "production",
                "build_date": "2026-02-26T10:00:00Z",
            }
        }


class APIInfo(BaseModel):
    """Informations générales sur l'API"""

    name: str
    version: str
    build_date: Optional[datetime] = Field(None, description="Date de build")
    documentation: str
    support: str
