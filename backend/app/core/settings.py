# backend/app/core/settings.py
# Chargement des variables d’environnement via Pydantic Settings, avec propriétés utiles (ex. `mongodb_uri`).

from pydantic_settings import BaseSettings, SettingsConfigDict
from rich import print

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

    # === TEST ===
    test: str
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def mongodb_uri(self) -> str:
        """Construit l’URI MongoDB à partir du template et des credentials.

        Description:
            Remplace les tokens `[[MONGODB_USER]]` et `[[MONGODB_PASSWORD]]` dans `mongodb_uri_tpl`
            par les valeurs chargées, afin d’obtenir une URI complète.

        Returns:
            str: URI MongoDB complète.
        """
        return self.mongodb_uri_tpl.replace("[[MONGODB_USER]]", self.mongodb_user)\
                                   .replace("[[MONGODB_PASSWORD]]", self.mongodb_password)

# Instance globale
settings = Settings()

print("--- Settings loaded ---")
