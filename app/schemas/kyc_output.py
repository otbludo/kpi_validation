"""Modèles de réponse de l'endpoint de validation KYC."""
from typing import Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ValidatedField(BaseModel, Generic[T]):
    """Résultat de validation d'un champ unique."""

    value: T = Field(..., description="La valeur brute du champ analysé")
    status_validation: str = Field(
        ..., description="Statut final ('valid', 'invalid' ou 'not_required')"
    )
    percentage: float = Field(
        default=0.0,
        description="Pénalité appliquée si le champ est invalide (0 si valide ou non pris en compte)",
    )


class KYCOutputData(BaseModel):
    """Verdict complet d'un dossier : statut par champ, score et synthèse."""

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
    total_percentage: float = Field(
        default=0.0, description="Score global de confiance, sur 100 (100 moins les pénalités)"
    )
    state_status: str = Field(
        default="valide",
        description="État global du dossier : 'valide' si le score atteint le seuil, sinon 'invalide'",
    )
    description: str = Field(default="", description="Description des champs invalides et leurs raisons")


class KYCOutputResponse(BaseModel):
    """Enveloppe de la réponse en cas d'analyse complète."""

    donnees_output: KYCOutputData


class DocumentQualityRejection(BaseModel):
    """
    Réponse renvoyée quand les photos sont trop floues pour être analysées.

    Dans ce cas, aucune validation de champ n'est effectuée.
    """

    message: str = Field(..., description="Message destiné à l'utilisateur")
    reasons: List[str] = Field(default_factory=list, description="Détail par image rejetée")
