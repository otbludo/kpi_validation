from pydantic import BaseModel, Field
from typing import Optional, Generic, TypeVar

T = TypeVar('T')

class ValidatedField(BaseModel, Generic[T]):
    value: T = Field(..., description="La valeur brute du champ analysé")
    status_validation: str = Field(..., description="Statut final ('valid' ou 'invalid')")
    percentage: float = Field(default=0.0, description="Pénalité appliquée si le champ est invalide (0 si valide ou non pris en compte)")

class KYCOutputData(BaseModel):
    photo_profile: ValidatedField[str]
    nom_et_prenom: ValidatedField[str]
    adresse_mail: ValidatedField[str]
    profession: ValidatedField[str]
    numero_NUI: ValidatedField[str]
    registre_commerce: ValidatedField[Optional[str]]
    date_naissance: ValidatedField[str]
    sexe: ValidatedField[str]
    pays: ValidatedField[str]
    region: ValidatedField[str]
    ville: ValidatedField[str]
    adresse: ValidatedField[str]
    code_postal: ValidatedField[Optional[str]]
    num_CNI_passeport: ValidatedField[str]
    date_expiration: ValidatedField[str]
    photo_CNI_recto: ValidatedField[str]
    photo_CNI_verso: ValidatedField[Optional[str]]
    photo_passeport: ValidatedField[Optional[str]]
    total_percentage: float = Field(default=0.0, description="Score global de validation (somme des parts des champs valides), sur 100")
    state_status: str = Field(default="valide", description="État global du dossier : 'valide' si tous les champs sont valides, sinon 'invalide'")
    description: str = Field(default="", description="Description des champs invalides et leurs raisons")

class KYCOutputResponse(BaseModel):
    donnees_output: KYCOutputData