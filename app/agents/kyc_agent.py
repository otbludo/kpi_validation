import re
import asyncio
from datetime import datetime
from app.schemas.kyc_input import KYCFormData
from app.schemas.kyc_output import KYCOutputData
from app.services.ocr_engine import ocr_engine
from app.services.openrouter_vision import openrouter_vision
from app.services.insightface import insightface_engine
from app.services.mailtrap.mail_service import mailService
from app.services.kyc_callback import kyc_callback_service


class KYCAgent:
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

    VERIFIED_FIELDS = {
        "nom_et_prenom",
        "date_naissance",
        "sexe",
        "num_CNI_passeport",
        "date_expiration",
        "pays",
        "ville",
    }

    PHOTO_FIELDS = {
        "photo_profile",
        "photo_CNI_recto",
        "photo_CNI_verso",
        "photo_passeport",
    }

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

    PENALTY_FIELDS = {
        "photo_profile": 50,
        "photo_CNI_recto": 50,
        "photo_CNI_verso": 50,
        "photo_passeport": 50,
        "nom_et_prenom": 30,
        "date_naissance":30,
        "sexe": 20,
        "pays": 25,
        "num_CNI_passeport": 50,
        "date_expiration": 30,
    }

    def __init__(self):
        self.vision_engine = openrouter_vision

    def _build_user_prompt(self, user_data: KYCFormData) -> str:
        return f"""
Tu es un système expert de validation KYC par vision artificielle. Tu devras IMPÉRATIVEMENT analyser les images de la pièce d'identité fournies pour vérifier les déclarations de l'utilisateur.

Données déclarées par l'utilisateur :
- nom_et_prenom : {user_data.nom_et_prenom}
- sexe : {user_data.sexe}
- date_naissance : {user_data.date_naissance}
- num_CNI_passeport : {user_data.num_CNI_passeport}
- date_expiration : {user_data.date_expiration}
- pays : {user_data.pays}
- region : {user_data.region}

Consignes d'analyse visuelle ultra-strictes :
1. Regarde TRÈS ATTENTIVEMENT les images de la pièce d'identité jointes (Recto et Verso ou Passeport). Ne devine pas, lis ce qui est écrit sur les documents.
2. Compare chaque champ déclaré avec ce que tu vois écrit sur les images :
   - Si les caractères sur les documents sont différents du texte déclaré, mets "status_validation": "invalid".
   - Si et seulement si ça correspond exactement (présent sur le Recto, le Verso ou le Passeport), mets "status_validation": "valid".
3. Sois impitoyable : si l'utilisateur a triché ou mis des données erronées (mauvais nom, mauvaise date, mauvais numéro de document, pays incorrect, région incorrecte, ville incorrecte), tu DOIS retourner "invalid" pour ce champ.
4. Les dates peuvent être fournies au format AAAA-MM-JJ ou JJ-MM-AAAA.

IMPORTANT : Retourne UNIQUEMENT un objet JSON valide, sans aucun texte supplémentaire, sans markdown, sans ```json.

Format JSON attendu (ne retourne que les champs listés ci-dessous avec leurs statuts) :
{{
    "nom_et_prenom": {{"value": "{user_data.nom_et_prenom}", "status_validation": "valid"}},
    "date_naissance": {{"value": "{user_data.date_naissance}", "status_validation": "valid"}},
    "sexe": {{"value": "{user_data.sexe}", "status_validation": "valid"}},
    "pays": {{"value": "{user_data.pays}", "status_validation": "valid"}},
    "region": {{"value": "{user_data.region}", "status_validation": "valid"}},
    "num_CNI_passeport": {{"value": "{user_data.num_CNI_passeport}", "status_validation": "valid"}},
    "date_expiration": {{"value": "{user_data.date_expiration}", "status_validation": "valid"}}
}}
"""

    def _compute_percentages(self, raw_output: dict, form_data: KYCFormData) -> None:
        if form_data.type_document == 'CNI':
            excluded_fields = {"photo_passeport"}
        else:
            excluded_fields = {"photo_CNI_recto", "photo_CNI_verso"}

        total_percentage = 100.0

        for field in self.ALL_FIELDS:
            if field in excluded_fields:
                raw_output[field]["percentage"] = 0.0
                continue

            if field in self.PENALTY_FIELDS:
                penalty = self.PENALTY_FIELDS[field]
                if raw_output[field].get("status_validation") == "invalid":
                    total_percentage -= penalty
                    raw_output[field]["percentage"] = penalty
                else:
                    raw_output[field]["percentage"] = 0.0
            else:
                raw_output[field]["percentage"] = 0.0

        total_percentage = max(0.0, total_percentage)
        raw_output["total_percentage"] = round(total_percentage, 2)
        raw_output["state_status"] = "valide" if total_percentage >= 60 else "invalide"


    def _get_invalid_field_labels(self, raw_output: dict, form_data: KYCFormData) -> list:
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


    def _get_field_invalid_reason(self, field: str, raw_output: dict, form_data: KYCFormData) -> str:
        if field == "photo_profile":
            return "Photo de profil ne correspond pas à la photo du document"
        if field == "photo_CNI_recto":
            return "Document non fourni"
        if field == "date_naissance":
            val = (getattr(form_data, "date_naissance", "") or "").strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", val) and not re.fullmatch(r"\d{2}-\d{2}-\d{4}", val):
                return "Format de date invalide (attendu: AAAA-MM-JJ ou JJ-MM-AAAA)"
            dt = self._parse_date_string(val)
            if dt is None:
                return "Date de naissance invalide"
            if not (1900 <= dt.year <= datetime.now().year):
                return "Année de naissance invalide"
            return "Ne correspond pas aux informations du document"
        if field == "date_expiration":
            val = (getattr(form_data, "date_expiration", "") or "").strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", val) and not re.fullmatch(r"\d{2}-\d{2}-\d{4}", val):
                return "Format de date invalide (attendu: AAAA-MM-JJ ou JJ-MM-AAAA)"
            dt = self._parse_date_string(val)
            if dt is None:
                return "Date d'expiration invalide"
            if dt < datetime.now():
                return "Date d'expiration déjà passée"
            return "Ne correspond pas aux informations du document"
        if field == "sexe":
            val = (getattr(form_data, "sexe", "") or "").strip().lower()
            return "Valeur de sexe invalide ou non correspondant qu document (valeurs autorisées: M, F, Masculin, Féminin, Homme, Femme)"
        if field == "num_CNI_passeport":
            val = (getattr(form_data, "num_CNI_passeport", "") or "").strip()
            return "Numéro de document invalide (5 à 20 caractères alphanumériques requis)"
        if field == "nom_et_prenom":
            val = (getattr(form_data, "nom_et_prenom", "") or "").strip()
            return "Nom et prénom invalide (2 à 50 caractères alphabétiques requis)"
        return "Ne correspond pas aux informations du document"


    def _get_invalid_fields_with_reasons(self, raw_output: dict, form_data: KYCFormData) -> list:
        if form_data.type_document == 'CNI':
            excluded_fields = {"photo_passeport"}
        else:
            excluded_fields = {"photo_CNI_recto", "photo_CNI_verso"}

        result = []
        for field in self.ALL_FIELDS:
            if field in excluded_fields:
                continue
            if raw_output.get(field, {}).get("status_validation") == "invalid":
                label = self.FIELD_LABELS.get(field, field)
                reason = self._get_field_invalid_reason(field, raw_output, form_data)
                result.append({"label": label, "reason": reason})
        return result


    def _build_rejection_reason(self, invalid_fields_with_reasons: list) -> str:
        if not invalid_fields_with_reasons:
            return ""
        parts = [f"{item['label']} ({item['reason']})" for item in invalid_fields_with_reasons]
        return "Champs invalides ou non conformes à la pièce d'identité : " + ", ".join(parts) + "."


    async def _notify_invalid_fields(self, raw_output: dict, form_data: KYCFormData) -> None:
        invalid_fields = self._get_invalid_fields_with_reasons(raw_output, form_data)

        if not invalid_fields:
            return

        invalid_fields_html = "".join(f"<li>{item['label']} ({item['reason']})</li>" for item in invalid_fields)

        try:
            await mailService.send_email(
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
        invalid_fields = self._get_invalid_fields_with_reasons(raw_output, form_data)
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


    def _parse_date_string(self, val: str):
        val = val.strip()
        for sep in ["-", "/", "."]:
            if sep in val:
                parts = val.split(sep)
                if len(parts) == 3:
                    try:
                        a, b, c = map(int, parts)
                    except ValueError:
                        return None
                    if a > 1000:
                        y, m, d = a, b, c
                    elif c > 1000:
                        d, m, y = a, b, c
                    else:
                        return None
                    try:
                        return datetime(y, m, d)
                    except ValueError:
                        return None
        return None


    def _apply_local_validations(self, raw_output: dict, form_data: KYCFormData) -> None:
        now = datetime.now()
        current_year = now.year

        if "date_naissance" in raw_output and isinstance(raw_output["date_naissance"], dict):
            val = (getattr(form_data, "date_naissance", "") or "").strip()
            dt = self._parse_date_string(val)
            if dt is None:
                raw_output["date_naissance"]["status_validation"] = "invalid"
            else:
                if not (1900 <= dt.year <= current_year):
                    raw_output["date_naissance"]["status_validation"] = "invalid"

        if "date_expiration" in raw_output and isinstance(raw_output["date_expiration"], dict):
            val = (getattr(form_data, "date_expiration", "") or "").strip()
            dt = self._parse_date_string(val)
            if dt is None:
                raw_output["date_expiration"]["status_validation"] = "invalid"
            else:
                if dt < now:
                    raw_output["date_expiration"]["status_validation"] = "invalid"

        if "sexe" in raw_output and isinstance(raw_output["sexe"], dict):
            val = (getattr(form_data, "sexe", "") or "").strip().lower()
            if val not in {"m", "f", "masculin", "feminin", "homme", "femme"}:
                raw_output["sexe"]["status_validation"] = "invalid"

        if "num_CNI_passeport" in raw_output and isinstance(raw_output["num_CNI_passeport"], dict):
            val = (getattr(form_data, "num_CNI_passeport", "") or "").strip()
            if not re.fullmatch(r"[A-Za-z0-9]{5,20}", val):
                raw_output["num_CNI_passeport"]["status_validation"] = "invalid"

        if "nom_et_prenom" in raw_output and isinstance(raw_output["nom_et_prenom"], dict):
            val = (getattr(form_data, "nom_et_prenom", "") or "").strip()
            if not re.fullmatch(r"[A-Za-zÀ-ÿ\s\-']{2,50}", val):
                raw_output["nom_et_prenom"]["status_validation"] = "invalid"


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

        is_blurry, blur_reasons = await asyncio.to_thread(openrouter_vision.check_blur, images_bytes)
        if is_blurry:
            return {
                "message": "Un ou plusieurs documents sont flous ou illisibles. Veuillez fournir une image plus claire.",
                "reasons": blur_reasons,
            }

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
            if field in self.PHOTO_FIELDS:
                continue
            if field not in raw_output:
                raw_output[field] = {"value": getattr(form_data, field, ""), "status_validation": "valid"}
            elif isinstance(raw_output[field], dict):
                if field not in self.VERIFIED_FIELDS:
                    raw_output[field]["status_validation"] = "valid"
            else:
                raw_output[field] = {"value": getattr(form_data, field, ""), "status_validation": "valid"}

        self._apply_local_validations(raw_output, form_data)

        invalid_fields_with_reasons = self._get_invalid_fields_with_reasons(raw_output, form_data)
        raw_output["description"] = self._build_rejection_reason(invalid_fields_with_reasons)

        self._compute_percentages(raw_output, form_data)
        await self._notify_invalid_fields(raw_output, form_data)
        await self._send_callback(raw_output, form_data)

        return KYCOutputData(**raw_output)


kyc_agent = KYCAgent()
