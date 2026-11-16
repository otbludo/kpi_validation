"""
Configuration centralisée de l'application.

Toutes les variables d'environnement sont lues **ici et uniquement ici**.
Les autres modules consomment l'instance ``settings`` plutôt que d'appeler
``os.getenv`` directement, ce qui :

* rend la configuration découvrable en un seul endroit ;
* facilite la surcharge des valeurs dans les tests (``monkeypatch.setattr``) ;
* évite les incohérences de typage (ex. un port SMTP lu comme ``str``).

Le fichier ``.env`` est chargé une seule fois, à l'import de ce module.
"""
import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()


def _get_bool(name: str, default: str = "false") -> bool:
    """Interprète une variable d'environnement comme un booléen."""
    return os.getenv(name, default).strip().lower() == "true"


def _get_optional_int(name: str) -> Optional[int]:
    """
    Lit un entier optionnel.

    Les valeurs ``"false"``, ``"0"`` ou une chaîne vide sont interprétées
    comme « désactivé » et renvoient ``None``.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip().lower() in {"false", "0", ""}:
        return None
    return int(raw)


def _get_list(name: str, default: str) -> List[str]:
    """Lit une liste de valeurs séparées par des virgules."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]


class Settings:
    """Paramètres de l'application, résolus depuis l'environnement."""

    # --- Application -------------------------------------------------------
    PROJECT_NAME: str = "KYC Validation Pipeline"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = _get_bool("DEBUG")

    # --- CORS --------------------------------------------------------------
    ALLOWED_ORIGINS: List[str] = _get_list(
        "ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://onutechagent.vercel.app",
    )

    # --- Authentification JWT ---------------------------------------------
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "change-me")
    JWT_ALGORITHM: str = "HS256"
    #: Durée de validité des tokens en minutes ; ``None`` = pas d'expiration.
    JWT_EXPIRE_MINUTES: Optional[int] = _get_optional_int("JWT_EXPIRE_MINUTES")

    # --- OpenRouter (modèle de vision) ------------------------------------
    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = os.getenv(
        "OPENROUTER_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"
    )
    #: Plafond de tokens de la réponse d'analyse (JSON de 7 champs ≈ 300 tokens).
    #: Sans plafond, OpenRouter réserve la taille maximale du modèle sur les
    #: crédits et peut refuser la requête (erreur 402).
    OPENROUTER_MAX_TOKENS: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "1024"))

    # --- InsightFace (reconnaissance faciale) -----------------------------
    INSIGHTFACE_MODEL: str = os.getenv("INSIGHTFACE_MODEL", "buffalo_l")
    INSIGHTFACE_PROVIDERS: List[str] = _get_list("INSIGHTFACE_PROVIDERS", "CPUExecutionProvider")
    #: Similarité cosinus minimale pour considérer deux visages identiques.
    INSIGHTFACE_THRESHOLD: float = float(os.getenv("INSIGHTFACE_THRESHOLD", "0.40"))
    #: ``-1`` = CPU, ``>= 0`` = index du GPU.
    INSIGHTFACE_CTX_ID: int = int(os.getenv("INSIGHTFACE_CTX_ID", "-1"))

    # --- SMTP (notifications email) ---------------------------------------
    SMTP_HOST: Optional[str] = os.getenv("SMTP_HOST")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: Optional[str] = os.getenv("SMTP_USER")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    EMAIL_FROM: Optional[str] = os.getenv("EMAIL_FROM")

    # --- Callback vers le service appelant --------------------------------
    KYC_CALLBACK_URL: Optional[str] = os.getenv("KYC_CALLBACK_URL")
    KYC_CALLBACK_TOKEN: Optional[str] = os.getenv("KYC_CALLBACK_TOKEN")
    KYC_CALLBACK_TIMEOUT: float = float(os.getenv("KYC_CALLBACK_TIMEOUT", "10"))


settings = Settings()
