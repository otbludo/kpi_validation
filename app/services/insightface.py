import os
from typing import Optional, Tuple
import cv2
import numpy as np
from insightface.app import FaceAnalysis


class InsightFaceEngine:
    def __init__(
        self,
        model_name: Optional[str] = None,
        providers: Optional[list] = None,
        det_size: Optional[tuple] = None,
        threshold: Optional[float] = None,
        ctx_id: Optional[int] = None,
    ):
        self.model_name = model_name or os.getenv("INSIGHTFACE_MODEL", "buffalo_l")
        self.providers = providers or os.getenv("INSIGHTFACE_PROVIDERS", "CPUExecutionProvider").split(",")
        self.det_size = det_size or (640, 640)
        self.threshold = threshold if threshold is not None else float(
            os.getenv("INSIGHTFACE_THRESHOLD", "0.40")
        )
        self.ctx_id = int(os.getenv("INSIGHTFACE_CTX_ID", str(ctx_id if ctx_id is not None else -1)))

        self.face_app = FaceAnalysis(
            name=self.model_name,
            providers=self.providers,
        )
        self.face_app.prepare(
            ctx_id=self.ctx_id,
            det_size=self.det_size,
        )
        

    @staticmethod
    def _read_image(image_bytes: bytes) -> np.ndarray:
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Image invalide")
        return img


    @staticmethod
    def _compute_cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        return float(dot_product / (norm1 * norm2))


    def compare(
        self,
        image1_bytes: bytes,
        image2_bytes: bytes,
        threshold: Optional[float] = None,
    ) -> Tuple[bool, float]:
        effective_threshold = threshold if threshold is not None else self.threshold

        try:
            img1 = self._read_image(image1_bytes)
            img2 = self._read_image(image2_bytes)
        except Exception:
            return False, 1.0

        try:
            faces1 = self.face_app.get(img1)
            faces2 = self.face_app.get(img2)
        except Exception:
            return False, 1.0

        if len(faces1) == 0 or len(faces2) == 0:
            return False, 1.0

        embedding1 = faces1[0].embedding
        embedding2 = faces2[0].embedding

        similarity = self._compute_cosine_similarity(embedding1, embedding2)
        distance = 1.0 - similarity
        return similarity >= effective_threshold, distance


insightface_engine = InsightFaceEngine()
