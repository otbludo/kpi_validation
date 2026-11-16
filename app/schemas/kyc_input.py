"""
Modèle d'entrée d'un dossier KYC.

Le formulaire arrive en ``multipart/form-data`` (champs texte + fichiers) ;
sa déclaration FastAPI se trouve dans :mod:`app.api.v1.dependencies`.
"""
from dataclasses import dataclass
from typing import List, Optional

from fastapi import UploadFile

from app.core.exceptions import InvalidSubmissionError
from app.domain.kyc.fields import DocumentType


@dataclass
class KYCFormData:
    """Données déclarées par l'utilisateur et pièces justificatives associées."""

    # --- Pièces jointes -----------------------------------------------------
    photo_profile: UploadFile
    photo_CNI_recto: Optional[UploadFile] = None
    photo_CNI_verso: Optional[UploadFile] = None
    photo_passeport: Optional[UploadFile] = None

    # --- Métadonnées du dossier ----------------------------------------------
    type_document: str = ""
    kyc_id: str = ""

    # --- Identité ------------------------------------------------------------
    nom_et_prenom: str = ""
    adresse_mail: str = ""
    profession: str = ""
    numero_NUI: str = ""
    date_naissance: str = ""
    sexe: str = ""

    # --- Résidence -----------------------------------------------------------
    pays: str = ""
    region: str = ""
    ville: str = ""
    adresse: str = ""
    code_postal: Optional[str] = None

    # --- Pièce d'identité ----------------------------------------------------
    num_CNI_passeport: str = ""
    date_expiration: str = ""
    registre_commerce: Optional[str] = None

    def validate_documents(self) -> None:
        """
        Vérifie que la pièce correspondant au ``type_document`` est jointe.

        Raises:
            InvalidSubmissionError: si la photo attendue est absente.
        """
        if self.type_document == DocumentType.CNI and self.photo_CNI_recto is None:
            raise InvalidSubmissionError("'CNI' sélectionné mais 'photo_CNI_recto' non fourni")
        if self.type_document == DocumentType.PASSPORT and self.photo_passeport is None:
            raise InvalidSubmissionError("'passeport' sélectionné mais 'photo_passeport' non fourni")


def get_document_uploads(form_data: KYCFormData) -> List[UploadFile]:
    """
    Retourne les photos de la pièce d'identité, dans l'ordre d'analyse.

    * CNI : recto puis verso (si fournis) ;
    * passeport : page d'identité.
    """
    if form_data.type_document == DocumentType.CNI:
        candidates = [form_data.photo_CNI_recto, form_data.photo_CNI_verso]
    else:
        candidates = [form_data.photo_passeport]
    return [upload for upload in candidates if upload]
