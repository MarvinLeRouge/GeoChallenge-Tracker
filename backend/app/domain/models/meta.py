from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.core.utils import utcnow


class HealthCheck(BaseModel):
    """Health check response model."""

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
    """Version information."""

    version: str = Field(..., description="API version (semver)")
    environment: str = Field(..., description="Environment (dev, staging, prod)")
    build_date: Optional[datetime] = Field(None, description="Build date")

    class Config:
        json_schema_extra = {
            "example": {
                "version": "0.1.0",
                "environment": "production",
                "build_date": "2026-02-26T10:00:00Z",
            }
        }


class APIInfo(BaseModel):
    """General API information."""

    name: str
    version: str
    build_date: Optional[datetime] = Field(None, description="Build date")
    documentation: str
    support: str
