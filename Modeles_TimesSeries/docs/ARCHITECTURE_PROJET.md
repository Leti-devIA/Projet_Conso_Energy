# Architecture du projet

Cette page décrit l'architecture **réellement implémentée** dans `Modeles_TimesSeries`.

## 1) Vue d'ensemble

```text
┌──────────────────────────┐
│ Microsoft Fabric / SQL   │
└─────────────┬────────────┘
              │ (lecture)
              ▼
┌──────────────────────────┐
│ API Dataclean (FastAPI)  │  port 8000
│ api/api-dataclean        │
└─────────────┬────────────┘
              │ HTTP (JSON/CSV)
              ▼
┌──────────────────────────┐
│ API Inference (FastAPI)  │  port 8001
│ api/api-inference        │
└──────┬───────────┬───────┘
       │           │
       │           ├────────► models/saved/ (modèles Prophet, métriques)
       │           ├────────► data/raw/, data/processed/, data/predictions/
       │           └────────► mlruns/ (tracking MLflow)
       │
       ▼
┌──────────────────────────┐
│ Dashboard Streamlit      │  port 8501
│ dashboard_app.py         │
└──────────────────────────┘
```

## 2) Composants applicatifs

### `api/api-dataclean`

- Expose les données historiques, météo et prix spot via routes HTTP.
- Routeur principal : `app/routers/dataclean.py`.
- N'exécute pas d'entraînement ML.

### `api/api-inference`

- Orchestration des actions de sync et de prédiction.
- Routeurs :
  - `app/routers/sync.py`
  - `app/routers/predict.py`
  - `app/routers/models.py`
  - `app/routers/health.py`
- Utilise les modules `src/` pour preprocessing, features, entraînement et inférence.

### `src/` (cœur métier)

- `data_loader.py` : chargement des données (CSV, interface abstraite).
- `preprocessing.py` : nettoyage + agrégation.
- `feature_engineering.py` : création des variables explicatives.
- `train.py` : entraînement Prophet + sauvegarde artefacts.
- `predict.py` : construction du futur + génération des prévisions.
- `grid_search.py` : optimisation des hyperparamètres.
- `simulation_engine.py` : moteur de simulation achat/vente énergie.

### `dashboard_app.py`

- Consomme les APIs et affiche les vues métier.
- Intègre la simulation de coûts (section « Simulation achat énergie »).

## 3) Flux principal (PRM)

```text
1. POST /sync/prm/{prm}
   └─ récupère dataclean PRM et alimente data/raw/sites/

2. Entraînement (train.py)
   └─ data/raw -> data/processed -> modèle Prophet + métriques

3. POST /predict/prm/{prm}
   └─ construit les features futures + prédit yhat/yhat_lower/yhat_upper

4. Dashboard
   └─ lit modèles/prédictions/métriques et affiche KPIs + simulation prix
```

## 4) Architecture d'exécution Docker

Le fichier `docker-compose.yml` définit les services :

- `api-dataclean` (port 8000)
- `api-inference` (port 8001)
- `dashboard` (port 8501)
- `ngrok` + `ngrok-config-sync` (profil `local`)

Réseau partagé : `conso-network`.

## 5) CI/CD (vue architecture de livraison)

Workflows présents dans `.github/workflows/` :

- `ci.yml`
- `cd-api-dataclean.yml`
- `cd-api-inference.yml`
- `cd-dashboard.yml`
- `sync_docs.yml`

Ces workflows couvrent tests/lint, build/push d'images et synchronisation documentaire.
