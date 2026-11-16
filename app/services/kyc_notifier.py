"""
Diffusion du résultat d'un dossier KYC vers l'extérieur.

* **Email** à l'utilisateur lorsque des anomalies sont détectées ;
* **Callback HTTP** systématique vers le service appelant.

Ces notifications sont « best effort » : leur échec est journalisé mais ne
remet jamais en cause la réponse renvoyée par l'API.
"""
import asyncio
import html
from typing import Any, List

from app.core.logging import get_logger
from app.domain.kyc.fields import FieldResults
from app.domain.kyc.reasons import InvalidField, build_rejection_reason
from app.services.kyc_callback import KYCCallbackService, kyc_callback_service
from app.services.mailer.mail_service import MailService, mail_service

logger = get_logger(__name__)

WARNING_EMAIL_SUBJECT = "Alerte KYC : champs invalides détectés"
WARNING_EMAIL_TEMPLATE = "warning"


class KYCNotifier:
    """Informe l'utilisateur et le service appelant du verdict d'un dossier."""

    def __init__(
        self,
        mailer: MailService = mail_service,
        callback: KYCCallbackService = kyc_callback_service,
    ):
        self.mailer = mailer
        self.callback = callback

    @staticmethod
    def _render_invalid_fields(invalid_fields: List[InvalidField]) -> str:
        """
        Liste HTML des anomalies.

        Libellés et motifs proviennent exclusivement des constantes du
        domaine (jamais de la saisie utilisateur) : aucun échappement requis.
        """
        return "".join(f"<li>{item['label']} ({item['reason']})</li>" for item in invalid_fields)

    async def send_warning_email(
        self,
        results: FieldResults,
        form_data: Any,
        invalid_fields: List[InvalidField],
    ) -> None:
        """
        Envoie l'email d'alerte si au moins un champ est invalide.

        Le nom affiché est celui déclaré par l'utilisateur ; il est échappé
        pour empêcher toute injection HTML dans le gabarit.
        """
        if not invalid_fields:
            return

        user_name = form_data.nom_et_prenom or form_data.adresse_mail
        try:
            # smtplib est bloquant : exécution dans un thread dédié.
            await asyncio.to_thread(
                self.mailer.send_email,
                email_to=form_data.adresse_mail,
                subject=WARNING_EMAIL_SUBJECT,
                template_name=WARNING_EMAIL_TEMPLATE,
                user_name=html.escape(user_name or ""),
                invalid_fields=self._render_invalid_fields(invalid_fields),
                total_percentage=results.get("total_percentage", 0.0),
            )
        except Exception:
            logger.warning("Échec de l'envoi de l'email d'alerte KYC", exc_info=True)

    async def send_callback(
        self,
        results: FieldResults,
        form_data: Any,
        invalid_fields: List[InvalidField],
    ) -> None:
        """Transmet le score et le motif de rejet au service appelant."""
        await self.callback.notify(
            kyc_id=form_data.kyc_id,
            ai_confidence_score=results.get("total_percentage", 0.0),
            rejection_reason=build_rejection_reason(invalid_fields),
        )

    async def notify(
        self,
        results: FieldResults,
        form_data: Any,
        invalid_fields: List[InvalidField],
    ) -> None:
        """Déclenche l'ensemble des notifications (email puis callback)."""
        await self.send_warning_email(results, form_data, invalid_fields)
        await self.send_callback(results, form_data, invalid_fields)


kyc_notifier = KYCNotifier()
