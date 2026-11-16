"""Utilitaires de lecture des dates saisies par l'utilisateur."""
import re
from datetime import datetime
from typing import Optional

_SEPARATORS = ("-", "/", ".")

#: Formats « stricts » (chiffres complets) utilisés pour affiner le motif d'erreur.
#: Les séparateurs acceptés sont les mêmes que ceux de :func:`parse_date`.
_STRICT_DATE_PATTERNS = (
    re.compile(r"\d{4}[-/.]\d{2}[-/.]\d{2}"),  # AAAA-MM-JJ
    re.compile(r"\d{2}[-/.]\d{2}[-/.]\d{4}"),  # JJ-MM-AAAA
)


def parse_date(value: str) -> Optional[datetime]:
    """
    Convertit une date saisie librement en ``datetime``.

    Formats acceptés (séparateur ``-``, ``/`` ou ``.``) :

    * ``AAAA-MM-JJ`` — l'année est détectée en première position ;
    * ``JJ-MM-AAAA`` — l'année est détectée en dernière position.

    Args:
        value: chaîne saisie par l'utilisateur.

    Returns:
        La date correspondante, ou ``None`` si la chaîne est mal formée
        ou désigne une date inexistante (ex. 31 février).
    """
    value = (value or "").strip()

    for separator in _SEPARATORS:
        if separator not in value:
            continue

        parts = value.split(separator)
        if len(parts) != 3:
            continue

        try:
            first, month, last = map(int, parts)
        except ValueError:
            return None

        # L'année est le seul composant à 4 chiffres : sa position donne le format.
        if first > 1000:
            year, day = first, last
        elif last > 1000:
            year, day = last, first
        else:
            return None

        try:
            return datetime(year, month, day)
        except ValueError:
            return None

    return None


def has_strict_date_format(value: str) -> bool:
    """Indique si ``value`` respecte exactement ``AAAA-MM-JJ`` ou ``JJ-MM-AAAA`` (séparateur ``-``, ``/`` ou ``.``)."""
    value = (value or "").strip()
    return any(pattern.fullmatch(value) for pattern in _STRICT_DATE_PATTERNS)
