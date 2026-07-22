from fastapi import UploadFile
from app.messages.errors import IMAGE_READ_ERROR


class OCREngine:
    @staticmethod
    async def get_image_bytes(upload_file: UploadFile) -> bytes:
        """Lit un UploadFile et retourne ses octets bruts pour Ollama."""
        if not upload_file:
            return b""
        
        try:
            contents = await upload_file.read()
            await upload_file.seek(0)  
            return contents
        except Exception as e:
            raise ValueError(IMAGE_READ_ERROR.format(str(e)))


ocr_engine = OCREngine()