# Projet Prévision Énergétique — Documentation Technique

Bienvenue sur la documentation complète du projet **Modèles Time Series**.

Ce projet prédit la **consommation d'énergie horaire** pour plusieurs sites industriels identifiés par leur PRM Enedis. Il s'appuie sur le modèle de séries temporelles **Prophet** de Meta, expose les résultats via deux APIs FastAPI, un dashboard Streamlit, et s'intègre à Microsoft Fabric.

> Ce document s'adresse à toute personne reprenant le projet : développeur, data scientist ou data engineer. Il suppose une connaissance basique de Python et de Git.

---

## Vue d'ensemble du système

```
Microsoft Fabric (données pré-nettoyées)
         │
         ▼
┌─────────────────────┐
│   API Dataclean     │  ← Expose historiques Enedis + météo + prix spot
│   (port 8000)       │
└─────────┬───────────┘
          │  HTTP
          ▼
┌─────────────────────┐
│   API Inference     │  ← Synchronise, entraîne Prophet, génère prédictions
│   (port 8001)       │
└─────────┬───────────┘
          │  HTTP
          ▼
┌─────────────────────┐
│  Dashboard Streamlit│  ← Visualisation métier (courbes, métriques, coûts)
└─────────────────────┘
```

Le projet est également exposable via **ngrok** pour permettre à Microsoft Fabric d'appeler l'API d'inférence depuis le cloud sans déploiement réseau complexe.

---

## Structure du dépôt

```
Modeles_TimesSeries/
│
├── api/
│   ├── api-dataclean/      # API FastAPI — accès aux données Fabric
│   └── api-inference/      # API FastAPI — pipeline ML complet
│
├── src/                    # Modules Python : preprocessing, features, train, predict
├── data/
│   ├── raw/                # Données brutes (historiques par PRM, météo)
│   ├── processed/          # Données enrichies (feature engineering)
│   └── predictions/        # Sorties de prédiction
│
├── models/saved/           # Modèles Prophet sérialisés (.pkl)
├── tests/                  # Tests unitaires et d'intégration
│
├── docs/                   # Cette documentation (MkDocs)
├── config/
│   ├── config.yaml         # Paramètres pipeline (horizon, features, MLflow…)
│   ├── fabric_runtime.json # URL ngrok active (générée automatiquement)
│   └── fabric_runtime.env
│
├── dashboard_app.py        # Dashboard Streamlit
├── main.py                 # CLI pédagogique (list, train, predict)
├── docker-compose.yml      # Orchestration complète (APIs + ngrok)
├── docker-compose.ci.yml   # Orchestration CI (tests uniquement)
├── mkdocs.yml              # Configuration documentation
└── requirements.txt
```

---

## Flux de données

1. **Ingestion** — `api-dataclean` lit les tables pré-nettoyées depuis Microsoft Fabric (via ODBC) et les expose en CSV/JSON par PRM.
2. **Synchronisation** — `api-inference` appelle `api-dataclean` pour récupérer localement l'historique d'un PRM dans `data/raw/sites/`.
3. **Feature engineering** — les données brutes sont enrichies (lags, rolling means, encodage cyclique heure/jour, météo, jours fériés).
4. **Entraînement** — un modèle Prophet est ajusté pour chaque PRM et sauvegardé sous `models/saved/prophet_{prm}.pkl`.
5. **Prédiction** — le modèle chargé génère un horizon de prédiction à partir des données météo futures.
6. **Exposition** — les prédictions sont stockées dans Fabric et exposées via endpoints REST.
7. **Visualisation** — le dashboard Streamlit lit les prédictions et affiche métriques, courbes et estimation des coûts.

---

## Prérequis

