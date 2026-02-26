# backend/app/core/settings.py
# Chargement des variables d’environnement via Pydantic Settings, avec propriétés utiles (ex. `mongodb_uri`).

import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict
from rich import print

log = logging.getLogger("settings")


def _resolve_env_file() -> Path:
    # backend/ comme racine par défaut
    backend_root = Path(__file__).resolve().parents[1]
    default_env = backend_root / ".env"
    env_file = os.getenv("ENV_FILE")
    env_path = Path(env_file).resolve() if env_file else default_env
    log.info("Loading dotenv from: %s", env_path)
    return env_path


class Settings(BaseSettings):
    """Paramètres de l’application (Pydantic Settings).

    Description:
        Regroupe la configuration (app, MongoDB, JWT, admin, mail, elevation). Les valeurs
        sont chargées depuis `.env` (voir `model_config`). Fournit des valeurs par défaut
        lorsque pertinent (ex. `jwt_algorithm`, `jwt_expiration_minutes`).

    """

    # === App settings ===
    app_name: str = "GeoChallenge"
    environment: str = "development"  # or "production"
    api_version: str = "0.1.0"

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

    # === ELEVATION ===
    elevation_provider: str
    elevation_provider_endpoint: str
    elevation_provider_max_points_per_req: int
    elevation_provider_rate_delay_s: int
    elevation_enabled: bool

    # UPLOAD
    one_mb: int
    max_upload_mb: int

    # === TEST ===
    test: str

    model_config = SettingsConfigDict(
        env_file=_resolve_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def mongodb_uri(self) -> str:
        """Construit l’URI MongoDB à partir du template et des credentials.

        Description:
            Remplace les tokens `[[MONGODB_USER]]` et `[[MONGODB_PASSWORD]]` dans `mongodb_uri_tpl`
            par les valeurs chargées, afin d’obtenir une URI complète.

        Returns:
            str: URI MongoDB complète.
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


print("--- Settings loaded ---")
