import os
from dotenv import load_dotenv
import json
import re
import base64
from typing import List, Optional
from openai import OpenAI

load_dotenv()

class OpenRouterVisionEngine:
    DEFAULT_MODEL = "meta-llama/llama-4-scout"

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


openrouter_vision = OpenRouterVisionEngine()
