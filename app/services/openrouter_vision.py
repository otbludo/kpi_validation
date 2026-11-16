"""
Client du modèle de vision hébergé sur OpenRouter.

Deux usages :

* :meth:`OpenRouterVisionEngine.analyze_json` — confronte les déclarations
  de l'utilisateur au contenu de sa pièce d'identité ;
* :meth:`OpenRouterVisionEngine.check_blur` — détecte les photos floues
  avant toute analyse.

Les appels sont **synchrones** (SDK OpenAI) : depuis du code asynchrone, les
exécuter via ``asyncio.to_thread`` pour ne pas bloquer la boucle d'événements.
"""
import base64
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from openai import BadRequestError, NotFoundError, OpenAI

from app.core.config import settings
from app.core.logging import get_logger
from app.domain.kyc.prompts import BLUR_CHECK_PROMPT

logger = get_logger(__name__)

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JSON_OBJECT_PATTERN = re.compile(r"\{.*\}", re.DOTALL)

#: Mot-clé renvoyé par le modèle lorsqu'une image est jugée floue.
BLUR_KEYWORD = "flou"


class OpenRouterVisionEngine:
    """Encapsule les appels au modèle de vision multimodal."""

    DEFAULT_MODEL = settings.OPENROUTER_MODEL

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Args:
            api_key: clé OpenRouter ; à défaut, ``settings.OPENROUTER_API_KEY``.
            model: identifiant du modèle ; à défaut, :attr:`DEFAULT_MODEL`.

        Sans clé, le client n'est pas créé et chaque appel échoue proprement
        (dictionnaire vide ou image considérée floue).
        """
        self.default_model = model or self.DEFAULT_MODEL
        self.client: Optional[OpenAI] = None

        key = api_key or settings.OPENROUTER_API_KEY
        if key:
            self.client = OpenAI(base_url=settings.OPENROUTER_BASE_URL, api_key=key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _detect_mime_type(image: bytes) -> str:
        """Détermine le type MIME à partir de la signature binaire (PNG, sinon JPEG)."""
        return "image/png" if image[:8] == _PNG_SIGNATURE else "image/jpeg"

    @classmethod
    def _image_part(cls, image: bytes) -> Dict[str, Any]:
        """Encode une image au format ``image_url`` (data URI base64)."""
        encoded = base64.b64encode(image).decode("utf-8")
        return {
            "type": "image_url",
            "image_url": {"url": f"data:{cls._detect_mime_type(image)};base64,{encoded}"},
        }

    @classmethod
    def _build_message_content(cls, prompt_text: str, images: Optional[List[bytes]]) -> list:
        """Assemble un message multimodal : le texte suivi des images."""
        return [{"type": "text", "text": prompt_text}] + [
            cls._image_part(image) for image in images or []
        ]

    @staticmethod
    def _extract_json(text: str) -> dict:
        """
        Extrait le premier objet JSON d'une réponse textuelle.

        Tolère un texte parasite autour du JSON (préambule, balises markdown).
        Retourne ``{}`` si aucun JSON exploitable n'est trouvé.
        """
        match = _JSON_OBJECT_PATTERN.search(text)
        if not match:
            return {}
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _message_content(response: Any) -> Optional[str]:
        """
        Extrait le texte de la première réponse du modèle.

        OpenRouter peut répondre ``200 OK`` sans aucun ``choices`` lorsque le
        fournisseur échoue en cours de route : le corps contient alors un
        objet ``error`` (non typé par le SDK OpenAI, d'où ``getattr``).

        Returns:
            Le texte produit, ou ``None`` si la réponse n'en contient pas.
        """
        if not getattr(response, "choices", None):
            logger.error(
                "Réponse OpenRouter sans contenu (erreur fournisseur) : %s",
                getattr(response, "error", None) or response,
            )
            return None
        return response.choices[0].message.content

    @staticmethod
    def _image_label(index: int) -> str:
        """Libellé lisible d'une image selon sa position dans la liste."""
        return "Document principal" if index == 0 else f"Image {index + 1}"

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def analyze_json(self, prompt_text: str, images: Optional[List[bytes]] = None) -> dict:
        """
        Soumet un prompt et des images, et retourne la réponse JSON du modèle.

        Returns:
            Le dictionnaire produit par le modèle, ou ``{}`` en cas d'erreur
            (clé absente, erreur réseau, réponse non JSON).
        """
        if self.client is None:
            logger.error("OPENROUTER_API_KEY manquante : analyse du document impossible.")
            return {}

        request = {
            "model": self.default_model,
            "messages": [{"role": "user", "content": self._build_message_content(prompt_text, images)}],
            "temperature": 0.0,
            "max_tokens": settings.OPENROUTER_MAX_TOKENS,
        }

        try:
            try:
                response = self.client.chat.completions.create(
                    **request, response_format={"type": "json_object"}
                )
            except (NotFoundError, BadRequestError) as exc:
                # Selon le routage OpenRouter, aucun fournisseur disponible ne
                # supporte forcément ``response_format`` (erreur 404 « No
                # endpoints found »). Le prompt exige déjà du JSON pur et
                # ``_extract_json`` tolère du texte parasite : on relance sans.
                logger.warning("response_format refusé par OpenRouter, nouvel essai sans : %s", exc)
                response = self.client.chat.completions.create(**request)
        except Exception:
            logger.exception("Échec de l'appel OpenRouter (analyse du document)")
            return {}

        content = self._message_content(response)
        return self._extract_json(content) if content else {}

    def check_blur(self, images: List[bytes]) -> Tuple[bool, List[str]]:
        """
        Vérifie la netteté de chaque image.

        Une erreur d'analyse est assimilée à une image illisible : on ne
        poursuit pas la validation sur un document dont la qualité n'a pas
        pu être confirmée.

        Returns:
            ``(au_moins_une_image_floue, motifs)``.
        """
        if self.client is None:
            logger.error("OPENROUTER_API_KEY manquante : contrôle de netteté impossible.")
            return True, ["OpenRouter API key manquante"]

        reasons = []
        for index, image in enumerate(images):
            label = self._image_label(index)
            try:
                response = self.client.chat.completions.create(
                    model=self.default_model,
                    messages=[{"role": "user", "content": self._build_message_content(BLUR_CHECK_PROMPT, [image])}],
                    temperature=0.0,
                    max_tokens=5,
                )
            except Exception as exc:
                logger.exception("Échec de l'appel OpenRouter (contrôle de netteté)")
                reasons.append(f"{label} : erreur lors de l'analyse de netteté ({exc})")
                continue

            content = self._message_content(response)
            if content is None:
                reasons.append(f"{label} : erreur lors de l'analyse de netteté (réponse vide du fournisseur)")
                continue

            verdict = content.strip().lower()

            if BLUR_KEYWORD in verdict:
                reasons.append(f"{label} : image floue ou illisible ({verdict})")

        return bool(reasons), reasons


openrouter_vision = OpenRouterVisionEngine()
