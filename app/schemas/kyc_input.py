from typing import Optional, Literal
from fastapi import File, Form, UploadFile
from pydantic import EmailStr

class KYCFormData:
    def __init__(
        self,
        photo_profile: UploadFile,
        photo_CNI_recto: Optional[UploadFile] = None,
        photo_CNI_verso: Optional[UploadFile] = None,
        photo_passeport: Optional[UploadFile] = None,
        type_document: str = "",
        kyc_id: str = "",
        nom_et_prenom: str = "",
        adresse_mail: EmailStr = "",
        profession: str = "",
        numero_NUI: str = "",
        date_naissance: str = "",
        sexe: str = "",
        pays: str = "",
        region: str = "",
        ville: str = "",
        adresse: str = "",
        num_CNI_passeport: str = "",
        date_expiration: str = "",
        registre_commerce: Optional[str] = None,
        code_postal: Optional[str] = None,
    ):
        self.photo_profile = photo_profile
        self.photo_CNI_recto = photo_CNI_recto
        self.photo_CNI_verso = photo_CNI_verso
        self.photo_passeport = photo_passeport
        self.type_document = type_document
        self.kyc_id = kyc_id
        self.nom_et_prenom = nom_et_prenom
        self.adresse_mail = adresse_mail
        self.profession = profession
        self.numero_NUI = numero_NUI
        self.date_naissance = date_naissance
        self.sexe = sexe
        self.pays = pays
        self.region = region
        self.ville = ville
        self.adresse = adresse
        self.num_CNI_passeport = num_CNI_passeport
        self.date_expiration = date_expiration
        self.registre_commerce = registre_commerce
        self.code_postal = code_postal


def build_kyc_form_dependency():
    async def _dependency(
        photo_profile: UploadFile = File(..., description="Le selfie de l'utilisateur (Fichier image)"),
        photo_CNI_recto: UploadFile = File(None, description="La pièce d'identité - Recto (Fichier image)"),
        photo_CNI_verso: UploadFile = File(None, description="La pièce d'identité - Verso (Optionnel si passeport)"),
        photo_passeport: UploadFile = File(None, description="Le passeport (Optionnel si CNI fournie)"),
        type_document: Literal['CNI', 'passeport'] = Form(..., description="Type de document fourni: 'CNI' ou 'passeport'"),
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
        if type_document == 'CNI' and photo_CNI_recto is None:
            raise ValueError("'CNI' sélectionné mais 'photo_CNI_recto' non fourni")
        elif type_document == 'passeport' and photo_passeport is None:
            raise ValueError("'passeport' sélectionné mais 'photo_passeport' non fourni")

        return KYCFormData(
            photo_profile=photo_profile, photo_CNI_recto=photo_CNI_recto,
            photo_CNI_verso=photo_CNI_verso, photo_passeport=photo_passeport,
            type_document=type_document, kyc_id=kyc_id, nom_et_prenom=nom_et_prenom,
            adresse_mail=adresse_mail, profession=profession, numero_NUI=numero_NUI,
            date_naissance=date_naissance, sexe=sexe, pays=pays, region=region,
            ville=ville, adresse=adresse, num_CNI_passeport=num_CNI_passeport,
            date_expiration=date_expiration, registre_commerce=registre_commerce,
            code_postal=code_postal
        )
    return _dependency