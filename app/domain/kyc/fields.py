"""
Référentiel des champs d'un dossier KYC.

Ce module est la **source unique de vérité** sur les champs manipulés par le
pipeline : leur ordre, leur libellé lisible, leur poids dans le score et leur
pertinence selon le type de pièce d'identité.
"""
from typing import Any, Dict, FrozenSet

#: Résultat de validation d'un dossier : ``{champ: {"value", "status_validation", "percentage"}}``.
FieldResults = Dict[str, Dict[str, Any]]


class DocumentType:
    """Types de pièce d'identité acceptés."""

    CNI = "CNI"
    PASSPORT = "passeport"


class ValidationStatus:
    """Statuts possibles d'un champ après validation."""

    VALID = "valid"
    INVALID = "invalid"
    NOT_REQUIRED = "not_required"


class DossierStatus:
    """État global d'un dossier KYC."""

    VALID = "valide"
    INVALID = "invalide"


class PhotoValue:
    """Valeur affichée pour un champ photo (le contenu binaire n'est pas renvoyé)."""

    PROVIDED = "fourni"
    NOT_PROVIDED = "non_fourni"


#: Tous les champs du dossier, dans l'ordre de restitution.
ALL_FIELDS = (
    "photo_profile",
    "nom_et_prenom",
    "adresse_mail",
    "profession",
    "numero_NUI",
    "registre_commerce",
    "date_naissance",
    "sexe",
    "pays",
    "region",
    "ville",
    "adresse",
    "code_postal",
    "num_CNI_passeport",
    "date_expiration",
    "photo_CNI_recto",
    "photo_CNI_verso",
    "photo_passeport",
)

#: Champs dont la valeur est confrontée à la pièce d'identité par le modèle de vision.
#: Les autres champs textuels sont déclaratifs et considérés valides d'office.
VERIFIED_FIELDS: FrozenSet[str] = frozenset({
    "nom_et_prenom",
    "date_naissance",
    "sexe",
    "num_CNI_passeport",
    "date_expiration",
    "pays",
    "ville",
})

#: Champs contenant une image (traités séparément des champs textuels).
PHOTO_FIELDS: FrozenSet[str] = frozenset({
    "photo_profile",
    "photo_CNI_recto",
    "photo_CNI_verso",
    "photo_passeport",
})

#: Libellés lisibles utilisés dans les emails et les motifs de rejet.
FIELD_LABELS: Dict[str, str] = {
    "photo_profile": "Photo de profil",
    "nom_et_prenom": "Nom et prénom",
    "adresse_mail": "Adresse mail",
    "profession": "Profession",
    "numero_NUI": "Numéro NUI",
    "registre_commerce": "Registre de commerce",
    "date_naissance": "Date de naissance",
    "sexe": "Sexe",
    "pays": "Pays",
    "region": "Région",
    "ville": "Ville",
    "adresse": "Adresse",
    "code_postal": "Code postal",
    "num_CNI_passeport": "Numéro CNI / Passeport",
    "date_expiration": "Date d'expiration",
    "photo_CNI_recto": "Photo CNI (Recto)",
    "photo_CNI_verso": "Photo CNI (Verso)",
    "photo_passeport": "Photo passeport",
}

#: Points retirés au score global (sur 100) lorsqu'un champ est invalide.
#: Un champ absent de ce dictionnaire n'impacte pas le score.
FIELD_PENALTIES: Dict[str, float] = {
    "photo_profile": 50,
    "photo_CNI_recto": 50,
    "photo_CNI_verso": 50,
    "photo_passeport": 50,
    "nom_et_prenom": 30,
    "date_naissance": 30,
    "sexe": 20,
    "pays": 25,
    "num_CNI_passeport": 50,
    "date_expiration": 30,
}

#: Score minimal (inclus) pour qu'un dossier soit déclaré valide.
VALIDITY_THRESHOLD = 60.0

#: Valeurs acceptées pour le champ ``sexe`` (comparaison insensible à la casse).
ALLOWED_SEX_VALUES: FrozenSet[str] = frozenset(
    {"m", "f", "masculin", "feminin", "homme", "femme"}
)


def get_excluded_fields(document_type: str) -> FrozenSet[str]:
    """
    Retourne les champs photo non pertinents pour le type de document fourni.

    Un dossier CNI n'a pas de photo de passeport et inversement : ces champs
    sont ignorés dans le score et dans la liste des anomalies.

    Args:
        document_type: ``"CNI"`` ou ``"passeport"``.
    """
    if document_type == DocumentType.CNI:
        return frozenset({"photo_passeport"})
    return frozenset({"photo_CNI_recto", "photo_CNI_verso"})


def is_invalid(results: FieldResults, field: str) -> bool:
    """Indique si ``field`` est marqué invalide dans ``results``."""
    return results.get(field, {}).get("status_validation") == ValidationStatus.INVALID
