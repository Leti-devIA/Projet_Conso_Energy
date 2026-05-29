
# API Inference

L'API Inference sert de **pont applicatif** entre :

1. les données historiques fournies par `api-dataclean`,
2. les modèles Prophet entraînés,
3. les consommateurs métier (dashboard, scripts, automatisations Fabric).

Elle permet de synchroniser les historiques, lancer des prédictions et exposer les résultats sous forme d'endpoints REST.

---

## 1) Objectif

Pour un étudiant data/IA, cette API montre un cas concret de mise en production :

- appel API → pipeline ML → réponse JSON,
- séparation claire entre ingestion de données (`api-dataclean`) et inférence (`api-inference`),
- gestion d'authentification simple via clé API,
- intégration avec Fabric/MLflow.

---

## 2) Fonctionnalités principales

- **Health check** de l'API (`/health`)
- **Synchronisation** d'un historique PRM depuis `api-dataclean` vers `data/raw/sites`
- **Prédiction Prophet** par PRM (`POST /predict/prm/{prm}`)
- **Lecture de la dernière prédiction** depuis Fabric (`GET /predictions/prm/{prm}/latest`)
- **Listing des modèles disponibles** (`GET /models/list`)
- **Routes modèles avancées** (registre/modèle actif/push vers Fabric selon configuration)

---

## 3) Structure du projet

```
api-inference/
│
├── app/
│   ├── main.py                    # Entrée FastAPI, CORS, routers
│   ├── settings.py                # Variables d'environnement et chemins
│   ├── security.py                # Vérification X-API-Key
│   ├── logging_utils.py           # Logs + corrélation de requêtes
│   ├── project_paths.py           # Résolution de la racine projet
│   ├── config/
│   │   ├── database.py            # Connexion DB/Fabric
│   │   └── fabric_automation.py   # Automatisation OneLake/Notebook
│   ├── repository/
│   │   └── fabric_repository.py   # Accès données prédictions/modèles
│   └── routers/
│       ├── health.py
│       ├── sync.py
│       ├── predict.py
│       └── models.py
│
├── tests/
├── requirements.txt
├── Dockerfile
├── .env
└── README.md
```

---

## 4) Prérequis

- Python 3.11 recommandé
- `pip`
- Accès à `api-dataclean` (local ou Docker)
- Modèles Prophet présents dans `models/saved/` (racine projet)
- Accès DB/Fabric si endpoints Fabric utilisés

---

## 5) Configuration (`.env`)

Variables essentielles :

```env
DATACLEAN_BASE_URL=http://127.0.0.1:8000
INFERENCE_API_KEY=dev-inference-key
CORS_ORIGINS=*
MLFLOW_TRACKING_URI=./mlruns
```

Variables DB/Fabric (selon vos routes actives) :

```env
DB_SERVER=...
DB_DATABASE=...
DB_USER=...
DB_PASSWORD=...
```

Notes :

- en Docker Compose, `DATACLEAN_BASE_URL` devient souvent `http://api-dataclean:8000`
- les endpoints protégés exigent l'en-tête `X-API-Key`

---

## 6) Installation et lancement local

```bash
cd api/api-inference
python -m venv env_api
```

- Windows PowerShell :
```powershell
.\env_api\Scripts\Activate.ps1
```

- macOS/Linux :
```bash
source env_api/bin/activate
```

Installer les dépendances :

```bash
pip install -r requirements.txt
```

Lancer l'API en local :

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

URLs utiles :

- API : http://127.0.0.1:8001
- Swagger : http://127.0.0.1:8001/docs

---

## 7) Endpoints principaux

### Vue d'ensemble

| Méthode | Endpoint | Auth `X-API-Key` | Description |
|---|---|---|---|
| GET | `/health` | Non | Vérifie que l'API est opérationnelle (health check technique). |
| POST | `/sync/prm/{prm}` | Oui | Synchronise un PRM en téléchargeant son CSV depuis `api-dataclean`, puis enregistre le fichier dans `data/raw/sites/`. Retourne le nombre de lignes importées. |
| POST | `/predict/prm/{prm}` | Oui | Lance une prédiction complète pour un PRM : historique Dataclean → météo future → modèle Prophet → réponse JSON + sauvegarde CSV locale. |
| GET | `/predictions/prm/{prm}/latest` | Oui | Retourne la dernière prédiction d'un PRM avec fallback progressif : cache mémoire, puis CSV local, puis Fabric ; `force_refresh=true` permet de recalculer. |
| POST | `/predict/all/regenerate` | Oui | Démarre un job asynchrone de régénération des prédictions pour tous les PRM disposant d'un modèle `_latest.pkl`. |
| GET | `/predict/all/regenerate/{job_id}` | Oui | Donne l'état d'avancement d'un job de régénération globale (done, ok, failed, durée, erreurs). |
| GET | `/models/list` | Non | Liste les modèles locaux disponibles détectés dans `models/saved` (fichiers `*_latest.pkl`). |
| GET | `/models/prm/{prm}` | Non | Retourne le modèle actif pour un PRM (source Fabric si disponible, sinon fallback fichier local). |
| GET | `/models/latest` | Non | Expose l'ensemble des derniers modèles entraînés, enrichis avec les métriques MLflow. |
| GET | `/models/latest/ia-models` | Non | Fournit un payload prêt à insérer dans la table Fabric `ia_models` (mapping orienté ingestion). |

