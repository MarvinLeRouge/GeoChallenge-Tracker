# backend/app/api/core/settings.py

from pydantic_settings import BaseSettings, SettingsConfigDict
from rich import print

class Settings(BaseSettings):
    # === App settings ===
    app_name: str = "GeoChallenge"
    environment: str = "development"  # or "production"

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
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def mongodb_uri(self) -> str:
        """Build the full MongoDB URI from template."""
        return self.mongodb_uri_tpl.replace("[[MONGODB_USER]]", self.mongodb_user)\
                                   .replace("[[MONGODB_PASSWORD]]", self.mongodb_password)

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * self.one_mb

# Instance globale
settings = Settings()

print("--- Settings loaded ---")
