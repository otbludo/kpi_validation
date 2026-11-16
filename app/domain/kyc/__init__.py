"""
Logique métier du KYC, indépendante de toute infrastructure.

Les modules de ce paquet sont **purs** : aucun appel réseau, aucune lecture
de fichier. Ils sont donc testables unitairement et réutilisables hors API.

* :mod:`fields` — référentiel des champs, libellés et pénalités ;
* :mod:`dates` — lecture des dates saisies ;
* :mod:`validators` — contrôles de format et de plausibilité ;
* :mod:`scoring` — calcul du score de confiance ;
* :mod:`reasons` — motifs de rejet lisibles ;
* :mod:`prompts` — prompts envoyés au modèle de vision.
"""
