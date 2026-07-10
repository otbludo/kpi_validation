# Intégration de la route KYC

## Endpoint

```
POST /api/v1/kyc/process
```

Traite un dossier KYC complet et retourne un score de validation par champ.

---

## Request

### Content-Type

```
multipart/form-data
```

### Champs

| Paramètre | Type | Requis | Description |
|-----------|------|--------|-------------|
| `photo_profile` | UploadFile (image) | Oui | Selfie de l'utilisateur |
| `photo_CNI_recto` | UploadFile (image) | Non | Recto de la CNI |
| `photo_CNI_verso` | UploadFile (image) | Non | Verso de la CNI (optionnel si passeport) |
| `photo_passeport` | UploadFile (image) | Non | Passeport (optionnel si CNI fournie) |
| `type_document` | str | Oui | `CNI` ou `passeport` |
| `kyc_id` | str | Oui | Identifiant unique du dossier |
| `nom_et_prenom` | str | Oui | Nom complet déclaré |
| `adresse_mail` | EmailStr | Oui | Adresse email valide |
| `profession` | str | Oui | Profession déclarée |
| `numero_NUI` | str | Oui | Numéro Unique d'Identification |
| `date_naissance` | str | Oui | Format `AAAA-MM-JJ` |
| `sexe` | str | Oui | Genre (ex: `M`, `F`) |
| `pays` | str | Oui | Pays de résidence |
| `region` | str | Oui | Région de résidence |
| `ville` | str | Oui | Ville de résidence |
| `adresse` | str | Oui | Adresse de domicile fixe |
| `num_CNI_passeport` | str | Oui | Numéro de la pièce d'identité |
| `date_expiration` | str | Oui | Date d'expiration de la pièce (`AAAA-MM-JJ`) |
| `registre_commerce` | str | Non | Numéro de registre de commerce |
| `code_postal` | str | Non | Code postal |

### Règles de validation

- Si `type_document = CNI`, `photo_CNI_recto` est obligatoire.
- Si `type_document = passeport`, `photo_passeport` est obligatoire.
- Les images fournies sont analysées par un modèle de vision (Groq) pour vérifier la cohérence des champs `nom_et_prenom`, `date_naissance`, `sexe` et `num_CNI_passeport`.
- Le `photo_profile` est confronté à la photo du document (CNI recto/verso ou passeport) via InsightFace. Si les visages ne correspondent pas, le champ `photo_profile` passe en `invalid` et impacte le score global.

---

## Response

### Succès (200)

```json
{
  "donnees_output": {
    "photo_profile": {
      "value": "fourni",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "nom_et_prenom": {
      "value": "Jean Dupont",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "adresse_mail": {
      "value": "user@example.com",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "profession": {
      "value": "Ingénieur",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "numero_NUI": {
      "value": "NUI123",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "registre_commerce": {
      "value": "",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "date_naissance": {
      "value": "2000-01-02",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "sexe": {
      "value": "M",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "pays": {
      "value": "Cameroun",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "region": {
      "value": "Centre",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "ville": {
      "value": "Yaoundé",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "adresse": {
      "value": "Rue 1",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "code_postal": {
      "value": "",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "num_CNI_passeport": {
      "value": "ABC123",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "date_expiration": {
      "value": "2035-01-01",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "photo_CNI_recto": {
      "value": "fourni",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "photo_CNI_verso": {
      "value": "fourni",
      "status_validation": "valid",
      "percentage": 5.56
    },
    "photo_passeport": {
      "value": "non_fourni",
      "status_validation": "not_required",
      "percentage": 0.0
    },
    "total_percentage": 100.0,
    "state_status": "valide"
  }
}
```

### Champs de la réponse

| Champ | Type | Description |
|-------|------|-------------|
| `value` | any | Valeur brute analysée ou statut de présence |
| `status_validation` | str | `valid`, `invalid` ou `not_required` |
| `percentage` | float | Part du score attribuée au champ (0 si `not_required`) |
| `total_percentage` | float | Score global sur 100 |
| `state_status` | str | `valide` si tous les champs actifs sont valides, sinon `invalide` |

---

## Codes d'erreur

| Code | Message | Cas |
|------|---------|-----|
| 400 | `Données de formulaire invalides : ...` | Champs manquants ou incohérents (`type_document` sans la photo correspondante) |
| 422 | Erreur de validation FastAPI | Format des champs invalide (email, dates, etc.) |
| 500 | `Erreur d'infrastructure interne : ...` | Erreur inattendue lors du traitement |

---

## Effets de bord

### 1. Notification email (Mailtrap)

Si des champs sont invalides, un email de type `warning` est envoyé à `adresse_mail` via le template Mailtrap configuré.

Variables du template `warning` :
- `user_name`
- `invalid_fields` (HTML)
- `total_percentage`

### 2. Callback HTTP (KYC Callback)

Après traitement, un `POST` est envoyé à `KYC_CALLBACK_URL` avec :

