import httpx
from app.core.config import settings


class KYCCallbackService:
    def __init__(self, url: str = None, token: str = None, timeout: float = None):
        self.url = url or settings.KYC_CALLBACK_URL
        self.token = token or settings.KYC_CALLBACK_TOKEN
        self.timeout = timeout if timeout is not None else settings.KYC_CALLBACK_TIMEOUT


    async def notify(self, kyc_id: str, ai_confidence_score: float, rejection_reason: str = "") -> bool:
        payload = {
            "kyc_id": kyc_id,
            "ai_confidence_score": ai_confidence_score,
            "rejection_reason": rejection_reason,
        }

        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.url, json=payload, headers=headers)
                response.raise_for_status()
            return True
        except Exception:
            return False


kyc_callback_service = KYCCallbackService()
