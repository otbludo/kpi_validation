from fastapi import UploadFile


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
            raise ValueError(f"Impossible de lire les octets de l'image : {str(e)}")


ocr_engine = OCREngine()