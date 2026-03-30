# backend/app/core/email.py
# Email sending utilities (async SMTP) for account verification.

import logging
from email.message import EmailMessage

from aiosmtplib import send

from app.core.settings import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


async def send_verification_email(to_email: str, username: str, code: str):
    """Sends the account verification email.

    Description:
        Builds a message containing a verification link and sends it via SMTP (async).
        The link includes the `code` to be validated on the API side.
        Uses STARTTLS if smtp_port is 587, SSL if 465, plain otherwise.

    Args:
        to_email (str): Recipient email address.
        username (str): Username (for personalizing the message).
        code (str): Verification token (single use).

    Returns:
        None: Coroutine completes after sending.
    """
    msg = EmailMessage()
    msg["Subject"] = "Vérifiez votre compte GeoChallenge"
    msg["From"] = settings.mail_from
    msg["To"] = to_email

    link = f"{settings.app_frontend_url}/verify-email?code={code}"
    msg.set_content(
        f"Bonjour {username},\n\nCliquez sur le lien suivant pour vérifier votre compte :\n{link}\n\nCe lien expire dans 24 heures."
    )

    use_tls = settings.smtp_port == 465
    start_tls = settings.smtp_port == 587

    try:
        await send(
            msg,
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            username=settings.smtp_username or None,
            password=settings.smtp_password or None,
            use_tls=use_tls,
            start_tls=start_tls,
        )
    except Exception:
        logger.exception("Failed to send verification email to %s", to_email)


async def send_test_email(to_email: str, user_count: int, cache_count: int, challenge_count: int):
    """Sends a test email with basic app statistics.

    Args:
        to_email (str): Recipient email address.
        user_count (int): Number of users in the database.
        cache_count (int): Number of caches in the database.
        challenge_count (int): Number of challenges in the database.

    Raises:
        aiosmtplib.errors.SMTPException: If the SMTP send fails.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    msg = EmailMessage()
    msg["Subject"] = f"GC Tracker - Test email — {now}"
    msg["From"] = settings.mail_from
    msg["To"] = to_email

    msg.set_content(
        f"Bonjour,\n\n"
        f"Ceci est un email de test envoyé depuis GeoChallenge Tracker.\n\n"
        f"État de la base de données au {now} :\n"
        f"  - Utilisateurs : {user_count}\n"
        f"  - Caches       : {cache_count}\n"
        f"  - Défis        : {challenge_count}\n\n"
        f"Si vous recevez cet email, la configuration SMTP est fonctionnelle.\n\n"
        f"— GeoChallenge Tracker"
    )

    use_tls = settings.smtp_port == 465
    start_tls = settings.smtp_port == 587

    await send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        use_tls=use_tls,
        start_tls=start_tls,
    )
