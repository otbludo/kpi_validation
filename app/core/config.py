import os
from typing import List

class Settings:
    PROJECT_NAME: str = "KYC Validation Pipeline"
    PROJECT_VERSION: str = "1.0.0"
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    
    # External Services
    DATA_PROVIDER_URL: str = os.getenv("DATA_PROVIDER_URL")

    # KYC Callback (notification du service appelant une fois le traitement terminé)
    KYC_CALLBACK_URL: str = os.getenv("KYC_CALLBACK_URL")
    KYC_CALLBACK_TOKEN: str = os.getenv("KYC_CALLBACK_TOKEN")
    KYC_CALLBACK_TIMEOUT: float = float(os.getenv("KYC_CALLBACK_TIMEOUT", "10"))
    
    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = os.getenv("ALLOWED_ORIGINS", "*").split(",") if os.getenv("ALLOWED_ORIGINS") else ["*"]
    
    # OCR Configuration
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "fra")
    
    # Debug Mode
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

settings = Settings()
