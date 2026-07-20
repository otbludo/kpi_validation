"""
Tests de bout en bout de KYCAgent avec toutes les dépendances externes
mockées (OCR, moteur Groq, mail, callback). Aucun appel réseau réel.
"""
from types import SimpleNamespace
import pytest
import app.agents.kyc_agent as agent_module
from app.agents.kyc_agent import KYCAgent
from app.services.insightface import insightface_engine
from app.services.blur_detection import blur_detection_service
from app.schemas.kyc_output import KYCOutputData
from tests.conftest import ALL_FIELDS, _make_raw_output


@pytest.fixture
def agent():
    return KYCAgent()


def _full_form(type_document="CNI", **overrides):
    """Formulaire complet (tous les attributs utilisés par l'agent)."""
    data = dict(
        type_document=type_document,
        kyc_id="kyc-999",
        nom_et_prenom="Jean Dupont",
        adresse_mail="user@example.com",
        profession="Ingénieur",
        numero_NUI="NUI1",
        registre_commerce="RC1",
        date_naissance="2000-01-02",
        sexe="M",
        pays="Cameroun",
        region="Centre",
        ville="Yaoundé",
        adresse="Rue 1",
        code_postal="0000",
        num_CNI_passeport="ABC123",
        date_expiration="2035-01-01",
        photo_profile=object(),
        photo_CNI_recto=object(),
        photo_CNI_verso=object(),
        photo_passeport=None,
    )
    data.update(overrides)
    return SimpleNamespace(**data)


# ---------------------------------------------------------------------------
# _build_user_prompt
# ---------------------------------------------------------------------------

def test_build_user_prompt_contains_declared_values(agent):
    form = _full_form()
    prompt = agent._build_user_prompt(form)

    assert "Jean Dupont" in prompt
    assert "ABC123" in prompt
    assert "status_validation" in prompt


# ---------------------------------------------------------------------------
# _notify_invalid_fields
# ---------------------------------------------------------------------------

async def test_notify_invalid_fields_sends_mail(agent, monkeypatch, raw_output_factory, form_factory):
    sent = {}

    async def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(agent_module.mailService, "send_email", fake_send_email)

    raw = raw_output_factory({"nom_et_prenom": "invalid"})
    await agent._notify_invalid_fields(raw, form_factory(type_document="CNI"))

    assert sent["template_name"] == "warning"
    assert sent["email_to"] == "user@example.com"
    assert "Nom et prénom" in sent["invalid_fields"]


async def test_notify_invalid_fields_no_mail_when_all_valid(agent, monkeypatch, raw_output_factory, form_factory):
    calls = []
    async def fake_send_email(**k):
        calls.append(k)
        return True
    monkeypatch.setattr(agent_module.mailService, "send_email", fake_send_email)

    raw = raw_output_factory()
    await agent._notify_invalid_fields(raw, form_factory(type_document="CNI"))

    assert calls == []


async def test_notify_invalid_fields_swallows_mail_errors(agent, monkeypatch, raw_output_factory, form_factory):
    async def boom(**kwargs):
        raise Exception("SMTP down")

    monkeypatch.setattr(agent_module.mailService, "send_email", boom)

    raw = raw_output_factory({"sexe": "invalid"})
    await agent._notify_invalid_fields(raw, form_factory(type_document="CNI"))


# ---------------------------------------------------------------------------
# _send_callback
# ---------------------------------------------------------------------------

async def test_send_callback_passes_score_and_reason(agent, monkeypatch, raw_output_factory, form_factory):
    captured = {}

    async def fake_notify(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(agent_module.kyc_callback_service, "notify", fake_notify)

    raw = raw_output_factory({"num_CNI_passeport": "invalid"})
    agent._compute_percentages(raw, form_factory(type_document="CNI"))
    await agent._send_callback(raw, form_factory(type_document="CNI", kyc_id="abc"))

    assert captured["kyc_id"] == "abc"
    assert captured["ai_confidence_score"] == raw["total_percentage"]
    assert "Numéro CNI / Passeport" in captured["rejection_reason"]


# ---------------------------------------------------------------------------
# process (bout en bout, dépendances mockées)
# ---------------------------------------------------------------------------

async def test_process_end_to_end(agent, monkeypatch):
    async def fake_get_bytes(upload):
        return b"image-bytes"

    monkeypatch.setattr(agent_module.ocr_engine, "get_image_bytes", fake_get_bytes)
    monkeypatch.setattr(
        insightface_engine,
        "compare",
        lambda a, b, threshold=0.5: (True, 0.1),
    )
    monkeypatch.setattr(
        agent.vision_engine,
        "analyze_json",
        lambda **kwargs: _make_raw_output({"photo_profile": "invalid", "nom_et_prenom": "invalid", "num_CNI_passeport": "invalid"}),
    )
    monkeypatch.setattr(
        blur_detection_service,
        "check_images",
        lambda images_bytes: (False, []),
    )

    mail_calls = []
    async def fake_send_email(**k):
        mail_calls.append(k)
        return True
    monkeypatch.setattr(agent_module.mailService, "send_email", fake_send_email)

    callback_calls = []

    async def fake_notify(**kwargs):
        callback_calls.append(kwargs)
        return True

    monkeypatch.setattr(agent_module.kyc_callback_service, "notify", fake_notify)

    result = await agent.process(_full_form(type_document="CNI"))

    assert isinstance(result, KYCOutputData)
    assert result.state_status == "invalide"
    assert result.total_percentage == 20.0
    assert result.nom_et_prenom.status_validation == "invalid"
    assert result.numero_NUI.status_validation == "valid"
    assert len(mail_calls) == 1
    assert len(callback_calls) == 1
    assert callback_calls[0]["kyc_id"] == "kyc-999"


async def test_process_raises_when_no_image(agent, monkeypatch):
    async def fake_get_bytes(upload):
        return b""

    monkeypatch.setattr(agent_module.ocr_engine, "get_image_bytes", fake_get_bytes)
    monkeypatch.setattr(
        blur_detection_service,
        "check_images",
        lambda images_bytes: (False, []),
    )
    form = _full_form(type_document="CNI", photo_CNI_recto=None, photo_CNI_verso=None)

    with pytest.raises(ValueError):
        await agent.process(form)
