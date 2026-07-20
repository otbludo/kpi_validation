import os
from dotenv import load_dotenv
import json
import re
import base64
from typing import List, Optional, Tuple
from openai import OpenAI

load_dotenv()

class OpenRouterVisionEngine:
    DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.client = None
        self.default_model = model or self.DEFAULT_MODEL
        key = api_key or os.environ.get("OPENROUTER_API_KEY")
        if key:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=key,
            )

    @staticmethod
    def _build_message_content(prompt_text: str, images: Optional[List[bytes]]) -> list:
        message_content = [{"type": "text", "text": prompt_text}]
        for img in images or []:
            base64_image = base64.b64encode(img).decode("utf-8")
            message_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{base64_image}"
                }
            })
        return message_content

    @staticmethod
    def _extract_json(text: str) -> dict:
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if not match:
            return {}
        try:
            return json.loads(match.group())
        except Exception:
            return {}

    def analyze_json(self, prompt_text: str, images: Optional[List[bytes]] = None) -> dict:
        if self.client is None:
            print("[OpenRouter Error]: OPENROUTER_API_KEY manquante, analyse impossible.")
            return {}

        message_content = self._build_message_content(prompt_text, images)

        try:
            response = self.client.chat.completions.create(
                model=self.default_model,
                messages=[{"role": "user", "content": message_content}],
                temperature=0.0,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            if not content:
                return {}
            return self._extract_json(content)
        except Exception as e:
            print(f"[OpenRouter Error]: {str(e)}")
            return {}

    def check_blur(self, images: List[bytes]) -> Tuple[bool, List[str]]:
        if self.client is None:
            print("[OpenRouter Error]: OPENROUTER_API_KEY manquante, analyse impossible.")
            return True, ["OpenRouter API key manquante"]

        reasons = []
        for idx, img_bytes in enumerate(images):
            base64_image = base64.b64encode(img_bytes).decode("utf-8")
            mime_type = "image/png" if img_bytes[:8] == b"\x89PNG\r\n\x1a\n" else "image/jpeg"

            try:
                response = self.client.chat.completions.create(
                    model=self.default_model,
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
                if "flou" in resultat:
                    label = "Document principal" if idx == 0 else f"Image {idx + 1}"
                    reasons.append(f"{label} : image floue ou illisible ({resultat})")
            except Exception as e:
                label = "Document principal" if idx == 0 else f"Image {idx + 1}"
                reasons.append(f"{label} : erreur lors de l'analyse de netteté ({str(e)})")

        return len(reasons) > 0, reasons


openrouter_vision = OpenRouterVisionEngine()
