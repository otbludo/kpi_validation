"""
Envoi d'emails transactionnels via SMTP (Mailtrap en développement).

Les gabarits HTML se trouvent dans ``templates/`` et utilisent la syntaxe
``{{variable}}``. Les valeurs sont injectées telles quelles : l'appelant est
responsable d'échapper les données saisies par l'utilisateur.

L'envoi est **synchrone** (``smtplib``) : depuis du code asynchrone,
l'exécuter via ``asyncio.to_thread``.
"""
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.core.config import settings
from app.core.exceptions import EmailDeliveryError
from app.messages.errors import EMAIL_SEND_ERROR

TEMPLATES_DIR = Path(__file__).parent / "templates"


class MailService:
    """Rend un gabarit HTML et l'envoie par SMTP."""

    def __init__(self, templates_dir: Path = TEMPLATES_DIR):
        self.template_path = templates_dir

    def _load_template(self, template_name: str, **context) -> str:
        """
        Charge ``<template_name>.html`` et remplace chaque ``{{clé}}``.

        Raises:
            FileNotFoundError: si le gabarit n'existe pas.
        """
        file_path = self.template_path / f"{template_name}.html"
        if not file_path.exists():
            raise FileNotFoundError(f"Template {template_name}.html introuvable")

        content = file_path.read_text(encoding="utf-8")
        for key, value in context.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
        return content

    def _build_message(self, email_to: str, subject: str, html_content: str) -> MIMEMultipart:
        message = MIMEMultipart()
        message["From"] = settings.EMAIL_FROM
        message["To"] = email_to
        message["Subject"] = subject
        message.attach(MIMEText(html_content, "html"))
        return message

    def send_email(self, email_to: str, subject: str, template_name: str, **context) -> bool:
        """
        Envoie un email HTML construit à partir d'un gabarit.

        Args:
            email_to: destinataire.
            subject: objet du message.
            template_name: nom du gabarit (sans extension).
            **context: variables injectées dans le gabarit.

        Returns:
            ``True`` si l'envoi a abouti.

        Raises:
            EmailDeliveryError: gabarit introuvable ou erreur SMTP.
        """
        try:
            html_content = self._load_template(template_name, **context)
            message = self._build_message(email_to, subject, html_content)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.send_message(message)
            return True
        except Exception as exc:
            raise EmailDeliveryError(EMAIL_SEND_ERROR.format(exc)) from exc


mail_service = MailService()
