"""
Tests de la logique de validation de KYCAgent :
- application des pénalités (_compute_percentages)
- état global (state_status) et score (total_percentage)
- détection des champs invalides et raison du rejet
"""
import pytest
from app.agents.kyc_agent import KYCAgent
import app.agents.kyc_agent as agent_module


@pytest.fixture
def agent():
    return KYCAgent()


# ---------------------------------------------------------------------------
# _compute_percentages
# ---------------------------------------------------------------------------

def test_cni_all_valid_gives_100_and_valide(agent, raw_output_factory, form_factory):
    raw = raw_output_factory()
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 100.0
    assert raw["state_status"] == "valide"
    assert raw["nom_et_prenom"]["percentage"] == 0.0
    assert raw["photo_passeport"]["percentage"] == 0.0


def test_passeport_excludes_cni_photos(agent, raw_output_factory, form_factory):
    raw = raw_output_factory()
    form = form_factory(type_document="passeport")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 100.0
    assert raw["state_status"] == "valide"
    assert raw["nom_et_prenom"]["percentage"] == 0.0
    assert raw["photo_CNI_recto"]["percentage"] == 0.0
    assert raw["photo_CNI_verso"]["percentage"] == 0.0
    assert raw["photo_passeport"]["percentage"] == 0.0


def test_invalid_fields_reduce_total_and_set_invalide(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"nom_et_prenom": "invalid", "sexe": "invalid"})
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 40.0
    assert raw["state_status"] == "invalide"


def test_excluded_field_invalid_does_not_affect_score(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"photo_passeport": "invalid"})
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 100.0
    assert raw["state_status"] == "valide"


def test_penalty_fields_invalid_set_percentage_to_penalty(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"photo_profile": "invalid", "num_CNI_passeport": "invalid"})
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 0.0
    assert raw["state_status"] == "invalide"
    assert raw["photo_profile"]["percentage"] == 50
    assert raw["num_CNI_passeport"]["percentage"] == 50


def test_threshold_60_makes_valide(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"photo_profile": "invalid"})
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 50.0
    assert raw["state_status"] == "invalide"


def test_non_penalty_field_invalid_does_not_affect_score(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"adresse_mail": "invalid", "profession": "invalid"})
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 100.0
    assert raw["state_status"] == "valide"


# ---------------------------------------------------------------------------
# _get_invalid_field_labels / _build_rejection_reason
# ---------------------------------------------------------------------------

def test_get_invalid_fields_with_reasons_uses_readable_labels(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"nom_et_prenom": "invalid", "date_naissance": "invalid"})
    form = form_factory(type_document="CNI", date_naissance="07/05/200")

    fields = agent._get_invalid_fields_with_reasons(raw, form)

    assert len(fields) == 2
    assert {"label": "Nom et prénom", "reason": "Nom et prénom invalide (2 à 50 caractères alphabétiques requis)"} in fields
    assert {"label": "Date de naissance", "reason": "Format de date invalide (attendu: AAAA-MM-JJ ou JJ-MM-AAAA)"} in fields


def test_get_invalid_fields_with_reasons_ignores_excluded_fields(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"photo_CNI_recto": "invalid"})
    form = form_factory(type_document="passeport")

    fields = agent._get_invalid_fields_with_reasons(raw, form)

    assert fields == []


def test_build_rejection_reason_empty_when_no_invalid(agent):
    assert agent._build_rejection_reason([]) == ""


def test_build_rejection_reason_lists_fields_with_reasons(agent):
    reason = agent._build_rejection_reason([
        {"label": "Nom et prénom", "reason": "Nom et prénom invalide (2 à 50 caractères alphabétiques requis)"},
        {"label": "Sexe", "reason": "Valeur de sexe invalide (valeurs autorisées: M, F, Masculin, Féminin, Homme, Femme)"}
    ])

    assert "Nom et prénom" in reason
    assert "Sexe" in reason
    assert "Nom et prénom invalide (2 à 50 caractères alphabétiques requis)" in reason
    assert "Valeur de sexe invalide" in reason
    assert reason.endswith(".")


