# backend/app/core/email.py
# Email sending utilities (async SMTP) for account verification.

from email.message import EmailMessage

from aiosmtplib import send

from app.core.settings import get_settings

settings = get_settings()


async def send_verification_email(to_email: str, username: str, code: str):
    """Sends the account verification email.

    Description:
        Builds a message containing a verification link and sends it via SMTP (async).
        The link includes the `code` to be validated on the API side.

    Args:
        to_email (str): Recipient email address.
        username (str): Username (for personalizing the message).
        code (str): Verification token (single use).

    Returns:
        None: Coroutine completes after sending.

    Raises:
        aiosmtplib.errors.SMTPException: If the SMTP send fails.
    """
    msg = EmailMessage()
    msg["Subject"] = "Vérifiez votre compte GeoChallenge"
    msg["From"] = settings.mail_from
    msg["To"] = to_email

    link = f"http://localhost:8000/auth/verify-email?code={code}"  # adjust if using a frontend URL
    msg.set_content(
        f"Bonjour {username},\n\nCliquez sur le lien suivant pour vérifier votre compte :\n{link}\n\nCe lien expire dans 1 heure."
    )

    await send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=False,  # for Maildev or local development
    )
