"""
Configuration et fixtures partagées pour la suite de tests.

IMPORTANT : on charge les variables d'environnement AVANT d'importer
tout module de `app`, car `app.core.config` évalue certaines variables
(dont KYC_CALLBACK_TIMEOUT) dès l'import. On fournit aussi des valeurs
de repli pour que les tests tournent même sans fichier .env.
"""
import os
import pytest
from types import SimpleNamespace
from dotenv import load_dotenv

load_dotenv()

os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key")
os.environ.setdefault("KYC_CALLBACK_URL", "http://callback.test/kyc/callback")
os.environ.setdefault("KYC_CALLBACK_TOKEN", "test-token")
os.environ.setdefault("KYC_CALLBACK_TIMEOUT", "5")

# ---------------------------------------------------------------------------
# Fabriques de données de test
# ---------------------------------------------------------------------------

# Tous les champs analysés (identique à KYCAgent.ALL_FIELDS)
ALL_FIELDS = [
    "photo_profile",
    "nom_et_prenom",
    "adresse_mail",
    "profession",
    "numero_NUI",
    "registre_commerce",
    "date_naissance",
    "sexe",
    "pays",
    "region",
    "ville",
    "adresse",
    "code_postal",
    "num_CNI_passeport",
    "date_expiration",
    "photo_CNI_recto",
    "photo_CNI_verso",
    "photo_passeport",
]


def _make_raw_output(status_overrides=None):
    """
    Construit un dictionnaire raw_output complet (les 18 champs),
    tous 'valid' par défaut, avec surcharges de statut optionnelles.
    """
    status_overrides = status_overrides or {}
    raw = {}
    for field in ALL_FIELDS:
        raw[field] = {
            "value": "fourni" if field.startswith("photo") else f"valeur_{field}",
            "status_validation": status_overrides.get(field, "valid"),
        }
    return raw


def _make_form(type_document="CNI", **kwargs):
    """Objet léger imitant KYCFormData pour les méthodes de l'agent."""
    defaults = dict(
        type_document=type_document,
        kyc_id="kyc-123",
        adresse_mail="user@example.com",
        nom_et_prenom="Jean Dupont",
        date_naissance="2000-01-01",
        date_expiration="2035-01-01",
        sexe="M",
        num_CNI_passeport="ABC123",
        pays="Cameroun",
        region="Centre",
        ville="Yaoundé",
        adresse="Rue 1",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


@pytest.fixture
def raw_output_factory():
    return _make_raw_output


@pytest.fixture
def form_factory():
    return _make_form


@pytest.fixture
def valid_output_dict():
    """
    Dictionnaire complet et cohérent pour instancier un KYCOutputData
    (tous champs valides, métadonnées incluses).
    """
    raw = _make_raw_output()
    for field in ALL_FIELDS:
        raw[field]["percentage"] = 0.0
    raw["total_percentage"] = 100.0
    raw["state_status"] = "valide"
    return raw
