"""
Comparaison de visages avec InsightFace.

Le modèle (~280 Mo) est chargé **à la première utilisation** et non à
l'import du module : le démarrage de l'API et l'exécution des tests ne
paient donc ce coût que si une comparaison est réellement effectuée.
"""
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Résolution utilisée par le détecteur de visages.
DEFAULT_DETECTION_SIZE = (640, 640)

#: Distance renvoyée quand la comparaison est impossible (aucune similarité).
NO_MATCH_DISTANCE = 1.0


class FaceMatcher:
    """Détermine si deux images représentent la même personne."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        providers: Optional[List[str]] = None,
        det_size: Optional[Tuple[int, int]] = None,
        threshold: Optional[float] = None,
        ctx_id: Optional[int] = None,
    ):
        """
        Args:
            model_name: pack de modèles InsightFace (ex. ``"buffalo_l"``).
            providers: fournisseurs ONNX Runtime (CPU, CUDA...).
            det_size: résolution du détecteur.
            threshold: similarité cosinus minimale pour valider la correspondance.
            ctx_id: ``-1`` pour le CPU, sinon index du GPU.
        """
        self.model_name = model_name or settings.INSIGHTFACE_MODEL
        self.providers = providers or settings.INSIGHTFACE_PROVIDERS
        self.det_size = det_size or DEFAULT_DETECTION_SIZE
        self.threshold = threshold if threshold is not None else settings.INSIGHTFACE_THRESHOLD
        self.ctx_id = ctx_id if ctx_id is not None else settings.INSIGHTFACE_CTX_ID
        self._face_app = None

    @property
    def face_app(self):
        """Instance ``FaceAnalysis`` initialisée à la demande."""
        if self._face_app is None:
            # Import local : la bibliothèque est lourde et inutile tant
            # qu'aucune comparaison n'est demandée.
            from insightface.app import FaceAnalysis

            logger.info("Chargement du modèle InsightFace '%s'", self.model_name)
            face_app = FaceAnalysis(name=self.model_name, providers=self.providers)
            face_app.prepare(ctx_id=self.ctx_id, det_size=self.det_size)
            self._face_app = face_app
        return self._face_app

    @staticmethod
    def _decode_image(image_bytes: bytes) -> np.ndarray:
        """Décode des octets (JPEG, PNG...) en matrice BGR OpenCV."""
        buffer = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(buffer, cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError("Image invalide")
        return image

    @staticmethod
    def _cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Similarité cosinus entre deux vecteurs d'embedding."""
        return float(
            np.dot(embedding1, embedding2)
            / (np.linalg.norm(embedding1) * np.linalg.norm(embedding2))
        )

    def compare(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        threshold: Optional[float] = None,
    ) -> Tuple[bool, float]:
        """
        Compare le visage principal détecté sur chaque image.

        Toute erreur (image illisible, aucun visage détecté...) est traitée
        comme une non-correspondance : en contexte KYC, le doute profite à
        la sécurité.

        Args:
            image1_bytes: première image (ex. selfie).
            image2_bytes: seconde image (ex. pièce d'identité).
            threshold: seuil ponctuel ; à défaut, celui de l'instance.

        Returns:
            ``(correspondance, distance)`` où ``distance = 1 - similarité``.
        """
        effective_threshold = threshold if threshold is not None else self.threshold

        try:
            faces1 = self.face_app.get(self._decode_image(image1_bytes))
            faces2 = self.face_app.get(self._decode_image(image2_bytes))
        except Exception:
            logger.warning("Comparaison faciale impossible", exc_info=True)
            return False, NO_MATCH_DISTANCE

        if not faces1 or not faces2:
            return False, NO_MATCH_DISTANCE

        similarity = self._cosine_similarity(faces1[0].embedding, faces2[0].embedding)
        return similarity >= effective_threshold, 1.0 - similarity


face_matcher = FaceMatcher()
