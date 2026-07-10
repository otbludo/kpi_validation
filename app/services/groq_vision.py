import os
import json
import base64
from typing import List, Optional, Union
from dotenv import load_dotenv
from groq import Groq

load_dotenv()


class GroqVisionEngine:
    """
    Moteur de vision Groq générique et réutilisable.
    Ce moteur est volontairement découplé de toute logique métier (KYC ou autre).
    Il reçoit uniquement un prompt textuel et, optionnellement, des images,
    puis renvoie la sortie brute du modèle. On peut donc le réutiliser partout
    (agents, utils, etc.) sans le modifier.
    """

    DEFAULT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.client = Groq(api_key=api_key or os.environ.get("GROQ_API_KEY"))
        self.default_model = model or self.DEFAULT_MODEL


    @staticmethod
    def bytes_to_base64_url(image_bytes: bytes, mime_type: str = "image/jpeg") -> str:
        """
        Convertit les octets bruts d'une image en une URL de données Base64
        compatible avec l'API de vision de Groq.
        """
        base64_encoded = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:{mime_type};base64,{base64_encoded}"


    @staticmethod
    def _clean_content(content_string: str) -> str:
        """
        Nettoie la chaîne de caractères renvoyée par le modèle
        (sécurité contre le Markdown résiduel type ```json ... ```).
        """
        if "```json" in content_string:
            content_string = content_string.split("```json")[1].split("```")[0].strip()
        elif "```" in content_string:
            content_string = content_string.split("```")[1].split("```")[0].strip()
        return content_string


    def _build_message_content(
        self, prompt_text: str, images: Optional[List[Union[bytes, str]]]
    ) -> list:
        """
        Construit le contenu du message (texte + images) attendu par l'API Groq.
        Les images peuvent être fournies soit en octets bruts, soit en URL Base64.
        """
        message_content = [{"type": "text", "text": prompt_text}]

        for img in images or []:
            url = self.bytes_to_base64_url(img) if isinstance(img, (bytes, bytearray)) else img
            message_content.append({"type": "image_url", "image_url": {"url": url}})
        return message_content


    def analyze(
        self,
        prompt_text: str,
        images: Optional[List[Union[bytes, str]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
        json_mode: bool = True,
    ) -> str:
        """
        Envoie un prompt (et éventuellement des images) au modèle de vision Groq
        et renvoie la sortie textuelle brute (nettoyée).

        - prompt_text : le texte de la requête.
        - images : liste d'images (octets bruts ou URL Base64). Optionnel.
        - model : surcharge du modèle par défaut. Optionnel.
        - temperature : 0.0 par défaut pour des réponses déterministes.
        - json_mode : force le modèle à renvoyer un objet JSON pur.
        """
        message_content = self._build_message_content(prompt_text, images)

        kwargs = {
            "model": model or self.default_model,
            "messages": [{"role": "user", "content": message_content}],
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = self.client.chat.completions.create(**kwargs)
        return self._clean_content(response.choices[0].message.content)


    def analyze_json(
        self,
        prompt_text: str,
        images: Optional[List[Union[bytes, str]]] = None,
        model: Optional[str] = None,
        temperature: float = 0.0,
    ) -> dict:
        """
        Identique à `analyze` mais renvoie directement un dictionnaire Python
        en parsant la sortie JSON du modèle.
        """
        content_string = self.analyze(
            prompt_text=prompt_text,
            images=images,
            model=model,
            temperature=temperature,
            json_mode=True,
        )
        return json.loads(content_string)


groq_vision = GroqVisionEngine()
