"""
Dépendances FastAPI de l'API v1.

Le formulaire KYC est déclaré champ par champ avec ``Form``/``File`` afin que
FastAPI le valide et le documente automatiquement (Swagger / OpenAPI).
"""
from typing import Literal, Optional

from fastapi import File, Form, HTTPException, UploadFile, status
from pydantic import EmailStr

from app.core.exceptions import InvalidSubmissionError
from app.messages.errors import INVALID_FORM_DATA
from app.schemas.kyc_input import KYCFormData


async def get_kyc_form(
    photo_profile: UploadFile = File(..., description="Le selfie de l'utilisateur (Fichier image)"),
    # NB : ne pas annoter ces champs en ``Optional[UploadFile]``. Le schéma
    # OpenAPI généré (anyOf binary/null) fait perdre le sélecteur de fichier
    # dans Swagger UI ; ``File(None)`` suffit à les rendre facultatifs.
    photo_CNI_recto: UploadFile = File(None, description="La pièce d'identité - Recto (Fichier image)"),
    photo_CNI_verso: UploadFile = File(None, description="La pièce d'identité - Verso (Optionnel si passeport)"),
    photo_passeport: UploadFile = File(None, description="Le passeport (Optionnel si CNI fournie)"),
    type_document: Literal["CNI", "passeport"] = Form(..., description="Type de document fourni: 'CNI' ou 'passeport'"),
    kyc_id: str = Form(..., description="Identifiant unique du dossier KYC en cours de traitement"),
    nom_et_prenom: str = Form(..., description="Nom complet déclaré"),
    adresse_mail: EmailStr = Form(..., description="Adresse email valide de l'utilisateur"),
    profession: str = Form(..., description="Profession déclarée"),
    numero_NUI: str = Form(..., description="Numéro Unique d'Identification"),
    date_naissance: str = Form(..., description="Date de naissance au format AAAA-MM-JJ"),
    sexe: str = Form(..., description="Genre (M/F ou Masculin/Féminin)"),
    pays: str = Form(..., description="Pays de résidence"),
    region: str = Form(..., description="Région de résidence"),
    ville: str = Form(..., description="Ville de résidence"),
    adresse: str = Form(..., description="Adresse de domicile fixe"),
    num_CNI_passeport: str = Form(..., description="Numéro de la pièce d'identité fournie"),
    date_expiration: str = Form(..., description="Date d'expiration de la pièce d'identité"),
    registre_commerce: Optional[str] = Form(None, description="Numéro de registre de commerce si applicable"),
    code_postal: Optional[str] = Form(None, description="Code postal de la zone"),
) -> KYCFormData:
    """
    Construit et contrôle le :class:`KYCFormData` à partir de la requête.

    Raises:
        HTTPException: 400 si la pièce correspondant au ``type_document``
            n'est pas jointe.
    """
    form_data = KYCFormData(
        photo_profile=photo_profile,
        photo_CNI_recto=photo_CNI_recto,
        photo_CNI_verso=photo_CNI_verso,
        photo_passeport=photo_passeport,
        type_document=type_document,
        kyc_id=kyc_id,
        nom_et_prenom=nom_et_prenom,
        adresse_mail=adresse_mail,
        profession=profession,
        numero_NUI=numero_NUI,
        date_naissance=date_naissance,
        sexe=sexe,
        pays=pays,
        region=region,
        ville=ville,
        adresse=adresse,
        num_CNI_passeport=num_CNI_passeport,
        date_expiration=date_expiration,
        registre_commerce=registre_commerce,
        code_postal=code_postal,
    )

    try:
        form_data.validate_documents()
    except InvalidSubmissionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=INVALID_FORM_DATA.format(exc),
        ) from exc

    return form_data
