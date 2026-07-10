"""
Tests des services :
- GroqVisionEngine : helpers (base64, nettoyage, construction du message)
- KYCCallbackService : envoi du callback (httpx mocké)
- OCREngine : lecture des octets d'un UploadFile
"""
import base64
import pytest
from types import SimpleNamespace
import app.services.kyc_callback as cb_module
from app.services.groq_vision import GroqVisionEngine
from app.services.kyc_callback import KYCCallbackService
from app.services.ocr_engine import ocr_engine


# ---------------------------------------------------------------------------
# GroqVisionEngine
# ---------------------------------------------------------------------------

def test_bytes_to_base64_url_prefix_and_content():
    data = b"hello-image"
    url = GroqVisionEngine.bytes_to_base64_url(data)

    assert url.startswith("data:image/jpeg;base64,")
    encoded = url.split(",", 1)[1]
    assert base64.b64decode(encoded) == data


def test_clean_content_strips_json_fence():
    raw = '```json\n{"a": 1}\n```'
    assert GroqVisionEngine._clean_content(raw) == '{"a": 1}'


def test_clean_content_strips_plain_fence():
    raw = '```\n{"a": 1}\n```'
    assert GroqVisionEngine._clean_content(raw) == '{"a": 1}'


def test_clean_content_leaves_plain_text():
    raw = '{"a": 1}'
    assert GroqVisionEngine._clean_content(raw) == '{"a": 1}'


def test_build_message_content_mixes_text_and_images():
    engine = GroqVisionEngine(api_key="test-key")
    content = engine._build_message_content(
        "mon prompt",
        images=[b"raw-bytes", "data:image/png;base64,AAAA"],
    )

    assert content[0] == {"type": "text", "text": "mon prompt"}
    assert content[1]["type"] == "image_url"
    assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert content[2]["image_url"]["url"] == "data:image/png;base64,AAAA"


def test_build_message_content_without_images():
    engine = GroqVisionEngine(api_key="test-key")
    content = engine._build_message_content("prompt seul", images=None)

    assert len(content) == 1
    assert content[0]["type"] == "text"


class _FakeGroqClient:
    """Client Groq factice capturant les kwargs et renvoyant un contenu fixe."""
    def __init__(self, content):
        self._content = content
        self.captured = {}
        outer = self

        class _Completions:
            def create(self, **kwargs):
                outer.captured = kwargs
                message = SimpleNamespace(content=outer._content)
                choice = SimpleNamespace(message=message)
                return SimpleNamespace(choices=[choice])

        self.chat = SimpleNamespace(completions=_Completions())


def test_analyze_returns_cleaned_content():
    engine = GroqVisionEngine(api_key="test-key")
    engine.client = _FakeGroqClient('```json\n{"x": 1}\n```')

    result = engine.analyze("prompt", images=[b"img"])

    assert result == '{"x": 1}'
    assert engine.client.captured["response_format"] == {"type": "json_object"}
    assert engine.client.captured["temperature"] == 0.0


def test_analyze_json_parses_dict():
    engine = GroqVisionEngine(api_key="test-key")
    engine.client = _FakeGroqClient('{"a": 1, "b": "ok"}')

    result = engine.analyze_json("prompt")

    assert result == {"a": 1, "b": "ok"}


def test_analyze_without_json_mode_omits_response_format():
    engine = GroqVisionEngine(api_key="test-key")
    engine.client = _FakeGroqClient('texte libre')

    result = engine.analyze("prompt", json_mode=False)

    assert result == "texte libre"
    assert "response_format" not in engine.client.captured



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
    """Client httpx factice qui capture le dernier appel POST."""
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
