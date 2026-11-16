"""
Exceptions métier de l'application.

Les services lèvent ces exceptions plutôt que des ``HTTPException`` :
c'est à la couche API, et à elle seule, de décider du code HTTP renvoyé.
"""


class KYCError(Exception):
    """Classe de base de toutes les erreurs métier du pipeline KYC."""


class InvalidSubmissionError(KYCError, ValueError):
    """
    Le dossier soumis est incomplet ou incohérent (ex. document manquant).

    Hérite de ``ValueError`` pour rester compatible avec le code appelant
    qui intercepte déjà cette exception standard.
    """


class ImageReadError(InvalidSubmissionError):
    """Impossible de lire le contenu d'un fichier image envoyé."""


class VisionAnalysisError(KYCError):
    """Le modèle de vision n'a pas pu analyser la pièce d'identité."""


class EmailDeliveryError(KYCError):
    """L'envoi d'un email a échoué (template introuvable, SMTP indisponible...)."""
