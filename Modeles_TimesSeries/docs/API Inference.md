# API Inference

## Rôle et positionnement

L'API Inference est le **cœur opérationnel du projet**. Elle orchestre l'ensemble du pipeline machine learning : récupération des données, entraînement, génération de prédictions et exposition des résultats.

**Ce que fait cette API :**

- synchroniser les historiques depuis `api-dataclean` vers le disque local,
- lancer l'entraînement d'un modèle Prophet pour un PRM donné,
- générer des prédictions sur un horizon futur,
- exposer les résultats en JSON,
- lire les prédictions stockées dans Fabric.

**Ce que ne fait pas cette API :**

- elle ne stocke pas elle-même dans Fabric (c'est configurable via variables d'environnement),
- elle ne gère pas les permissions utilisateur au-delà de la clé API.

> Pour un nouveau développeur : cette API est le chef d'orchestre. Elle sait qui appeler et dans quel ordre pour produire une prédiction.

---

## Architecture interne

```
api-inference/
│
├── app/
│   ├── main.py                    # Point d'entrée FastAPI
│   ├── settings.py                # Lecture des variables d'environnement
│   ├── security.py                # Vérification de l'en-tête X-API-Key
│   ├── logging_utils.py           # Logs structurés avec corrélation de requêtes
│   ├── project_paths.py           # Résolution du chemin racine du projet
│   ├── config/
│   │   ├── database.py            # Connexion DB/Fabric
│   │   └── fabric_automation.py   # Automatisation OneLake/Notebook
│   ├── repository/
│   │   └── fabric_repository.py   # Lecture des prédictions/modèles depuis Fabric
│   └── routers/
│       ├── health.py              # GET /health
│       ├── sync.py                # POST /sync/prm/{prm}
│       ├── predict.py             # POST /predict/prm/{prm}
│       └── models.py              # GET /models/list + routes registre
│
├── tests/
├── requirements.txt
├── Dockerfile
├── .env
└── README.md
```

**Principes de conception :**

- chaque router délègue le traitement à un service (dans `src/`),
- la sécurité est centralisée dans `security.py` (middleware et dépendance FastAPI),
- `settings.py` centralise toutes les variables d'environnement (pas de `os.environ` dispersés).

---

## Prérequis

- Python 3.11
- `api-dataclean` accessible (locale ou Docker)
- Modèles Prophet présents dans `models/saved/` pour les endpoints de prédiction
- ODBC Driver 17 si les endpoints Fabric sont activés

---

## Configuration (`.env`)

```env
# URL de l'API de données (internal Docker ou localhost)
DATACLEAN_BASE_URL=http://127.0.0.1:8000

# Clé d'authentification pour les endpoints protégés
INFERENCE_API_KEY=dev-inference-key

# Origines autorisées pour CORS (dashboard, Fabric…)
CORS_ORIGINS=*

# URI MLflow (local ou distant)
MLFLOW_TRACKING_URI=./mlruns

# Connexion Fabric (optionnel selon routes activées)
DB_SERVER=...
DB_DATABASE=...
DB_USER=...
DB_PASSWORD=...
```

Note : en Docker Compose, `DATACLEAN_BASE_URL` devient `http://api-dataclean:8000` (nom du service Docker).

---

## Installation et lancement local

```bash
cd api/api-inference

python -m venv env_api

# Windows
.\env_api\Scripts\Activate.ps1
# macOS/Linux
source env_api/bin/activate

pip install -r requirements.txt

uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

- API : http://127.0.0.1:8001
- Documentation Swagger interactive : http://127.0.0.1:8001/docs

---

## Endpoints disponibles

### Statut de l'API

```
GET /health
```

```json
{"status": "API inference ok"}
```

---

### Liste des modèles disponibles

```
GET /models/list
```

Liste les fichiers `prophet_model_<prm>_latest.pkl` présents dans `models/saved/`.

```json
{"models": ["30000250086126", "30000650805048"]}
```

---

### Synchronisation d'un PRM (protégé)

```
POST /sync/prm/{prm}
Header: X-API-Key: <votre_clé>
```

Télécharge l'historique JSON depuis `api-dataclean` et l'écrit dans :
`data/raw/sites/dataclean_prm_{prm}.csv`

```bash
curl -X POST "http://127.0.0.1:8001/sync/prm/30000250086126" \
  -H "X-API-Key: dev-inference-key"
