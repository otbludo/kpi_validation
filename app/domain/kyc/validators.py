"""
Règles de validation locales (déterministes) appliquées aux champs déclarés.

Ces contrôles complètent l'analyse du modèle de vision : ils vérifient le
format et la plausibilité des valeurs indépendamment du document. Une règle
ne peut que **dégrader** un statut (``valid`` → ``invalid``), jamais
l'inverse : le verdict du modèle de vision reste prioritaire.
"""
import re
from datetime import datetime
from typing import Any, Callable, Dict, Optional

from app.domain.kyc.dates import parse_date
from app.domain.kyc.fields import ALLOWED_SEX_VALUES, FieldResults, ValidationStatus

#: Année de naissance minimale acceptée.
MIN_BIRTH_YEAR = 1900

_DOCUMENT_NUMBER_PATTERN = re.compile(r"[A-Za-z0-9]{5,20}")
_FULL_NAME_PATTERN = re.compile(r"[A-Za-zÀ-ÿ\s\-']{2,50}")

#: Une règle reçoit la valeur déclarée (nettoyée) et l'instant de référence.
Rule = Callable[[str, datetime], bool]


def is_valid_birth_date(value: str, now: datetime) -> bool:
    """Date lisible et année comprise entre 1900 et l'année courante."""
    date = parse_date(value)
    return date is not None and MIN_BIRTH_YEAR <= date.year <= now.year


def is_valid_expiration_date(value: str, now: datetime) -> bool:
    """Date lisible et non encore dépassée."""
    date = parse_date(value)
    return date is not None and date >= now


def is_valid_sex(value: str, _now: datetime) -> bool:
    """Valeur présente dans :data:`ALLOWED_SEX_VALUES`."""
    return value.lower() in ALLOWED_SEX_VALUES


def is_valid_document_number(value: str, _now: datetime) -> bool:
    """5 à 20 caractères alphanumériques."""
    return _DOCUMENT_NUMBER_PATTERN.fullmatch(value) is not None


def is_valid_full_name(value: str, _now: datetime) -> bool:
    """2 à 50 lettres (accents, espaces, tirets et apostrophes autorisés)."""
    return _FULL_NAME_PATTERN.fullmatch(value) is not None


#: Association champ → règle de validation.
LOCAL_RULES: Dict[str, Rule] = {
    "date_naissance": is_valid_birth_date,
    "date_expiration": is_valid_expiration_date,
    "sexe": is_valid_sex,
    "num_CNI_passeport": is_valid_document_number,
    "nom_et_prenom": is_valid_full_name,
}


def apply_local_validations(
    results: FieldResults,
    form_data: Any,
    now: Optional[datetime] = None,
) -> None:
    """
    Applique :data:`LOCAL_RULES` et invalide les champs non conformes.

    Seuls les champs déjà présents dans ``results`` sont contrôlés.

    Args:
        results: résultats de validation, **modifiés en place**.
        form_data: formulaire soumis (doit exposer les attributs des champs).
        now: instant de référence (injectable pour les tests).
    """
    now = now or datetime.now()

    for field, rule in LOCAL_RULES.items():
        if not isinstance(results.get(field), dict):
            continue

        declared_value = (getattr(form_data, field, "") or "").strip()
        if not rule(declared_value, now):
            results[field]["status_validation"] = ValidationStatus.INVALID
