"""Lecture du contenu binaire des fichiers envoyés via le formulaire."""
from typing import Optional

from fastapi import UploadFile

from app.core.exceptions import ImageReadError
from app.messages.errors import IMAGE_READ_ERROR


class ImageLoader:
    """Extrait les octets d'un ``UploadFile`` sans consommer le flux."""

    @staticmethod
    async def get_image_bytes(upload_file: Optional[UploadFile]) -> bytes:
        """
        Lit l'intégralité d'un fichier envoyé.

        Le curseur est replacé au début après lecture, afin que le même
        fichier puisse être relu par une autre étape du pipeline.

        Args:
            upload_file: fichier reçu, ou ``None`` si le champ est absent.

        Returns:
            Le contenu binaire, ou ``b""`` si aucun fichier n'est fourni.

        Raises:
            ImageReadError: si la lecture du flux échoue.
        """
        if not upload_file:
            return b""

        try:
            contents = await upload_file.read()
            await upload_file.seek(0)
            return contents
        except Exception as exc:
            raise ImageReadError(IMAGE_READ_ERROR.format(exc)) from exc


image_loader = ImageLoader()
