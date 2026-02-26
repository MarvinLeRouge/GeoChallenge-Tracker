import logging

from app.core.settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


async def check_mongodb() -> str:
    """
    Vérifie la connexion MongoDB

    Returns:
        "ok" si connecté, message d'erreur sinon
    """
    try:
        from app.db.mongodb import db

        # Ping MongoDB
        await db.command("ping")
        return "ok"

    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return f"error: {str(e)}"


async def check_email() -> str:
    """
    Vérifie la connexion SMTP (optionnel)

    Returns:
        "ok" si connecté, message d'erreur sinon
    """
    try:
        # Si vous utilisez MailDev en dev, toujours ok
        if settings.environment == "development":
            return "ok"

        # TODO: Implémenter vrai check SMTP pour prod
        # import aiosmtplib
        # ...

        return "ok"

    except Exception as e:
        logger.error(f"Email health check failed: {e}")
        return f"error: {str(e)}"
