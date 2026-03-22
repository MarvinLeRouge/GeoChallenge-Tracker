import asyncio
import logging
import smtplib

from app.core.settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


async def check_mongodb() -> str:
    """
    Checks the MongoDB connection.

    Returns:
        "ok" if connected, error message otherwise.
    """
    try:
        from app.db.mongodb import get_db

        # Ping MongoDB to verify connectivity
        db = get_db()
        await db.command("ping")
        return "ok"

    except Exception as e:
        logger.error(f"MongoDB health check failed: {e}")
        return f"error: {str(e)}"


async def check_email() -> str:
    """Checks the SMTP connection via an EHLO/NOOP exchange.

    Opens an SMTP connection (with STARTTLS if port is 587), sends NOOP,
    then closes cleanly. Executed in a thread to avoid blocking the asyncio event loop.

    Returns:
        str: "ok" if the server responds, error message otherwise.
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
