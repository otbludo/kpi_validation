import os
import base64
from typing import Tuple, List
from openai import OpenAI


class BlurDetectionService:
    def __init__(self):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
        self.model = "meta-llama/llama-4-scout-17b-16e-instruct"

    def _check_image_readability(self, image_bytes: bytes, mime_type: str = "image/jpeg") -> Tuple[bool, str]:
        base64_image = base64.b64encode(image_bytes).decode("utf-8")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    "Analyse attentivement la qualité visuelle de ce document d'identité. "
                                    "Est-ce que cette image est floue ? "
                                    "Réponds UNIQUEMENT par le mot 'flou' si le texte ou les détails importants "
                                    "sont difficiles à lire à cause d'un manque de mise au point ou d'un bougé. "
                                    "Réponds UNIQUEMENT par le mot 'lisible' si l'image est nette, stable et exploitable. "
                                    "Ne mets aucun autre mot, aucune ponctuation, aucune explication."
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:{mime_type};base64,{base64_image}"
                                },
                            },
                        ],
                    }
                ],
                temperature=0.0,
                max_tokens=5,
            )

            resultat = response.choices[0].message.content.strip().lower()
            is_blurry = "flou" in resultat
            return is_blurry, resultat
        except Exception as e:
            return True, f"Erreur lors de l'appel OpenRouter : {str(e)}"

    def check_images(self, images_bytes: List[bytes]) -> Tuple[bool, List[str]]:
        reasons = []
        for idx, img_bytes in enumerate(images_bytes):
            mime_type = "image/png" if self._is_png(img_bytes) else "image/jpeg"
            is_blurry, detail = self._check_image_readability(img_bytes, mime_type=mime_type)
            if is_blurry:
                label = "Document principal" if idx == 0 else f"Image {idx + 1}"
                reasons.append(f"{label} : image floue ou illisible ({detail})")
        return len(reasons) > 0, reasons

    def _is_png(self, image_bytes: bytes) -> bool:
        return image_bytes[:8] == b"\x89PNG\r\n\x1a\n"


blur_detection_service = BlurDetectionService()
