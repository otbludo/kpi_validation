"""
Prompts envoyés au modèle de vision.

Les isoler du code d'orchestration permet de les relire, les versionner et
les ajuster sans risquer de modifier la logique du pipeline.
"""
from typing import Any

#: Champs attendus dans la réponse JSON du modèle (ordre du schéma).
PROMPT_FIELDS = (
    "nom_et_prenom",
    "date_naissance",
    "sexe",
    "pays",
    "region",
    "num_CNI_passeport",
    "date_expiration",
)

#: Ordre de présentation des déclarations. Il diffère de :data:`PROMPT_FIELDS`
#: et est conservé tel quel : le prompt a été évalué sous cette forme, et
#: toute modification peut influer sur la précision du modèle.
DECLARED_FIELDS_ORDER = (
    "nom_et_prenom",
    "sexe",
    "date_naissance",
    "num_CNI_passeport",
    "date_expiration",
    "pays",
    "region",
)

BLUR_CHECK_PROMPT = (
    "Évalue UNIQUEMENT la netteté de la prise de vue de cette image. "
    "Considère uniquement s'il y a un flou de bougé ou un problème de mise au point (optique).\n\n"
    "ATTENTION : Si le document papier est vieux, usé, plié ou taché, mais que la photo est "
    "NETTE et pas floue, réponds 'lisible'.\n\n"
    "Règles de réponse :\n"
    "- Réponds 'flou' SEULEMENT si l'image elle-même souffre d'un flou d'appareil photo "
    "(flou de bougé ou mise au point ratée).\n"
    "- Réponds 'lisible' si la prise de vue est nette et stable, même si le document "
    "d'origine est usé ou ancien.\n\n"
    "Réponds UNIQUEMENT par le mot 'flou' ou 'lisible', sans aucun autre mot ni ponctuation."
)

_KYC_PROMPT_TEMPLATE = """
Tu es un système expert de validation KYC par vision artificielle. Tu devras IMPÉRATIVEMENT analyser les images de la pièce d'identité fournies pour vérifier les déclarations de l'utilisateur.

Données déclarées par l'utilisateur :
{declared_values}

Consignes d'analyse visuelle ultra-strictes :
1. Regarde TRÈS ATTENTIVEMENT les images de la pièce d'identité jointes (Recto et Verso ou Passeport). Ne devine pas, lis ce qui est écrit sur les documents.
2. Compare chaque champ déclaré avec ce que tu vois écrit sur les images :
   - Si les caractères sur les documents sont différents du texte déclaré, mets "status_validation": "invalid".
   - Si et seulement si ça correspond exactement (présent sur le Recto, le Verso ou le Passeport), mets "status_validation": "valid".
3. Sois impitoyable : si l'utilisateur a triché ou mis des données erronées (mauvais nom, mauvaise date, mauvais numéro de document, pays incorrect, région incorrecte, ville incorrecte), tu DOIS retourner "invalid" pour ce champ.
4. Les dates peuvent être fournies au format AAAA-MM-JJ ou JJ-MM-AAAA.

IMPORTANT : Retourne UNIQUEMENT un objet JSON valide, sans aucun texte supplémentaire, sans markdown, sans ```json.

Format JSON attendu (ne retourne que les champs listés ci-dessous avec leurs statuts) :
{{
{expected_json}
}}
"""


def build_kyc_validation_prompt(form_data: Any) -> str:
    """
    Construit le prompt demandant au modèle de confronter les déclarations
    de l'utilisateur au contenu de sa pièce d'identité.

    Args:
        form_data: formulaire soumis (attributs listés dans :data:`PROMPT_FIELDS`).

    Returns:
        Le prompt complet, incluant le schéma JSON de réponse attendu.
    """
    values = {field: getattr(form_data, field, "") for field in PROMPT_FIELDS}

    declared_values = "\n".join(f"- {field} : {values[field]}" for field in DECLARED_FIELDS_ORDER)

    expected_json = ",\n".join(
        f'    "{field}": {{"value": "{values[field]}", "status_validation": "valid"}}'
        for field in PROMPT_FIELDS
    )

    return _KYC_PROMPT_TEMPLATE.format(
        declared_values=declared_values,
        expected_json=expected_json,
    )
