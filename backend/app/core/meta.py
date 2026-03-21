import asyncio
import logging
import smtplib

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
        from app.db.mongodb import get_db

        # Ping MongoDB
        db = get_db()
        await db.command("ping")
        return "ok"

    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return f"error: {str(e)}"


async def check_email() -> str:
    """Vérifie la connexion SMTP via un EHLO/NOOP.

    Ouvre une connexion SMTP (avec STARTTLS si le port est 587), envoie NOOP,
    puis ferme proprement. Exécuté dans un thread pour ne pas bloquer la boucle asyncio.

    Returns:
        str: "ok" si le serveur répond, message d'erreur sinon.
    """

    def _smtp_check() -> str:
        use_tls = settings.smtp_port == 465
        use_starttls = settings.smtp_port == 587
        smtp_cls = smtplib.SMTP_SSL if use_tls else smtplib.SMTP
        with smtp_cls(settings.smtp_host, settings.smtp_port, timeout=5) as smtp:
            if use_starttls:
                smtp.starttls()
            smtp.noop()
        return "ok"

    try:
        return await asyncio.get_event_loop().run_in_executor(None, _smtp_check)
    except Exception as e:
        logger.error("SMTP health check failed: %s", e)
        return f"error: {e}"