```

---

### Prédiction Prophet (protégé)

```
POST /predict/prm/{prm}
Header: X-API-Key: <votre_clé>
```

Pipeline complet déclenché en interne :

1. récupère l'historique JSON depuis `api-dataclean`,
2. génère la météo future,
3. applique le feature engineering,
4. charge le modèle Prophet sauvegardé,
5. génère les prédictions,
6. retourne la série en JSON.

```bash
curl -X POST "http://127.0.0.1:8001/predict/prm/30000250086126" \
  -H "X-API-Key: dev-inference-key"
```

Réponse (structure) :

```json
{
  "prm": "30000250086126",
  "message": "Prédiction générée avec succès",
  "rows": 336,
  "start": "2026-04-29T00:00:00",
  "end": "2026-05-13T23:00:00"
}
```

---

### Dernière prédiction stockée (protégé)

```
GET /predictions/prm/{prm}/latest
Header: X-API-Key: <votre_clé>
```

Lit la dernière prédiction disponible depuis Fabric.

```bash
curl "http://127.0.0.1:8001/predictions/prm/30000250086126/latest" \
  -H "X-API-Key: dev-inference-key"
```

---

## Exemples Python

### Déclencher une prédiction

```python
import requests

PRM = "30000250086126"
headers = {"X-API-Key": "dev-inference-key"}

response = requests.post(
    f"http://127.0.0.1:8001/predict/prm/{PRM}",
    headers=headers,
    timeout=180,
)
response.raise_for_status()
print(response.json())
```

### Lire la dernière prédiction

```python
import requests

PRM = "30000250086126"
headers = {"X-API-Key": "dev-inference-key"}

response = requests.get(
    f"http://127.0.0.1:8001/predictions/prm/{PRM}/latest",
    headers=headers,
    timeout=60,
)
response.raise_for_status()
data = response.json()
print("Source:", data.get("source"))
print("Nombre de points:", data.get("rows"))
```

---

## Sécurité

L'authentification repose sur une **clé API statique** passée dans l'en-tête HTTP `X-API-Key`.

- La clé est définie dans `INFERENCE_API_KEY` (variable d'environnement).
- Si la clé est absente ou incorrecte, l'API retourne `401 Unauthorized`.
- En production, remplacez `dev-inference-key` par une valeur aléatoire longue.

Ce système est simple et adapté à un usage interne ou en tunnel ngrok. Pour un usage public, envisagez OAuth2 ou JWT.

---

## Déploiement Docker

```bash
# Construire l'image depuis la racine du projet
docker build -f api/api-inference/Dockerfile -t api-inference .

# Lancer le conteneur
docker run -p 8001:8001 --env-file api/api-inference/.env api-inference
```

---

## Tests

```bash
# Depuis api/api-inference/
pytest tests/

# Ou depuis la racine du projet
pytest tests/
```

---

## Dépannage

| Erreur | Cause | Solution |
|---|---|---|
| `401 Clé API invalide` | En-tête `X-API-Key` manquant ou incorrect | Vérifier `INFERENCE_API_KEY` dans `.env` |
| `502 Dataclean indisponible` | `api-dataclean` éteinte | Vérifier que l'API Dataclean tourne et `DATACLEAN_BASE_URL` |
| `404 Modèle Prophet introuvable` | Fichier `.pkl` absent | Lancer l'entraînement : `POST /sync` puis `python main.py train --prm <PRM>` |
| `503 Erreur Fabric` | Variables DB incorrectes | Vérifier `DB_SERVER`, `DB_DATABASE`, droits de connexion |