## Santé
- `GET /health`

## Synchronisation (protégé)
- `POST /sync/prm/{prm}`
- Télécharge un CSV depuis `api-dataclean` et l'écrit dans `data/raw/sites/dataclean_prm_{prm}.csv`

Exemple :
```bash
curl -X POST "http://127.0.0.1:8001/sync/prm/30000250086126" \
  -H "X-API-Key: dev-inference-key"
```

## Prédiction Prophet (protégé)
- `POST /predict/prm/{prm}`
- Étapes internes :
  1. récupère l'historique JSON depuis `api-dataclean`,
  2. génère la météo future,
  3. lance la prédiction Prophet,
  4. retourne la série en JSON.

Exemple :
```bash
curl -X POST "http://127.0.0.1:8001/predict/prm/30000250086126" \
  -H "X-API-Key: dev-inference-key"
```

## Dernière prédiction (protégé)
- `GET /predictions/prm/{prm}/latest`
- Lit les prédictions depuis Fabric (table dédiée)

Exemple :
```bash
curl "http://127.0.0.1:8001/predictions/prm/30000250086126/latest" \
  -H "X-API-Key: dev-inference-key"
```

## Régénération globale (protégé)
- `POST /predict/all/regenerate`
- Lance un job asynchrone pour recalculer toutes les prédictions disponibles.

Exemple :
```bash
curl -X POST "http://127.0.0.1:8001/predict/all/regenerate" \
  -H "X-API-Key: dev-inference-key"
```

- `GET /predict/all/regenerate/{job_id}`
- Retourne le statut détaillé du job (progression, succès/échecs, erreurs).

## Modèles
- `GET /models/list` : liste les modèles `_latest.pkl` détectés
- `GET /models/prm/{prm}` : retourne le modèle actif pour un PRM
- `GET /models/latest` : retourne tous les derniers modèles + métriques MLflow
- `GET /models/latest/ia-models` : payload orienté ingestion Fabric (`ia_models`)

---

## 8) Exemples Python

### Lancer une prédiction

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

payload = response.json()
print(payload["message"], payload["rows"])
print(payload["start"], "->", payload["end"])
```

### Lire la dernière série stockée

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
print("source:", data.get("source"))
print("points:", data.get("rows"))
```

---

## 9) Intégration avec le reste du projet

- `api-dataclean` fournit l'historique (CSV/JSON)
- `api-inference` calcule ou lit les prédictions
- `dashboard_app.py` consomme surtout :
  - `/models/list`
  - `/predictions/prm/{prm}/latest`

---

## 10) Docker

Construire l'image (depuis la racine projet ou selon votre contexte Docker) :

```bash
docker build -f api/api-inference/Dockerfile -t api-inference .
```

Lancer le conteneur :

```bash
docker run -p 8001:8001 --env-file api/api-inference/.env api-inference
```

Le `Dockerfile` expose le port `8001` et démarre `uvicorn` sur ce port.

---

## 11) Tests

Depuis `api/api-inference/` :

```bash
pytest tests/
```

Depuis la racine du projet, tu peux aussi exécuter la suite globale.

---

## 12) Dépannage rapide

### `401 Clé API invalide ou manquante`
- Vérifier l'en-tête `X-API-Key`
- Vérifier `INFERENCE_API_KEY` dans `.env`

### `502 Dataclean API indisponible`
- Vérifier que `api-dataclean` tourne
- Vérifier `DATACLEAN_BASE_URL`

### `404 Modèle Prophet introuvable`
- Vérifier la présence du fichier : `models/saved/prophet_model_<prm>_latest.pkl`
- Vérifier que le PRM contient 14 chiffres

### `503 Erreur Fabric`
- Vérifier les variables DB/Fabric
- Vérifier droits et connectivité réseau

---

## 13) Résumé

`api-inference` est la couche d'orchestration de l'inférence :

- elle relie données historiques, modèle et restitution API,
- elle sécurise les routes sensibles par clé API,
- elle fournit une base solide pour un usage dashboard/production.
