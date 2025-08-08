# backend/app/core/email.py

from email.message import EmailMessage
from aiosmtplib import send
from app.core.settings import settings

async def send_verification_email(to_email: str, username: str, code: str):
    msg = EmailMessage()
    msg["Subject"] = "Vérifiez votre compte GeoChallenge"
    msg["From"] = settings.mail_from
    msg["To"] = to_email

    link = f"http://localhost:8000/auth/verify-email?code={code}"  # à adapter si frontend
    msg.set_content(
        f"Bonjour {username},\n\nCliquez sur le lien suivant pour vérifier votre compte :\n{link}\n\nCe lien expire dans 1 heure."
    )

    await send(
        msg,
        hostname=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username or None,
        password=settings.smtp_password or None,
        start_tls=False  # pour Maildev ou local
    )
