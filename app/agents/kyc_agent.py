"""
Orchestrateur du pipeline de validation KYC.

L'agent enchaîne les étapes suivantes ; chacune est déléguée à un module
spécialisé, l'agent ne portant aucune règle métier lui-même :

1. lecture des photos de la pièce d'identité  → :mod:`app.services.image_loader`
2. contrôle de netteté                         → :mod:`app.services.openrouter_vision`
3. confrontation déclarations / document      → :mod:`app.services.openrouter_vision`
4. comparaison du selfie avec le document      → :mod:`app.services.face_matcher`
5. contrôles locaux de format                  → :mod:`app.domain.kyc.validators`
6. calcul du score de confiance                → :mod:`app.domain.kyc.scoring`
7. notifications (email + callback)            → :mod:`app.services.kyc_notifier`
"""
import asyncio
from typing import List, Union

from app.core.exceptions import InvalidSubmissionError, VisionAnalysisError
from app.core.logging import get_logger
from app.domain.kyc.fields import (
    ALL_FIELDS,
    PHOTO_FIELDS,
    VERIFIED_FIELDS,
    FieldResults,
    PhotoValue,
    ValidationStatus,
)
from app.domain.kyc.prompts import build_kyc_validation_prompt
from app.domain.kyc.reasons import build_rejection_reason, collect_invalid_fields
from app.domain.kyc.scoring import compute_scores
from app.domain.kyc.validators import apply_local_validations
from app.messages.errors import BLURRY_DOCUMENT, NO_DOCUMENT_IMAGE
from app.schemas.kyc_input import KYCFormData, get_document_uploads
from app.schemas.kyc_output import DocumentQualityRejection, KYCOutputData
from app.services.face_matcher import FaceMatcher, face_matcher
from app.services.image_loader import ImageLoader, image_loader
from app.services.kyc_notifier import KYCNotifier, kyc_notifier
from app.services.openrouter_vision import OpenRouterVisionEngine, openrouter_vision

logger = get_logger(__name__)

#: Résultat de :meth:`KYCAgent.process`.
KYCResult = Union[KYCOutputData, DocumentQualityRejection]


