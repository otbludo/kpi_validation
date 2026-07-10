import os
from fastapi import HTTPException, status
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from app.messages.errors import ERREUR_ENVOI_EMAIL


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = os.getenv("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
EMAIL_FROM = os.getenv("EMAIL_FROM")


class MailService:
    def __init__(self):
        self.template_path = Path(__file__).parent / "model"


    def _load_template(self, template_name: str, **kwargs) -> str:
        """Charge un fichier HTML et remplace les variables {{key}}"""
        file_path = self.template_path / f"{template_name}.html"
        if not file_path.exists():
            raise FileNotFoundError(f"Template {template_name}.html introuvable")
        
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        for key, value in kwargs.items():
            content = content.replace(f"{{{{{key}}}}}", str(value))
        return content


    def send_email(self, email_to: str, subject: str, template_name: str, **kwargs):
        """Méthode générique pour envoyer n'importe quel type de mail"""
        try:
            html_content = self._load_template(template_name, **kwargs)
            
            message = MIMEMultipart()
            message["From"] = EMAIL_FROM
            message["To"] = email_to
            message["Subject"] = subject
            message.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASSWORD)
                server.send_message(message)
            return True
        
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
                detail=ERREUR_ENVOI_EMAIL.format(str(e))
            )


mailService = MailService()