def test_process_adds_description_with_invalid_fields(agent, monkeypatch):
    async def fake_get_bytes(upload):
        return b"image-bytes"

    monkeypatch.setattr("app.services.ocr_engine.ocr_engine.get_image_bytes", fake_get_bytes)
    monkeypatch.setattr(
        "app.services.insightface.insightface_engine.compare",
        lambda a, b, threshold=0.5: (True, 0.1),
    )
    monkeypatch.setattr(
        agent.vision_engine,
        "analyze_json",
        lambda **kwargs: {
            "nom_et_prenom": {"value": "Jean Dupont", "status_validation": "valid"},
            "date_naissance": {"value": "2000-01-01", "status_validation": "valid"},
            "sexe": {"value": "M", "status_validation": "valid"},
            "pays": {"value": "Cameroun", "status_validation": "valid"},
            "region": {"value": "Centre", "status_validation": "valid"},
            "ville": {"value": "Yaoundé", "status_validation": "valid"},
            "num_CNI_passeport": {"value": "ABC123", "status_validation": "valid"},
            "date_expiration": {"value": "2000-01-01", "status_validation": "valid"},
        },
    )
    monkeypatch.setattr(
        agent_module.openrouter_vision,
        "check_blur",
        lambda images: (False, []),
    )

    mail_calls = []
    monkeypatch.setattr("app.services.mailtrap.mail_service.mailService.send_email", lambda **k: mail_calls.append(k))

    callback_calls = []
    async def fake_notify(**kwargs):
        callback_calls.append(kwargs)
        return True
    monkeypatch.setattr("app.services.kyc_callback.kyc_callback_service.notify", fake_notify)

    form = type('F', (), {
        'type_document': 'CNI',
        'kyc_id': 'kyc-999',
        'photo_profile': object(),
        'photo_CNI_recto': object(),
        'photo_CNI_verso': None,
        'photo_passeport': None,
        'nom_et_prenom': 'Jean Dupont',
        'date_naissance': '2000-01-01',
        'sexe': 'M',
        'pays': 'Cameroun',
        'region': 'Centre',
        'ville': 'Yaoundé',
        'num_CNI_passeport': 'ABC123',
        'date_expiration': '2000-01-01',
        'adresse_mail': 'user@example.com',
    })()

    import asyncio
    result = asyncio.get_event_loop().run_until_complete(agent.process(form))

    assert "Date d'expiration déjà passée" in result.description
    assert len(mail_calls) == 1
    assert "Date d'expiration déjà passée" in mail_calls[0]["invalid_fields"]
    assert len(callback_calls) == 1


# ---------------------------------------------------------------------------
# _apply_local_validations
# ---------------------------------------------------------------------------

def test_local_validation_invalid_date_naissance_format(agent, form_factory):
    form = form_factory(type_document="CNI", date_naissance="07/05/200")
    raw = {
        "date_naissance": {"value": "07/05/200", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["date_naissance"]["status_validation"] == "invalid"


def test_local_validation_valid_date_naissance_format(agent, form_factory):
    form = form_factory(type_document="CNI", date_naissance="2000-05-07")
    raw = {
        "date_naissance": {"value": "2000-05-07", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["date_naissance"]["status_validation"] == "valid"


def test_local_validation_valid_date_naissance_format_with_slash(agent, form_factory):
    form = form_factory(type_document="CNI", date_naissance="07/05/2003")
    raw = {
        "date_naissance": {"value": "07/05/2003", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["date_naissance"]["status_validation"] == "valid"


def test_local_validation_valid_date_naissance_format_with_dot(agent, form_factory):
    form = form_factory(type_document="CNI", date_naissance="07.05.2003")
    raw = {
        "date_naissance": {"value": "07.05.2003", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["date_naissance"]["status_validation"] == "valid"


def test_local_validation_invalid_date_expiration_past(agent, form_factory):
    form = form_factory(type_document="CNI", date_expiration="2000-01-01")
    raw = {
        "date_expiration": {"value": "2000-01-01", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["date_expiration"]["status_validation"] == "invalid"


def test_local_validation_valid_date_expiration_format_with_slash(agent, form_factory):
    form = form_factory(type_document="CNI", date_expiration="23/05/2037")
    raw = {
        "date_expiration": {"value": "23/05/2037", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["date_expiration"]["status_validation"] == "valid"


def test_local_validation_invalid_sexe(agent, form_factory):
    form = form_factory(type_document="CNI", sexe="X")
    raw = {
        "sexe": {"value": "X", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["sexe"]["status_validation"] == "invalid"


def test_local_validation_invalid_num_CNI_too_short(agent, form_factory):
    form = form_factory(type_document="CNI", num_CNI_passeport="A1")
    raw = {
        "num_CNI_passeport": {"value": "A1", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["num_CNI_passeport"]["status_validation"] == "invalid"


def test_local_validation_invalid_nom_et_prenom_empty(agent, form_factory):
    form = form_factory(type_document="CNI", nom_et_prenom="")
    raw = {
        "nom_et_prenom": {"value": "", "status_validation": "valid"}
    }
    agent._apply_local_validations(raw, form)
    assert raw["nom_et_prenom"]["status_validation"] == "invalid"
