import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    PROJECT_NAME: str = "KYC Validation Pipeline"
    PROJECT_VERSION: str = "1.0.0"
    
    # API Configuration
    API_V1_STR: str = "/api/v1"
    
    # External Services
    DATA_PROVIDER_URL: str = os.getenv("DATA_PROVIDER_URL")

    # KYC Callback
    KYC_CALLBACK_URL: str = os.getenv("KYC_CALLBACK_URL")
    KYC_CALLBACK_TOKEN: str = os.getenv("KYC_CALLBACK_TOKEN")
    KYC_CALLBACK_TIMEOUT: float = float(os.getenv("KYC_CALLBACK_TIMEOUT", "10"))
    
    # CORS Configuration
    ALLOWED_ORIGINS: List[str] = os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://onutechagent.vercel.app",
    ).split(",")
    
    # OCR Configuration
    OCR_LANGUAGE: str = os.getenv("OCR_LANGUAGE", "fra")
    
    # Debug Mode
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me")
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int | None = None
    raw_expire = os.getenv("JWT_EXPIRE_MINUTES")
    if raw_expire is not None and raw_expire.strip().lower() not in {"false", "0", ""}:
        JWT_EXPIRE_MINUTES = int(raw_expire)

settings = Settings()
