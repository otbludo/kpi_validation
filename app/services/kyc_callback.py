"""Notification du service appelant à l'issue du traitement d'un dossier."""
from typing import Optional

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class KYCCallbackService:
    """Envoie le résultat d'un dossier KYC à ``KYC_CALLBACK_URL``."""

    def __init__(
        self,
        url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Args:
            url: URL du webhook ; à défaut, ``settings.KYC_CALLBACK_URL``.
            token: jeton Bearer ; à défaut, ``settings.KYC_CALLBACK_TOKEN``.
            timeout: délai maximal de la requête en secondes.
        """
        self.url = url or settings.KYC_CALLBACK_URL
        self.token = token or settings.KYC_CALLBACK_TOKEN
        self.timeout = timeout if timeout is not None else settings.KYC_CALLBACK_TIMEOUT

    def _headers(self) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def notify(self, kyc_id: str, ai_confidence_score: float, rejection_reason: str = "") -> bool:
        """
        Publie le score et le motif de rejet du dossier.

        L'échec du callback n'interrompt pas le pipeline : il est journalisé
        et signalé par la valeur de retour.

        Returns:
            ``True`` si le service distant a répondu avec un code 2xx.
        """
        payload = {
            "kyc_id": kyc_id,
            "ai_confidence_score": ai_confidence_score,
            "rejection_reason": rejection_reason,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, json=payload, headers=self._headers())
                response.raise_for_status()
            return True
        except Exception:
            logger.warning("Échec du callback KYC pour le dossier %s", kyc_id, exc_info=True)
            return False


kyc_callback_service = KYCCallbackService()
