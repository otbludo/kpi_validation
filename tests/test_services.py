"""
Tests des services :
- OpenRouterVisionEngine : analyse JSON via OpenRouter (Llama 4 Scout)
- KYCCallbackService : envoi du callback (httpx mocké)
- OCREngine : lecture des octets d'un UploadFile
"""
import os
import json
import base64
import pytest
from types import SimpleNamespace
import app.services.kyc_callback as cb_module
from app.services.openrouter_vision import OpenRouterVisionEngine
from app.services.kyc_callback import KYCCallbackService
from app.services.ocr_engine import ocr_engine


# ---------------------------------------------------------------------------
# OpenRouterVisionEngine
# ---------------------------------------------------------------------------

def test_build_message_content_mixes_text_and_images():
    engine = OpenRouterVisionEngine(api_key="test-key")
    content = engine._build_message_content(
        "mon prompt",
        images=[b"raw-bytes", b"other-bytes"],
    )

    assert content[0] == {"type": "text", "text": "mon prompt"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(content[1]["image_url"]["url"].split(",", 1)[1]) == b"raw-bytes"
    assert base64.b64decode(content[2]["image_url"]["url"].split(",", 1)[1]) == b"other-bytes"


def test_build_message_content_without_images():
    engine = OpenRouterVisionEngine(api_key="test-key")
    content = engine._build_message_content("prompt seul", images=None)

    assert len(content) == 1
    assert content[0]["type"] == "text"


def test_analyze_json_returns_parsed_dict(monkeypatch):
    class _FakeResponse:
        class _Choice:
            class _Message:
                content = '{"status": "ok"}'
            message = _Message()
        choices = [_Choice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr("app.services.openrouter_vision.OpenAI", lambda **kwargs: _FakeClient(**kwargs))
    engine = OpenRouterVisionEngine(api_key="test-key")

    result = engine.analyze_json("prompt", images=[b"img"])

    assert result == {"status": "ok"}


def test_analyze_json_returns_empty_dict_on_error(monkeypatch):
    class _FakeCompletions:
        def create(self, **kwargs):
            raise Exception("network error")

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr("app.services.openrouter_vision.OpenAI", lambda **kwargs: _FakeClient(**kwargs))
    engine = OpenRouterVisionEngine(api_key="test-key")

    result = engine.analyze_json("prompt", images=[b"img"])

    assert result == {}


def test_analyze_json_passes_correct_config(monkeypatch):
    captured = {}

    class _FakeResponse:
        class _Choice:
            class _Message:
                content = '{"ok": true}'
            message = _Message()
        choices = [_Choice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            captured.update(kwargs)
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, *args, **kwargs):
            self.chat = _FakeChat()

    monkeypatch.setattr("app.services.openrouter_vision.OpenAI", lambda **kwargs: _FakeClient(**kwargs))
    engine = OpenRouterVisionEngine(api_key="test-key")

    result = engine.analyze_json("mon prompt", images=[b"img1", b"img2"])

    assert result == {"ok": True}
    assert captured["model"] == "meta-llama/llama-4-scout"
    assert captured["temperature"] == 0.0
    assert captured["response_format"] == {"type": "json_object"}


def test_analyze_json_uses_openrouter_base_url(monkeypatch):
    init_kwargs = {}

    class _FakeResponse:
        class _Choice:
            class _Message:
                content = '{"ok": true}'
            message = _Message()
        choices = [_Choice()]

    class _FakeCompletions:
        def create(self, **kwargs):
            return _FakeResponse()

    class _FakeChat:
        completions = _FakeCompletions()

    class _FakeClient:
        def __init__(self, **kwargs):
            init_kwargs.update(kwargs)
            self.chat = _FakeChat()

    monkeypatch.setattr("app.services.openrouter_vision.OpenAI", lambda **kwargs: _FakeClient(**kwargs))
    engine = OpenRouterVisionEngine(api_key="test-key")
    engine.analyze_json("prompt", images=[b"img"])

    assert init_kwargs["base_url"] == "https://openrouter.ai/api/v1"
    assert init_kwargs["api_key"] == "test-key"


def test_extract_json_parses_pure_json():
    assert OpenRouterVisionEngine._extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_parses_json_in_text():
    raw = "Voici le résultat : {\"status\": \"ok\", \"value\": 42} Merci."
    assert OpenRouterVisionEngine._extract_json(raw) == {"status": "ok", "value": 42}


def test_extract_json_returns_empty_on_no_json():
    assert OpenRouterVisionEngine._extract_json("pas de json ici") == {}


# ---------------------------------------------------------------------------
# KYCCallbackService (httpx mocké)
# ---------------------------------------------------------------------------

class _FakeResponse:
    def __init__(self, raise_exc=False):
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc:
            raise Exception("HTTP error")


class _FakeAsyncClient:
    captured = {}
    should_fail = False

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, json=None, headers=None):
        _FakeAsyncClient.captured = {"url": url, "json": json, "headers": headers}
        if _FakeAsyncClient.should_fail:
            raise Exception("connexion impossible")
        return _FakeResponse()


@pytest.fixture
def fake_httpx(monkeypatch):
    _FakeAsyncClient.captured = {}
    _FakeAsyncClient.should_fail = False
    monkeypatch.setattr(cb_module.httpx, "AsyncClient", _FakeAsyncClient)
    return _FakeAsyncClient


async def test_callback_notify_success_builds_payload_and_bearer(fake_httpx):
    service = KYCCallbackService(url="http://cb.test/kyc/callback", token="secret", timeout=1)

    ok = await service.notify(kyc_id="kyc-1", ai_confidence_score=88.24, rejection_reason="raison")

    assert ok is True
    captured = fake_httpx.captured
    assert captured["url"] == "http://cb.test/kyc/callback"
    assert captured["json"] == {
        "kyc_id": "kyc-1",
        "ai_confidence_score": 88.24,
        "rejection_reason": "raison",
    }
    assert captured["headers"]["Authorization"] == "Bearer secret"


async def test_callback_notify_without_token_has_no_auth_header(fake_httpx):
    service = KYCCallbackService(url="http://cb.test/kyc/callback", token="x", timeout=1)
    service.token = ""

    ok = await service.notify(kyc_id="kyc-2", ai_confidence_score=100.0)

    assert ok is True
    assert "Authorization" not in fake_httpx.captured["headers"]


async def test_callback_notify_returns_false_on_failure(fake_httpx):
    fake_httpx.should_fail = True
    service = KYCCallbackService(url="http://cb.test/kyc/callback", token="x", timeout=1)

    ok = await service.notify(kyc_id="kyc-3", ai_confidence_score=0.0)

    assert ok is False


# ---------------------------------------------------------------------------
# OCREngine
# ---------------------------------------------------------------------------

class _FakeUpload:
    def __init__(self, data: bytes):
        self._data = data
        self.seeked_to = None

    async def read(self):
        return self._data

    async def seek(self, pos):
        self.seeked_to = pos


async def test_ocr_get_image_bytes_reads_and_rewinds():
    upload = _FakeUpload(b"image-bytes")

    result = await ocr_engine.get_image_bytes(upload)

    assert result == b"image-bytes"
    assert upload.seeked_to == 0


async def test_ocr_get_image_bytes_returns_empty_for_none():
    assert await ocr_engine.get_image_bytes(None) == b""
