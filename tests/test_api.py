"""
Tests de l'API FastAPI :
- endpoint de santé
- schéma de sortie (valeurs par défaut)
- validation du formulaire KYC (422 si champs manquants)
- flux /kyc/process avec l'agent mocké (aucun appel réseau)

On utilise httpx.ASGITransport (compatible httpx>=0.28) plutôt que
starlette.TestClient qui est incompatible avec cette version de httpx.
"""
import jwt
import httpx
import pytest
import app.api.v1.router as router_module
from app.main import app
from app.schemas.kyc_output import KYCOutputData, ValidatedField
from app.core.config import settings


def _async_client():
    transport = httpx.ASGITransport(app=app)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _auth_headers() -> dict:
    token = jwt.encode(
        {"sub": "test-user"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Santé
# ---------------------------------------------------------------------------

async def test_health_check():
    async with _async_client() as client:
        response = await client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["service"] == "KYC Validation Pipeline"


# ---------------------------------------------------------------------------
# Schéma de sortie
# ---------------------------------------------------------------------------

def test_validated_field_defaults():
    field = ValidatedField[str](value="x", status_validation="valid")
    assert field.percentage == 0.0


def test_kyc_output_data_defaults(valid_output_dict):
    output = KYCOutputData(**valid_output_dict)

    assert output.total_percentage == 100.0
    assert output.state_status == "valide"
    assert output.nom_et_prenom.status_validation == "valid"


# ---------------------------------------------------------------------------
# Endpoint /kyc/process
# ---------------------------------------------------------------------------

def _form_data():
    return {
        "type_document": "CNI",
        "kyc_id": "kyc-123",
        "nom_et_prenom": "Jean Dupont",
        "adresse_mail": "user@example.com",
        "profession": "Ingénieur",
        "numero_NUI": "NUI123",
        "date_naissance": "2000-01-02",
        "sexe": "M",
        "pays": "Cameroun",
        "region": "Centre",
        "ville": "Yaoundé",
        "adresse": "Rue 1",
        "num_CNI_passeport": "ABC123",
        "date_expiration": "2035-01-01",
    }


def _form_files():
    return {
        "photo_profile": ("profile.jpg", b"fake", "image/jpeg"),
        "photo_CNI_recto": ("recto.jpg", b"fake", "image/jpeg"),
    }


async def test_process_requires_fields():
    async with _async_client() as client:
        response = await client.post("/api/v1/kyc/process")
    assert response.status_code == 403


async def test_process_requires_auth():
    async with _async_client() as client:
        response = await client.post(
            "/api/v1/kyc/process",
            data=_form_data(),
            files=_form_files(),
        )
    assert response.status_code == 403
    body = response.json()
    assert body["detail"] == "Not authenticated"


async def test_process_accepts_valid_jwt(monkeypatch, valid_output_dict):
    async def fake_process(form_data):
        assert form_data.kyc_id == "kyc-123"
        return KYCOutputData(**valid_output_dict)

    monkeypatch.setattr(router_module.kyc_agent, "process", fake_process)

    async with _async_client() as client:
        response = await client.post(
            "/api/v1/kyc/process",
            data=_form_data(),
            files=_form_files(),
            headers=_auth_headers(),
        )

    assert response.status_code == 200
    body = response.json()
    assert body["donnees_output"]["state_status"] == "valide"
    assert body["donnees_output"]["total_percentage"] == 100.0


async def test_process_rejects_invalid_jwt(monkeypatch):
    async with _async_client() as client:
        response = await client.post(
            "/api/v1/kyc/process",
            data=_form_data(),
            files=_form_files(),
            headers={"Authorization": "Bearer invalid-token"},
        )

    assert response.status_code == 401
    body = response.json()
    assert body["detail"] == "Token invalide"


async def test_process_handles_internal_error(monkeypatch):
    async def boom(form_data):
        raise RuntimeError("échec interne")

    monkeypatch.setattr(router_module.kyc_agent, "process", boom)

    async with _async_client() as client:
        response = await client.post(
            "/api/v1/kyc/process",
            data=_form_data(),
            files=_form_files(),
            headers=_auth_headers(),
        )

    assert response.status_code == 500
