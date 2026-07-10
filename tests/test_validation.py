"""
Tests de la logique de validation de KYCAgent :
- répartition des pourcentages (_compute_percentages)
- état global (state_status) et score (total_percentage)
- détection des champs invalides et raison du rejet
"""
import pytest
from app.agents.kyc_agent import KYCAgent


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
    assert raw["nom_et_prenom"]["percentage"] == 5.88
    assert raw["photo_passeport"]["percentage"] == 0.0


def test_passeport_excludes_cni_photos(agent, raw_output_factory, form_factory):
    raw = raw_output_factory()
    form = form_factory(type_document="passeport")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 100.0
    assert raw["state_status"] == "valide"
    assert raw["nom_et_prenom"]["percentage"] == 6.25
    assert raw["photo_CNI_recto"]["percentage"] == 0.0
    assert raw["photo_CNI_verso"]["percentage"] == 0.0
    assert raw["photo_passeport"]["percentage"] == 6.25


def test_invalid_fields_reduce_total_and_set_invalide(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"nom_et_prenom": "invalid", "sexe": "invalid"})
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == pytest.approx(round(15 / 17 * 100, 2))
    assert raw["state_status"] == "invalide"


def test_excluded_field_invalid_does_not_affect_score(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"photo_passeport": "invalid"})
    form = form_factory(type_document="CNI")

    agent._compute_percentages(raw, form)

    assert raw["total_percentage"] == 100.0
    assert raw["state_status"] == "valide"


# ---------------------------------------------------------------------------
# _get_invalid_field_labels / _build_rejection_reason
# ---------------------------------------------------------------------------

def test_get_invalid_field_labels_uses_readable_labels(agent, raw_output_factory, form_factory):
    raw = raw_output_factory({"nom_et_prenom": "invalid", "date_naissance": "invalid"})
    form = form_factory(type_document="CNI")

    labels = agent._get_invalid_field_labels(raw, form)

    assert "Nom et prénom" in labels
    assert "Date de naissance" in labels
    assert len(labels) == 2


def test_get_invalid_field_labels_ignores_excluded_fields(agent, raw_output_factory, form_factory):
    # En mode passeport, un recto CNI 'invalid' ne doit pas être remonté
    raw = raw_output_factory({"photo_CNI_recto": "invalid"})
    form = form_factory(type_document="passeport")

    labels = agent._get_invalid_field_labels(raw, form)

    assert labels == []


def test_build_rejection_reason_empty_when_no_invalid(agent):
    assert agent._build_rejection_reason([]) == ""


def test_build_rejection_reason_lists_fields(agent):
    reason = agent._build_rejection_reason(["Nom et prénom", "Sexe"])

    assert "Nom et prénom" in reason
    assert "Sexe" in reason
    assert reason.endswith(".")
