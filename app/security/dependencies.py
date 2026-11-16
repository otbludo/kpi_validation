"""Dépendances FastAPI d'authentification."""
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.messages.errors import EXPIRED_JWT_TOKEN, INVALID_JWT_TOKEN
from app.security.jwt import decode_access_token

#: Extrait le jeton de l'en-tête ``Authorization: Bearer <token>``.
#: Renvoie 403 si l'en-tête est absent.
bearer_scheme = HTTPBearer()


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Authentifie l'appelant à partir de son JWT.

    Returns:
        Le payload décodé du jeton (contient au minimum ``sub``).

    Raises:
        HTTPException: 401 si le jeton est expiré, invalide ou sans ``sub``.
    """
    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise _unauthorized(EXPIRED_JWT_TOKEN)
    except jwt.InvalidTokenError:
        raise _unauthorized(INVALID_JWT_TOKEN)

    if payload.get("sub") is None:
        raise _unauthorized(INVALID_JWT_TOKEN)

    return payload