class KYCAgent:
    """Point d'entrée unique du traitement d'un dossier KYC."""

    def __init__(
        self,
        vision_engine: OpenRouterVisionEngine = openrouter_vision,
        face_matcher: FaceMatcher = face_matcher,
        image_loader: ImageLoader = image_loader,
        notifier: KYCNotifier = kyc_notifier,
    ):
        """
        Les dépendances sont injectables afin de pouvoir substituer des
        doublures dans les tests ; par défaut, les instances partagées de
        l'application sont utilisées.
        """
        self.vision_engine = vision_engine
        self.face_matcher = face_matcher
        self.image_loader = image_loader
        self.notifier = notifier

    # ------------------------------------------------------------------
    # Pipeline
    # ------------------------------------------------------------------

    async def process(self, form_data: KYCFormData) -> KYCResult:
        """
        Valide un dossier KYC de bout en bout.

        Returns:
            * :class:`DocumentQualityRejection` si une photo est floue
              (aucune validation n'est alors effectuée) ;
            * :class:`KYCOutputData` sinon, avec le statut de chaque champ,
              le score global et le motif de rejet éventuel.

        Raises:
            InvalidSubmissionError: aucune photo de document exploitable.
            VisionAnalysisError: le modèle de vision n'a pas pu analyser le document.
        """
        document_images = await self._load_document_images(form_data)

        is_blurry, blur_reasons = await asyncio.to_thread(
            self.vision_engine.check_blur, document_images
        )
        if is_blurry:
            logger.info("Dossier %s rejeté : document flou", form_data.kyc_id)
            return DocumentQualityRejection(message=BLURRY_DOCUMENT, reasons=blur_reasons)

        results = await self._analyze_document(form_data, document_images)
        results.update(await self._build_photo_results(form_data, document_images[0]))
        self._normalize_text_fields(results, form_data)
        apply_local_validations(results, form_data)

        invalid_fields = collect_invalid_fields(results, form_data)
        results["description"] = build_rejection_reason(invalid_fields)
        compute_scores(results, form_data)

        await self.notifier.notify(results, form_data, invalid_fields)

        logger.info(
            "Dossier %s traité : score=%s, état=%s",
            form_data.kyc_id, results["total_percentage"], results["state_status"],
        )
        return KYCOutputData(**results)

    # ------------------------------------------------------------------
    # Étapes
    # ------------------------------------------------------------------

    async def _load_document_images(self, form_data: KYCFormData) -> List[bytes]:
        """
        Lit les photos de la pièce d'identité.

        Raises:
            InvalidSubmissionError: si aucune image non vide n'est disponible.
        """
        images = [
            await self.image_loader.get_image_bytes(upload)
            for upload in get_document_uploads(form_data)
        ]
        images = [image for image in images if image]
        if not images:
            raise InvalidSubmissionError(NO_DOCUMENT_IMAGE)
        return images

    async def _analyze_document(self, form_data: KYCFormData, images: List[bytes]) -> FieldResults:
        """
        Demande au modèle de vision de confronter les déclarations au document.

        Raises:
            VisionAnalysisError: si le modèle ne renvoie aucun résultat. Sans
                ce garde-fou, un incident OpenRouter rendrait tous les champs
                « valides » par défaut.
        """
        results = await asyncio.to_thread(
            self.vision_engine.analyze_json,
            prompt_text=build_kyc_validation_prompt(form_data),
            images=images,
        )
        if not results:
            raise VisionAnalysisError("Le modèle de vision n'a renvoyé aucun résultat exploitable.")
        return results

    async def _build_photo_results(self, form_data: KYCFormData, document_image: bytes) -> FieldResults:
        """Statut des champs photo : présence des pièces et correspondance du selfie."""

        def presence(upload, status_if_missing: str) -> dict:
            if upload:
                return {"value": PhotoValue.PROVIDED, "status_validation": ValidationStatus.VALID}
            return {"value": PhotoValue.NOT_PROVIDED, "status_validation": status_if_missing}

        return {
            "photo_profile": {
                "value": PhotoValue.PROVIDED,
                "status_validation": await self._verify_selfie(form_data, document_image),
            },
            "photo_CNI_recto": presence(form_data.photo_CNI_recto, ValidationStatus.INVALID),
            "photo_CNI_verso": presence(form_data.photo_CNI_verso, ValidationStatus.NOT_REQUIRED),
            "photo_passeport": presence(form_data.photo_passeport, ValidationStatus.NOT_REQUIRED),
        }

    async def _verify_selfie(self, form_data: KYCFormData, document_image: bytes) -> str:
        """
        Compare la photo de profil au visage figurant sur la pièce d'identité.

        Toute erreur (selfie absent ou illisible, aucun visage détecté)
        conduit à un statut ``invalid``.
        """
        if not form_data.photo_profile:
            return ValidationStatus.INVALID

        try:
            profile_image = await self.image_loader.get_image_bytes(form_data.photo_profile)
        except Exception:
            logger.warning("Lecture de la photo de profil impossible", exc_info=True)
            return ValidationStatus.INVALID

        if not profile_image:
            return ValidationStatus.INVALID

        # Raccourci historique : fichiers identiques ⇒ même visage.
        # NB : ni ce raccourci ni la comparaison ne constituent une preuve de vivacité.
        if profile_image == document_image:
            return ValidationStatus.VALID

        try:
            is_match, _distance = await asyncio.to_thread(
                self.face_matcher.compare, profile_image, document_image
            )
        except Exception:
            logger.warning("Comparaison faciale en échec", exc_info=True)
            return ValidationStatus.INVALID

        return ValidationStatus.VALID if is_match else ValidationStatus.INVALID

    @staticmethod
    def _normalize_text_fields(results: FieldResults, form_data: KYCFormData) -> None:
        """
        Complète et harmonise les champs textuels de ``results`` (en place).

        * Champ absent ou mal formé dans la réponse du modèle : il est
          reconstruit à partir de la valeur déclarée et marqué ``valid``.
        * Champ hors :data:`VERIFIED_FIELDS` : il est déclaratif, donc
          forcé à ``valid`` quel que soit l'avis du modèle.
        """
        for field in ALL_FIELDS:
            if field in PHOTO_FIELDS:
                continue

            entry = results.get(field)
            if not isinstance(entry, dict):
                results[field] = {
                    "value": getattr(form_data, field, ""),
                    "status_validation": ValidationStatus.VALID,
                }
            elif field not in VERIFIED_FIELDS:
                entry["status_validation"] = ValidationStatus.VALID


kyc_agent = KYCAgent()
