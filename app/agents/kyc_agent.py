from app.schemas.kyc_input import KYCFormData
from app.schemas.kyc_output import KYCOutputData
from app.services.ocr_engine import ocr_engine
from app.services.groq_vision import groq_vision
from app.services.insightface import insightface_engine
from app.services.mailtrap.mail_service import mailService
from app.services.kyc_callback import kyc_callback_service


class KYCAgent:
    # Liste ordonnée de tous les champs analysés (hors métadonnées comme total_percentage)
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

    # Champs réellement confrontés à la pièce d'identité.
    VERIFIED_FIELDS = {
        "nom_et_prenom",
        "date_naissance",
        "sexe",
        "num_CNI_passeport",
        "date_expiration",
        "pays",
        "ville",
    }

    # Champs de type fichier/photo, dont le statut est géré manuellement (étape 4).
    PHOTO_FIELDS = {
        "photo_profile",
        "photo_CNI_recto",
        "photo_CNI_verso",
        "photo_passeport",
    }
    
    # Libellés lisibles des champs pour l'affichage dans le mail
    FIELD_LABELS = {
        "photo_profile": "Photo de profil",
        "nom_et_prenom": "Nom et prénom",
        "adresse_mail": "Adresse mail",
        "profession": "Profession",
        "numero_NUI": "Numéro NUI",
        "registre_commerce": "Registre de commerce",
        "date_naissance": "Date de naissance",
        "sexe": "Sexe",
        "pays": "Pays",
        "region": "Région",
        "ville": "Ville",
        "adresse": "Adresse",
        "code_postal": "Code postal",
        "num_CNI_passeport": "Numéro CNI / Passeport",
        "date_expiration": "Date d'expiration",
        "photo_CNI_recto": "Photo CNI (Recto)",
        "photo_CNI_verso": "Photo CNI (Verso)",
        "photo_passeport": "Photo passeport",
    }
    
    def __init__(self):
        self.vision_engine = groq_vision

    def _build_user_prompt(self, user_data: KYCFormData) -> str:
        return f"""
Tu es un système expert de validation KYC par vision artificielle. Tu devras IMPÉRATIVEMENT analyser les images de la CNI fournies pour vérifier les déclarations de l'utilisateur.

Données déclarées par l'utilisateur :
- nom_et_prenom : {user_data.nom_et_prenom}
- sexe : {user_data.sexe}
- date_naissance : {user_data.date_naissance}
- num_CNI_passeport : {user_data.num_CNI_passeport}
- date_expiration : {user_data.date_expiration}
- pays : {user_data.pays}
- region : {user_data.region}
- ville : {user_data.ville}

Consignes d'analyse visuelle ultra-strictes :
1. Regarde TRÈS ATTENTIVEMENT les images de la CNI jointes (Recto et Verso). Ne devine pas, lis ce qui est écrit sur les photos. Les informations peuvent être réparties sur l'une ou l'autre des faces.
2. Compare chaque champ déclaré avec ce que tu vois écrit sur les photos :
   - Si les caractères sur les photos sont différents du texte déclaré, mets "status_validation": "invalid".
   - Si et seulement si ça correspond exactement (présent sur le Recto ou le Verso), mets "status_validation": "valid".
3. Sois impitoyable : si l'utilisateur a triché ou mis des données erronées (mauvais nom, mauvaise date, mauvais numéro de CNI, pays incorrect, région incorrecte, ville incorrecte), tu DOIS retourner "invalid" pour ce champ.

Format JSON attendu en sortie (remplis les 'status_validation' exclusivement par 'valid' ou 'invalid') :
{{
    "photo_profile": {{"value": "fourni", "status_validation": "valid"}},
    "nom_et_prenom": {{"value": "{user_data.nom_et_prenom}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "adresse_mail": {{"value": "{user_data.adresse_mail}", "status_validation": "valid"}},
    "profession": {{"value": "{user_data.profession}", "status_validation": "valid"}},
    "numero_NUI": {{"value": "{user_data.numero_NUI}", "status_validation": "valid"}},
    "registre_commerce": {{"value": "{user_data.registre_commerce or ''}", "status_validation": "valid"}},
    "date_naissance": {{"value": "{user_data.date_naissance}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "sexe": {{"value": "{user_data.sexe}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "pays": {{"value": "{user_data.pays}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "region": {{"value": "{user_data.region}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "ville": {{"value": "{user_data.ville}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "adresse": {{"value": "{user_data.adresse}", "status_validation": "valid"}},
    "code_postal": {{"value": "{user_data.code_postal or ''}", "status_validation": "valid"}},
    "num_CNI_passeport": {{"value": "{user_data.num_CNI_passeport}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "date_expiration": {{"value": "{user_data.date_expiration}", "status_validation": "METTRE_ICI_valid_OU_invalid"}},
    "photo_CNI_recto": {{"value": "fourni", "status_validation": "valid"}},
    "photo_CNI_verso": {{"value": "fourni", "status_validation": "valid"}},
    "photo_passeport": {{"value": "fourni", "status_validation": "valid"}}
}}
"""

    def _compute_percentages(self, raw_output: dict, form_data: KYCFormData) -> None:
        """
        Répartit le pourcentage à parts égales entre les champs *actifs*
        et calcule le score global (total_percentage).
        - Si type_document == 'CNI' : photo_passeport n'est pas pris en compte.
        - Sinon (passeport) : photo_CNI_recto et photo_CNI_verso ne sont pas pris en compte.
        - Chaque champ actif reçoit une part égale (100 / nombre de champs actifs).
        - Un champ invalide ou non fourni ne contribue pas au total (on retire sa part).
        - Les champs non pris en compte ont un pourcentage de 0.
        """
        if form_data.type_document == 'CNI':
            excluded_fields = {"photo_passeport"}
        else:
            excluded_fields = {"photo_CNI_recto", "photo_CNI_verso"}

        active_fields = [f for f in self.ALL_FIELDS if f not in excluded_fields]
        active_count = len(active_fields)
        share = round(100 / active_count, 2) if active_count else 0.0

        valid_count = 0
        for field in self.ALL_FIELDS:
            if field in excluded_fields:
                # Champ non pris en compte : n'influence pas le score
                raw_output[field]["percentage"] = 0.0
                continue

            raw_output[field]["percentage"] = share

            if raw_output[field].get("status_validation") == "valid":
                valid_count += 1

        raw_output["total_percentage"] = round((valid_count / active_count) * 100, 2) if active_count else 0.0
        raw_output["state_status"] = "valide" if valid_count == active_count else "invalide"


    def _get_invalid_field_labels(self, raw_output: dict, form_data: KYCFormData) -> list:
        """
        Renvoie la liste des libellés lisibles des champs invalides,
        en ne considérant que les champs actifs (selon le type de document).
        """
        if form_data.type_document == 'CNI':
            excluded_fields = {"photo_passeport"}
        else:
            excluded_fields = {"photo_CNI_recto", "photo_CNI_verso"}

        return [
            self.FIELD_LABELS.get(field, field)
            for field in self.ALL_FIELDS
            if field not in excluded_fields
            and raw_output.get(field, {}).get("status_validation") == "invalid"
        ]
        

    def _build_rejection_reason(self, invalid_labels: list) -> str:
        if not invalid_labels:
            return ""
        return "Champs invalides ou non conformes à la pièce d'identité : " + ", ".join(invalid_labels) + "."


    def _notify_invalid_fields(self, raw_output: dict, form_data: KYCFormData) -> None:
        invalid_fields = self._get_invalid_field_labels(raw_output, form_data)

        if not invalid_fields:
            return

        invalid_fields_html = "".join(f"<li>{label}</li>" for label in invalid_fields)

        try:
            mailService.send_email(
                email_to=form_data.adresse_mail,
                subject="Alerte KYC : champs invalides détectés",
                template_name="warning",
                user_name=form_data.nom_et_prenom or form_data.adresse_mail,
                invalid_fields=invalid_fields_html,
                total_percentage=raw_output.get("total_percentage", 0.0),
            )
        except Exception:
            pass
        

    async def _send_callback(self, raw_output: dict, form_data: KYCFormData) -> None:
        invalid_fields = self._get_invalid_field_labels(raw_output, form_data)
        rejection_reason = self._build_rejection_reason(invalid_fields)

        await kyc_callback_service.notify(
            kyc_id=form_data.kyc_id,
            ai_confidence_score=raw_output.get("total_percentage", 0.0),
            rejection_reason=rejection_reason,
        )
        

    async def _validate_photo_profile(self, form_data: KYCFormData) -> str:
        if not form_data.photo_profile:
            return "invalid"

        try:
            profile_bytes = await ocr_engine.get_image_bytes(form_data.photo_profile)
        except Exception:
            return "invalid"

        document_bytes = None
        if form_data.type_document == "CNI":
            if form_data.photo_CNI_recto:
                document_bytes = await ocr_engine.get_image_bytes(form_data.photo_CNI_recto)
            elif form_data.photo_CNI_verso:
                document_bytes = await ocr_engine.get_image_bytes(form_data.photo_CNI_verso)
        elif form_data.type_document == "passeport":
            if form_data.photo_passeport:
                document_bytes = await ocr_engine.get_image_bytes(form_data.photo_passeport)

        if not document_bytes:
            return "invalid"

        if profile_bytes == document_bytes:
            return "valid"

        try:
            is_match, _ = insightface_engine.compare(profile_bytes, document_bytes)
            return "valid" if is_match else "invalid"
        except Exception:
            return "invalid"


    async def process(self, form_data: KYCFormData) -> KYCOutputData:
        images_bytes = []
        if form_data.type_document == 'CNI':
            if form_data.photo_CNI_recto:
                images_bytes.append(await ocr_engine.get_image_bytes(form_data.photo_CNI_recto))
            if form_data.photo_CNI_verso:
                images_bytes.append(await ocr_engine.get_image_bytes(form_data.photo_CNI_verso))
        else:
            if form_data.photo_passeport:
                images_bytes.append(await ocr_engine.get_image_bytes(form_data.photo_passeport))

        if not images_bytes:
            raise ValueError("Aucun fichier d'image valide n'a pu être extrait du formulaire.")

        prompt_text = self._build_user_prompt(form_data)
        raw_output = self.vision_engine.analyze_json(
            prompt_text=prompt_text,
            images=images_bytes,
        )

        photo_profile_status = await self._validate_photo_profile(form_data)
        raw_output["photo_profile"] = {"value": "fourni", "status_validation": photo_profile_status}
        raw_output["photo_CNI_recto"] = {"value": "fourni" if form_data.photo_CNI_recto else "non_fourni", "status_validation": "valid" if form_data.photo_CNI_recto else "invalid"}
        raw_output["photo_CNI_verso"] = {"value": "fourni" if form_data.photo_CNI_verso else "non_fourni", "status_validation": "valid" if form_data.photo_CNI_verso else "not_required"}
        raw_output["photo_passeport"] = {"value": "fourni" if form_data.photo_passeport else "non_fourni", "status_validation": "valid" if form_data.photo_passeport else "not_required"}

        for field in self.ALL_FIELDS:
            if field in self.VERIFIED_FIELDS or field in self.PHOTO_FIELDS:
                continue
            if field in raw_output and isinstance(raw_output[field], dict):
                raw_output[field]["status_validation"] = "valid"

        self._compute_percentages(raw_output, form_data)
        self._notify_invalid_fields(raw_output, form_data)
        await self._send_callback(raw_output, form_data)

        return KYCOutputData(**raw_output)


kyc_agent = KYCAgent()
