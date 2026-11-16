"""
Tests de l'orchestration KYC avec toutes les dépendances externes mockées
(lecture d'images, modèle de vision, InsightFace, mail, callback).
Aucun appel réseau réel.
"""
from types import SimpleNamespace
import pytest
from app.agents.kyc_agent import KYCAgent
from app.core.exceptions import VisionAnalysisError
from app.domain.kyc.prompts import build_kyc_validation_prompt
from app.domain.kyc.reasons import collect_invalid_fields
from app.domain.kyc.scoring import compute_scores
from app.schemas.kyc_output import DocumentQualityRejection, KYCOutputData
from app.services.kyc_notifier import KYCNotifier
from tests.conftest import _make_raw_output


@pytest.fixture
def agent():
    return KYCAgent()


@pytest.fixture
def notifier():
    return KYCNotifier()


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
# build_kyc_validation_prompt
# ---------------------------------------------------------------------------

def test_build_user_prompt_contains_declared_values():
    form = _full_form()
    prompt = build_kyc_validation_prompt(form)

    assert "Jean Dupont" in prompt
    assert "ABC123" in prompt
    assert "status_validation" in prompt


# ---------------------------------------------------------------------------
# KYCNotifier.send_warning_email
# ---------------------------------------------------------------------------

async def test_notify_invalid_fields_sends_mail(notifier, monkeypatch, raw_output_factory, form_factory):
    sent = {}

    def fake_send_email(**kwargs):
        sent.update(kwargs)
        return True

    monkeypatch.setattr(notifier.mailer, "send_email", fake_send_email)

    raw = raw_output_factory({"nom_et_prenom": "invalid"})
    form = form_factory(type_document="CNI")
    await notifier.send_warning_email(raw, form, collect_invalid_fields(raw, form))

    assert sent["template_name"] == "warning"
    assert sent["email_to"] == "user@example.com"
    assert "Nom et prénom" in sent["invalid_fields"]


async def test_notify_invalid_fields_no_mail_when_all_valid(notifier, monkeypatch, raw_output_factory, form_factory):
    calls = []
    def fake_send_email(**k):
        calls.append(k)
        return True
    monkeypatch.setattr(notifier.mailer, "send_email", fake_send_email)

    raw = raw_output_factory()
    form = form_factory(type_document="CNI")
    await notifier.send_warning_email(raw, form, collect_invalid_fields(raw, form))

    assert calls == []


async def test_notify_invalid_fields_swallows_mail_errors(notifier, monkeypatch, raw_output_factory, form_factory):
    def boom(**kwargs):
        raise Exception("SMTP down")

    monkeypatch.setattr(notifier.mailer, "send_email", boom)

    raw = raw_output_factory({"sexe": "invalid"})
    form = form_factory(type_document="CNI")
    await notifier.send_warning_email(raw, form, collect_invalid_fields(raw, form))


async def test_notify_escapes_user_supplied_name(notifier, monkeypatch, raw_output_factory, form_factory):
    sent = {}
    monkeypatch.setattr(notifier.mailer, "send_email", lambda **k: sent.update(k))

    raw = raw_output_factory({"sexe": "invalid"})
    form = form_factory(type_document="CNI", nom_et_prenom="<script>x</script>")
    await notifier.send_warning_email(raw, form, collect_invalid_fields(raw, form))

    assert "<script>" not in sent["user_name"]


# ---------------------------------------------------------------------------
# KYCNotifier.send_callback
# ---------------------------------------------------------------------------

async def test_send_callback_passes_score_and_reason(notifier, monkeypatch, raw_output_factory, form_factory):
    captured = {}

    async def fake_notify(**kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(notifier.callback, "notify", fake_notify)

    raw = raw_output_factory({"num_CNI_passeport": "invalid"})
    form = form_factory(type_document="CNI", kyc_id="abc")
    compute_scores(raw, form)
    await notifier.send_callback(raw, form, collect_invalid_fields(raw, form))

    assert captured["kyc_id"] == "abc"
    assert captured["ai_confidence_score"] == raw["total_percentage"]
    assert "Numéro CNI / Passeport" in captured["rejection_reason"]


# ---------------------------------------------------------------------------
# process (bout en bout, dépendances mockées)
# ---------------------------------------------------------------------------

async def test_process_end_to_end(agent, monkeypatch):
    async def fake_get_bytes(upload):
        return b"image-bytes"

    monkeypatch.setattr(agent.image_loader, "get_image_bytes", fake_get_bytes)
    monkeypatch.setattr(
        agent.face_matcher,
        "compare",
        lambda a, b, threshold=0.5: (True, 0.1),
    )
    monkeypatch.setattr(
        agent.vision_engine,
        "analyze_json",
        lambda **kwargs: _make_raw_output({"photo_profile": "invalid", "nom_et_prenom": "invalid", "num_CNI_passeport": "invalid"}),
    )
    monkeypatch.setattr(
        agent.vision_engine,
        "check_blur",
        lambda images: (False, []),
    )

    mail_calls = []
    def fake_send_email(**k):
        mail_calls.append(k)
        return True
    monkeypatch.setattr(agent.notifier.mailer, "send_email", fake_send_email)

    callback_calls = []

    async def fake_notify(**kwargs):
        callback_calls.append(kwargs)
        return True

    monkeypatch.setattr(agent.notifier.callback, "notify", fake_notify)

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

    monkeypatch.setattr(agent.image_loader, "get_image_bytes", fake_get_bytes)
    monkeypatch.setattr(
        agent.vision_engine,
        "check_blur",
        lambda images: (False, []),
    )
    form = _full_form(type_document="CNI", photo_CNI_recto=None, photo_CNI_verso=None)

    with pytest.raises(ValueError):
        await agent.process(form)


async def test_process_returns_rejection_when_document_is_blurry(agent, monkeypatch):
    async def fake_get_bytes(upload):
        return b"image-bytes"

    monkeypatch.setattr(agent.image_loader, "get_image_bytes", fake_get_bytes)
    monkeypatch.setattr(agent.vision_engine, "check_blur", lambda images: (True, ["Document principal : flou"]))

    result = await agent.process(_full_form(type_document="CNI"))

    assert isinstance(result, DocumentQualityRejection)
    assert result.reasons == ["Document principal : flou"]


async def test_process_fails_closed_when_vision_returns_nothing(agent, monkeypatch):
    """Un incident du modèle de vision ne doit jamais valider un dossier par défaut."""
    async def fake_get_bytes(upload):
        return b"image-bytes"

    monkeypatch.setattr(agent.image_loader, "get_image_bytes", fake_get_bytes)
    monkeypatch.setattr(agent.vision_engine, "check_blur", lambda images: (False, []))
    monkeypatch.setattr(agent.vision_engine, "analyze_json", lambda **kwargs: {})

    with pytest.raises(VisionAnalysisError):
        await agent.process(_full_form(type_document="CNI"))
