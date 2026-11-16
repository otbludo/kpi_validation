"""
Calcul du score de confiance d'un dossier KYC.

Principe : le score part de 100 et chaque champ invalide retire la pénalité
définie dans :data:`FIELD_PENALTIES`. Le dossier est déclaré valide si le
score final atteint :data:`VALIDITY_THRESHOLD`.
"""
from typing import Any

from app.domain.kyc.fields import (
    ALL_FIELDS,
    FIELD_PENALTIES,
    VALIDITY_THRESHOLD,
    DossierStatus,
    FieldResults,
    get_excluded_fields,
    is_invalid,
)

MAX_SCORE = 100.0


def compute_scores(results: FieldResults, form_data: Any) -> None:
    """
    Calcule les pénalités par champ, le score global et l'état du dossier.

    Effets sur ``results`` (modifié en place) :

    * ``results[champ]["percentage"]`` : pénalité appliquée (0 si aucune) ;
    * ``results["total_percentage"]`` : score final borné à [0, 100] ;
    * ``results["state_status"]`` : ``"valide"`` ou ``"invalide"``.

    Args:
        results: résultats de validation contenant tous les champs de
            :data:`ALL_FIELDS`.
        form_data: formulaire soumis (seul ``type_document`` est utilisé).
    """
    excluded = get_excluded_fields(form_data.type_document)
    score = MAX_SCORE

    for field in ALL_FIELDS:
        penalty = 0.0
        if field not in excluded and field in FIELD_PENALTIES and is_invalid(results, field):
            penalty = FIELD_PENALTIES[field]
            score -= penalty
        results[field]["percentage"] = penalty

    score = max(0.0, score)
    results["total_percentage"] = round(score, 2)
    results["state_status"] = (
        DossierStatus.VALID if score >= VALIDITY_THRESHOLD else DossierStatus.INVALID
    )
