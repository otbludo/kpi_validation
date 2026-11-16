"""
Configuration du logging applicatif.

Remplace les ``print`` dispersés par un logger standard, ce qui permet de
contrôler le niveau de verbosité et de router les logs (stdout, fichier,
agrégateur) sans modifier le code métier.
"""
import logging

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def configure_logging() -> None:
    """Initialise le logger racine (à appeler une fois au démarrage)."""
    logging.basicConfig(
        level=logging.DEBUG if settings.DEBUG else logging.INFO,
        format=_LOG_FORMAT,
    )


def get_logger(name: str) -> logging.Logger:
    """Retourne un logger nommé (utiliser ``__name__`` comme nom)."""
    return logging.getLogger(name)
