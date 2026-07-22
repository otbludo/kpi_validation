"""
Tests du module security :
- création et décodage d'un JWT valide
- rejet d'un token expiré
- rejet d'un token invalide
- support de JWT_EXPIRE_MINUTES=None (token sans expiration)
"""
import jwt
import pytest
from datetime import timedelta
from app.security.jwt import create_access_token, decode_access_token
from app.core.config import settings


def test_create_access_token_contains_sub_and_exp(monkeypatch):
    monkeypatch.setattr(settings, "JWT_EXPIRE_MINUTES", 60)
    token = create_access_token({"sub": "user-123"})
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    assert payload["sub"] == "user-123"
    assert "exp" in payload


def test_create_access_token_without_expiration_when_disabled(monkeypatch):
    monkeypatch.setattr(settings, "JWT_EXPIRE_MINUTES", None)
    token = create_access_token({"sub": "user-123"})
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    assert payload["sub"] == "user-123"
    assert "exp" not in payload


def test_decode_access_token_returns_payload():
    token = create_access_token({"sub": "user-123"})
    payload = decode_access_token(token)

    assert payload["sub"] == "user-123"


def test_create_access_token_with_custom_expiry(monkeypatch):
    monkeypatch.setattr(settings, "JWT_EXPIRE_MINUTES", 60)
    token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(minutes=5))
    payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

    assert "exp" in payload


def test_decode_access_token_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(settings, "JWT_EXPIRE_MINUTES", 60)
    token = create_access_token({"sub": "user-123"}, expires_delta=timedelta(minutes=-1))

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_decode_access_token_rejects_invalid_token():
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token("not-a-valid-token")


def test_decode_access_token_rejects_wrong_secret():
    token = jwt.encode(
        {"sub": "user-123"},
        "wrong-secret",
        algorithm=settings.JWT_ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)