| Composant | Version recommandée | Obligatoire |
|---|---|---|
| Python | 3.11 | Oui |
| Docker Desktop | Dernière version stable | Conseillé |
| ODBC Driver SQL Server | 17 | Oui (si connexion Fabric locale) |
| Accès Microsoft Fabric | — | Oui (en production) |
| ngrok | Dernière version | Non (si pas d'accès Fabric cloud) |

---

## Installation locale

```bash
git clone <url-du-repo>
cd Modeles_TimesSeries

# Créer et activer l'environnement virtuel
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

---

## Démarrage sans Docker

### 1. Variables d'environnement

```bash
# api/api-dataclean/.env
DB_SERVER=<serveur_fabric>
DB_DATABASE=<base_fabric>
DB_USER=<utilisateur>
DB_PASSWORD=<motdepasse>
```

```bash
# api/api-inference/.env
DATACLEAN_BASE_URL=http://127.0.0.1:8000
INFERENCE_API_KEY=dev-inference-key
CORS_ORIGINS=*
MLFLOW_TRACKING_URI=./mlruns
```

### 2. Lancer les APIs

```bash
# Terminal 1 — API Dataclean
cd api/api-dataclean
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 — API Inference
cd api/api-inference
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### 3. Lancer le dashboard

```bash
streamlit run dashboard_app.py
```

---

## Démarrage via Docker (recommandé)

```bash
docker compose up -d
docker compose ps
```

Pour inclure ngrok (tunnel public vers l'API inference) :

```bash
docker compose --profile local up -d
```

---

## CLI pédagogique (`main.py`)

```bash
# Lister les sites disponibles
python main.py list-sites

# Entraîner un PRM spécifique
python main.py train --prm 30000250086126

# Entraîner tous les sites
python main.py train --all-sites

# Prédire (nécessite un fichier météo futur)
python main.py predict --prm 30000250086126 --meteo data/raw/meteo/fichier.csv
```

---

## Résumé des endpoints

### API Dataclean (`http://localhost:8000`)

| Méthode | Route | Description |
|---|---|---|
| GET | `/health` | Statut de l'API |
| GET | `/dataclean/allbyprm?prm=<PRM>` | Historique CSV par PRM |
| GET | `/dataclean/allbyprm-json?prm=<PRM>` | Historique JSON par PRM |
| GET | `/dataclean/previsions-meteo` | Export CSV météo future |
| GET | `/dataclean/sites` | Export CSV table des sites |
| GET | `/dataclean/prixspot` | Export CSV prix spot |

### API Inference (`http://localhost:8001`)

| Méthode | Route | Auth | Description |
|---|---|---|---|
| GET | `/health` | Non | Statut de l'API |
| GET | `/models/list` | Non | Liste des modèles disponibles |
| POST | `/sync/prm/{prm}` | Oui | Synchronise l'historique d'un PRM |
| POST | `/predict/prm/{prm}` | Oui | Lance une prédiction Prophet |
| GET | `/predictions/prm/{prm}/latest` | Oui | Dernière prédiction depuis Fabric |

Les endpoints protégés requièrent l'en-tête HTTP `X-API-Key`.

---

## Dépannage rapide

| Erreur | Cause probable | Solution |
|---|---|---|
| `401 Clé API invalide` | En-tête manquant | Ajouter `X-API-Key` dans la requête |
| `503 Base de données non disponible` | Variables DB manquantes | Vérifier `.env` API Dataclean |
| `404 Modèle introuvable` | Fichier `.pkl` absent | Lancer `train --prm <PRM>` |
| `502 Dataclean indisponible` | API Dataclean éteinte | Vérifier `DATACLEAN_BASE_URL` |

---

## Navigation dans la documentation

| Section | Description |
|---|---|
| [API Dataclean](API Dataclean.md) | Architecture, endpoints, configuration |
| [API Inference](API Inference.md) | Pipeline ML, sécurité, endpoints |
| [Docker & Ngrok](DOCKER_NGROK.md) | Orchestration, tunnels, Docker Compose |
| [Pipeline d'entraînement](PIPELINE_ENTRAINEMENT.md) | Preprocessing, features, train, predict |
| [Modèle Prophet](AMELIORATIONS_PROPHET.md) | Fonctionnement, hyperparamètres, améliorations |
| [Grid Search](GRID_SEARCH_GUIDE.md) | Optimisation automatique des hyperparamètres |
| [MLflow](MLFLOW_GUIDE.md) | Tracking d'expériences, registre de modèles |
| [Dashboard](DASHBOARD_GUIDE.md) | Visualisation, métriques, coûts |
| [Tests](TESTING.md) | Tests unitaires, couverture, CI |
| [CI/CD](GUIDE_CICD.md) | GitHub Actions, déploiement automatique |
| [Formule coût horaire](FORMULE_COUT_HORAIRE.md) | Calcul financier détaillé |
| [MkDocs](MKDOCS_GUIDE.md) | Générer et déployer cette documentation |
