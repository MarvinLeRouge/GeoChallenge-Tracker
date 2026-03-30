# backend/app/core/settings.py
# Loads environment variables via Pydantic Settings, with useful properties (e.g. `mongodb_uri`).

import logging
import os
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

log = logging.getLogger("settings")


def _resolve_env_file() -> Path:
    # backend/ as the default root
    backend_root = Path(__file__).resolve().parents[2]
    default_env = backend_root / ".env"
    env_file = os.getenv("ENV_FILE")
    env_path = Path(env_file).resolve() if env_file else default_env
    log.info("Loading dotenv from: %s", env_path)
    return env_path


class Settings(BaseSettings):
    """Application settings (Pydantic Settings).

    Description:
        Groups configuration for app, MongoDB, JWT, admin, mail, and elevation. Values
        are loaded from `.env` (see `model_config`). Provides sensible defaults where
        applicable (e.g. `jwt_algorithm`, `jwt_expiration_minutes`).

    """

    # === App settings ===
    app_name: str = "GeoChallenge"
    environment: str = "development"  # or "production"
    api_version: str = "0.1.0"
    build_date: Optional[str] = None
    support_url: str = ""

    # === MongoDB ===
    mongodb_user: str
    mongodb_password: str
    mongodb_uri_tpl: str
    mongodb_db: str

    # === JWT ===
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60 * 24  # 1 day

    # === ADMIN ===
    admin_username: str
    admin_email: str
    admin_password: str

    # === MAIL ===
    mail_from: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    app_frontend_url: str = "http://localhost:5173"
    admin_dest_email: str

    # === ELEVATION ===
    elevation_provider: str
    elevation_provider_endpoint: str
    elevation_provider_max_points_per_req: int
    elevation_provider_rate_delay_s: int
    elevation_enabled: bool

    # === CORS ===
    cors_origins: list[str] = ["http://localhost:5173"]

    # UPLOAD
    one_mb: int
    max_upload_mb: int

    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("build_date", mode="before")
    @classmethod
    def empty_str_to_none(cls, v):
        """Converts an empty string to None."""
        if v == "":
            return None
        return v

    @property
    def build_date_parsed(self) -> Optional[datetime]:
        """Parses BUILD_DATE from the environment variable."""
        if self.build_date and self.build_date != "":
            try:
                return datetime.fromisoformat(self.build_date.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        return None

    @property
    def mongodb_uri(self) -> str:
        """Builds the MongoDB URI from the template and credentials.

        Description:
            Replaces the `[[MONGODB_USER]]` and `[[MONGODB_PASSWORD]]` tokens in `mongodb_uri_tpl`
            with the loaded values to produce a complete URI.

        Returns:
            str: Complete MongoDB URI.
        """
        return self.mongodb_uri_tpl.replace("[[MONGODB_USER]]", self.mongodb_user).replace(
            "[[MONGODB_PASSWORD]]", self.mongodb_password
        )

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * self.one_mb


@lru_cache
def get_settings() -> Settings:
    return Settings()


log.info("Settings loaded from: %s", _resolve_env_file())
