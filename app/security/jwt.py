"""Création et vérification des jetons JWT (HS256)."""
from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt

from app.core.config import settings


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Signe un jeton d'accès.

    Une date d'expiration (``exp``) n'est ajoutée que si
    ``JWT_EXPIRE_MINUTES`` est configuré ; ``expires_delta`` permet alors
    de surcharger ponctuellement la durée.

    Args:
        data: revendications à inclure (ex. ``{"sub": "user-123"}``).
        expires_delta: durée de validité spécifique.
    """
    claims = data.copy()
    if settings.JWT_EXPIRE_MINUTES is not None:
        lifetime = expires_delta or timedelta(minutes=settings.JWT_EXPIRE_MINUTES)
        claims["exp"] = datetime.now(timezone.utc) + lifetime
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    """
    Vérifie la signature et l'expiration d'un jeton, puis retourne son payload.

    Raises:
        jwt.ExpiredSignatureError: jeton expiré.
        jwt.InvalidTokenError: jeton mal formé ou signature invalide.
    """
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
