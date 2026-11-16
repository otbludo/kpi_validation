"""
Messages d'erreur exposés par l'API.

Centraliser les libellés évite les chaînes en dur dans le code et facilite
une future internationalisation.
"""

# --- Erreurs HTTP génériques ----------------------------------------------
INVALID_FORM_DATA = "Invalid form data: {}"
INTERNAL_SERVER_ERROR = "Internal server error"

# --- Services --------------------------------------------------------------
EMAIL_SEND_ERROR = "Error sending email: {}"
IMAGE_READ_ERROR = "Unable to read image bytes: {}"
NO_DOCUMENT_IMAGE = "Aucun fichier d'image valide n'a pu être extrait du formulaire."

# --- Authentification ------------------------------------------------------
INVALID_JWT_TOKEN = "Invalid JWT token"
EXPIRED_JWT_TOKEN = "Expired JWT token"

# --- Qualité des documents -------------------------------------------------
BLURRY_DOCUMENT = (
    "Un ou plusieurs documents sont flous ou illisibles. "
    "Veuillez fournir une image plus claire."
)
