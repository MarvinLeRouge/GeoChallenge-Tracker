from pydantic_settings import BaseSettings, SettingsConfigDict

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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def mongodb_uri(self) -> str:
        """Build the full MongoDB URI from template."""
        return self.mongodb_uri_tpl.replace("[[MONGODB_USER]]", self.mongodb_user)\
                                   .replace("[[MONGODB_PASSWORD]]", self.mongodb_password)

# Instance globale
settings = Settings()
