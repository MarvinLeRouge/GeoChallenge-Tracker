# backend/app/core/email.py
# Utilitaires d’envoi d’email (SMTP async) pour la vérification de compte.

from email.message import EmailMessage

from aiosmtplib import send

from app.core.settings import settings


async def send_verification_email(to_email: str, username: str, code: str):
    """Envoie l’email de vérification de compte.

    Description:
        Construit un message contenant un lien de vérification et l’envoie via SMTP (async).
        Le lien inclut le `code` à valider côté API.

    Args:
        to_email (str): Adresse destinataire.
        username (str): Nom d’utilisateur (personnalisation du message).
        code (str): Jeton de vérification (usage unique).

    Returns:
        None: Coroutine terminée après envoi.

    Raises:
        aiosmtplib.errors.SMTPException: En cas d’échec d’envoi SMTP.
    """
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
        start_tls=False,  # pour Maildev ou local
    )
