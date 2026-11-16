"""
Génération des motifs de rejet lisibles par l'utilisateur final.

Ces motifs alimentent trois sorties : le champ ``description`` de la réponse
API, l'email d'alerte et le ``rejection_reason`` du callback.
"""
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.domain.kyc.dates import has_strict_date_format, parse_date
from app.domain.kyc.fields import (
    ALL_FIELDS,
    FIELD_LABELS,
    FieldResults,
    get_excluded_fields,
    is_invalid,
)
from app.domain.kyc.validators import MIN_BIRTH_YEAR

#: Une anomalie : ``{"label": <libellé du champ>, "reason": <motif>}``.
InvalidField = Dict[str, str]

DEFAULT_REASON = "Ne correspond pas aux informations du document"
INVALID_DATE_FORMAT = "Format de date invalide (attendu: AAAA-MM-JJ ou JJ-MM-AAAA)"

#: Motifs fixes, indépendants de la valeur saisie.
_STATIC_REASONS: Dict[str, str] = {
    "photo_profile": "Photo de profil ne correspond pas à la photo du document",
    "photo_CNI_recto": "Document non fourni",
    "sexe": (
        "Valeur de sexe invalide ou non correspondante au document "
        "(valeurs autorisées: M, F, Masculin, Féminin, Homme, Femme)"
    ),
    "num_CNI_passeport": "Numéro de document invalide (5 à 20 caractères alphanumériques requis)",
    "nom_et_prenom": "Nom et prénom invalide (2 à 50 caractères alphabétiques requis)",
}


def _birth_date_reason(value: str, now: datetime) -> str:
    if not has_strict_date_format(value):
        return INVALID_DATE_FORMAT
    date = parse_date(value)
    if date is None:
        return "Date de naissance invalide"
    if not MIN_BIRTH_YEAR <= date.year <= now.year:
        return "Année de naissance invalide"
    return DEFAULT_REASON


def _expiration_date_reason(value: str, now: datetime) -> str:
    if not has_strict_date_format(value):
        return INVALID_DATE_FORMAT
    date = parse_date(value)
    if date is None:
        return "Date d'expiration invalide"
    if date < now:
        return "Date d'expiration déjà passée"
    return DEFAULT_REASON


def get_invalid_reason(field: str, form_data: Any, now: Optional[datetime] = None) -> str:
    """
    Explique pourquoi ``field`` a été jugé invalide.

    Pour les dates, le motif est affiné (format, date impossible, borne
    dépassée) ; à défaut on considère que la valeur ne correspond pas au
    document.
    """
    now = now or datetime.now()

    # La valeur déclarée n'est lue que pour les dates : les autres champs ont
    # un motif fixe, et les champs photo contiennent un fichier, pas du texte.
    if field == "date_naissance":
        return _birth_date_reason(_declared_text(form_data, field), now)
    if field == "date_expiration":
        return _expiration_date_reason(_declared_text(form_data, field), now)
    return _STATIC_REASONS.get(field, DEFAULT_REASON)


def _declared_text(form_data: Any, field: str) -> str:
    """Valeur texte déclarée pour ``field``, nettoyée (``""`` si absente)."""
    return (getattr(form_data, field, "") or "").strip()


def collect_invalid_fields(results: FieldResults, form_data: Any) -> List[InvalidField]:
    """
    Liste les champs invalides pertinents, avec leur libellé et leur motif.

    Les champs non applicables au type de document (ex. photo de passeport
    pour un dossier CNI) sont ignorés.
    """
    excluded = get_excluded_fields(form_data.type_document)
    return [
        {"label": FIELD_LABELS.get(field, field), "reason": get_invalid_reason(field, form_data)}
        for field in ALL_FIELDS
        if field not in excluded and is_invalid(results, field)
    ]


def build_rejection_reason(invalid_fields: List[InvalidField]) -> str:
    """
    Agrège les anomalies en une phrase unique.

    Returns:
        Une chaîne vide si aucune anomalie, sinon
        ``"Champs invalides ... : Label (motif), Label (motif)."``.
    """
    if not invalid_fields:
        return ""
    parts = ", ".join(f"{item['label']} ({item['reason']})" for item in invalid_fields)
    return f"Champs invalides ou non conformes à la pièce d'identité : {parts}."