```json
{
  "kyc_id": "kyc-123",
  "ai_confidence_score": 88.89,
  "rejection_reason": "Champs invalides ou non conformes à la pièce d'identité : Nom et prénom, Sexe."
}
```

En-tête :
```
Authorization: Bearer <KYC_CALLBACK_TOKEN>
Content-Type: application/json
```

Le callback échoue silencieusement si le service distant est indisponible (pas de levée d'exception).

---

## Configuration

### Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `GROQ_API_KEY` | - | Clé API Groq pour le modèle de vision |
| `SMTP_HOST` | `sandbox.smtp.mailtrap.io` | Hôte SMTP |
| `SMTP_PORT` | `2525` | Port SMTP |
| `SMTP_USER` | - | Utilisateur SMTP |
| `SMTP_PASSWORD` | - | Mot de passe SMTP |
| `EMAIL_FROM` | - | Expéditeur des emails |
| `EMAIL_FROM_NAME` | `KYC Service` | Nom de l'expéditeur |
| `DATA_PROVIDER_URL` | - | URL du microservice de données brutes |
| `KYC_CALLBACK_URL` | - | URL du callback de notification |
| `KYC_CALLBACK_TOKEN` | - | Token Bearer pour le callback |
| `KYC_CALLBACK_TIMEOUT` | `10` | Timeout du callback en secondes |
| `ALLOWED_ORIGINS` | `*` | Origines CORS autorisées |
| `OCR_LANGUAGE` | `fra` | Langue OCR |
| `DEBUG` | `False` | Mode debug |
| `INSIGHTFACE_MODEL` | `buffalo_l` | Modèle InsightFace pour la reconnaissance faciale |
| `INSIGHTFACE_PROVIDERS` | `CPUExecutionProvider` | Backends d'exécution InsightFace |
| `INSIGHTFACE_THRESHOLD` | `0.40` | Seuil de similarité InsightFace (cosine >= seuil = match) |
| `INSIGHTFACE_CTX_ID` | `-1` | ID de contexte InsightFace (-1 = CPU, 0 = GPU) |

---

## Exemples d'intégration

### cURL

```bash
curl -X POST "http://localhost:8000/api/v1/kyc/process" \
  -F "photo_profile=@/path/to/selfie.jpg" \
  -F "photo_CNI_recto=@/path/to/cni_recto.jpg" \
  -F "photo_CNI_verso=@/path/to/cni_verso.jpg" \
  -F "type_document=CNI" \
  -F "kyc_id=kyc-123" \
  -F "nom_et_prenom=Jean Dupont" \
  -F "adresse_mail=user@example.com" \
  -F "profession=Ingénieur" \
  -F "numero_NUI=NUI123" \
  -F "date_naissance=2000-01-02" \
  -F "sexe=M" \
  -F "pays=Cameroun" \
  -F "region=Centre" \
  -F "ville=Yaoundé" \
  -F "adresse=Rue 1" \
  -F "num_CNI_passeport=ABC123" \
  -F "date_expiration=2035-01-01"
```

### Python (requests)

```python
import requests

url = "http://localhost:8000/api/v1/kyc/process"
files = {
    "photo_profile": open("selfie.jpg", "rb"),
    "photo_CNI_recto": open("cni_recto.jpg", "rb"),
}
data = {
    "type_document": "CNI",
    "kyc_id": "kyc-123",
    "nom_et_prenom": "Jean Dupont",
    "adresse_mail": "user@example.com",
    "profession": "Ingénieur",
    "numero_NUI": "NUI123",
    "date_naissance": "2000-01-02",
    "sexe": "M",
    "pays": "Cameroun",
    "region": "Centre",
    "ville": "Yaoundé",
    "adresse": "Rue 1",
    "num_CNI_passeport": "ABC123",
    "date_expiration": "2035-01-01",
}

response = requests.post(url, files=files, data=data)
result = response.json()
print(result["donnees_output"]["state_status"])
print(result["donnees_output"]["total_percentage"])
```

### JavaScript (fetch)

```javascript
const formData = new FormData();
formData.append("photo_profile", fileInput.files[0]);
formData.append("type_document", "CNI");
formData.append("kyc_id", "kyc-123");
formData.append("nom_et_prenom", "Jean Dupont");
formData.append("adresse_mail", "user@example.com");

const response = await fetch("http://localhost:8000/api/v1/kyc/process", {
  method: "POST",
  body: formData,
});

const result = await response.json();
console.log(result.donnees_output.state_status);
```

---

## Déploiement

### Docker Compose

```bash
docker compose up --build
```

L'API est accessible sur `http://localhost:8000`.

### Health check

```bash
curl http://localhost:8000/health
```

Réponse :
```json
{
  "status": "healthy",
  "service": "KYC Validation Pipeline",
  "version": "1.0.0"
}
```

---

## Tests

```bash
pytest tests/test_api.py -v
```

Les tests couvrent :
- Health check
- Validation du formulaire (422)
- Flux complet avec agent mocké
- Gestion des erreurs internes (500)
