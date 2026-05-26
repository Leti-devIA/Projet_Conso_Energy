# Projet Modèles Time Series

Projet de prévision de consommation énergétique multi-sites, basé sur des modèles de séries temporelles (Prophet), avec un pipeline complet :

- récupération des données pré-nettoyées depuis Microsoft Fabric,
- entraînement de modèles par PRM,
- génération et exposition des prédictions via API,
- visualisation dans un dashboard Streamlit.

---

## 1) Vision du projet

### Ce que fait le projet
- Prévoit la consommation d'énergie horaire pour un ou plusieurs sites (PRM).
- Utilise un historique Enedis + météo déjà pré-nettoyé en amont (via Fabric).
- Sert les résultats via deux APIs FastAPI (`api-dataclean` et `api-inference`).
- Alimente un dashboard pour l'analyse métier et le pilotage.

### Ce que le projet ne fait pas directement
- Le nettoyage primaire de données n'est pas fait ici : les données arrivent déjà préparées.
- L'API dataclean expose et exporte les données ; elle ne fait pas d'entraînement ML.

---

## 2) Architecture globale

```
Modeles_TimesSeries/
│
├── api/
│   ├── api-dataclean/      # Lecture des données pré-nettoyées depuis Fabric
│   └── api-inference/      # Sync, prédiction Prophet, endpoints dashboard
│
├── src/                    # Prétraitement, features, entraînement, prédiction
├── data/                   # raw / processed / predictions
├── models/saved/           # Modèles Prophet sérialisés (.pkl)
├── docs/                   # Documentation technique détaillée (MkDocs)
├── tests/                  # Tests unitaires + intégration
├── dashboard_app.py        # Dashboard Streamlit
├── main.py                 # CLI pédagogique (list, train, predict)
├── docker-compose.yml      # Orchestration locale (API + ngrok optionnel)
└── README.md
```

### Flux de données simplifié
1. `api-dataclean` lit Fabric et expose les historiques (`CSV` et `JSON`).
2. `api-inference` consomme `api-dataclean`, génère la météo future, puis calcule les prédictions Prophet.
3. Les prédictions sont stockées/lues côté Fabric pour le dashboard.
4. `dashboard_app.py` consomme l'API d'inférence pour afficher résultats et métriques.

---

## 3) Prérequis

- Python 3.11 recommandé
- `pip`
- Docker + Docker Compose (optionnel, mais conseillé pour l'exécution complète)
- Accès Microsoft Fabric (warehouse / tables)
- Driver ODBC SQL Server (`ODBC Driver 17 for SQL Server`) si connexion locale DB/Fabric

---

## 4) Installation locale (mode développeur)

```bash
git clone <url-du-repo>
cd Modeles_TimesSeries
python -m venv .venv
```

### Activation de l'environnement

- Windows PowerShell :
```powershell
.\.venv\Scripts\Activate.ps1
```

- macOS/Linux :
```bash
source .venv/bin/activate
```

### Installation des dépendances

```bash
pip install -r requirements.txt
```

---

## 5) Configuration

Le projet s'appuie sur plusieurs fichiers de configuration :

- `config/config.yaml` : paramètres de pipeline (horizon, chemins data, etc.)
- `api/api-dataclean/.env` : accès DB/Fabric de l'API dataclean
- `api/api-inference/.env` : accès API dataclean, sécurité API key, options MLflow/Fabric

### Variables importantes (API dataclean)
- `DB_SERVER`
- `DB_DATABASE`
- `DB_USER`
- `DB_PASSWORD`

### Variables importantes (API inference)
- `DATACLEAN_BASE_URL` (ex: `http://127.0.0.1:8000` en local)
- `INFERENCE_API_KEY` (clé requise pour certains endpoints)
- `CORS_ORIGINS`
- `MLFLOW_TRACKING_URI`
- Variables d'automatisation Fabric (optionnelles selon votre workflow)

---

## 6) Démarrage rapide (sans Docker)

### Étape 1 — Démarrer l'API dataclean (port 8000)
```bash
cd api/api-dataclean
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Étape 2 — Démarrer l'API inference (port 8001)
```bash
cd ../../api/api-inference
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

### Étape 3 — Démarrer le dashboard
```bash
cd ../..
streamlit run dashboard_app.py
```

---

## 7) APIs : endpoints principaux

## API dataclean (`http://localhost:8000`)

- `GET /health` : statut de l'API
- `GET /dataclean/allbyprm?prm=<14_chiffres>` : historique en CSV
- `GET /dataclean/allbyprm-json?prm=<14_chiffres>` : historique en JSON
- `GET /dataclean/previsions-meteo` : export CSV météo
- `GET /dataclean/sites` : export CSV table des sites
- `GET /dataclean/prixspot` : export CSV prix spot

## API inference (`http://localhost:8001`)

- `GET /health` : statut de l'API
- `POST /sync/prm/{prm}` : synchronise un CSV local depuis dataclean (protégé par clé API)
- `POST /predict/prm/{prm}` : lance une prédiction Prophet (protégé par clé API)
- `GET /predictions/prm/{prm}/latest` : lit la dernière prédiction depuis Fabric (protégé par clé API)
- `GET /models/list` : liste les modèles Prophet disponibles localement

### Exemple d'appel protégé

```bash
curl -X POST "http://localhost:8001/predict/prm/30000250086126" \
  -H "X-API-Key: dev-inference-key"
```

---

## 8) Utilisation via CLI (`main.py`)

Le script `main.py` est une entrée pédagogique pour les étudiants.

### Lister les sites disponibles
```bash
python main.py list-sites
```

### Entraîner un site
```bash
python main.py train --prm 30000250086126
```

### Entraîner tous les sites
```bash
python main.py train --all-sites
```

### Prédire pour un site
```bash
python main.py predict --prm 30000250086126
```

### Prédire pour tous les sites
```bash
python main.py predict --all-sites
```

### Prédire à partir d'un fichier météo futur
```bash
python main.py predict --prm 30000250086126 --meteo data/raw/meteo/fichier.csv
```

---

## 9) Arborescence des données

- `data/raw/sites/` : historiques par PRM (`dataclean_prm_<prm>.csv`)
- `data/raw/meteo/` : météo brute / entrante
- `data/processed/` : données enrichies/feature engineering
- `data/predictions/` : sorties de prédiction pour exploitation

Convention clé : le `PRM` doit être une chaîne de 14 chiffres.

---

## 10) Tests

Depuis la racine du projet :

```bash
pytest tests/
```

Tests présents :
- data loader,
- feature engineering,
- preprocessing,
- utilitaires,
- intégration API bridge.

---

## 11) Exécution avec Docker Compose

Depuis la racine du projet :

```bash
docker compose up --build
```

Par défaut :
- `api-dataclean` exposée sur `8000`
- `api-inference` exposée sur `8001`
- `dashboard` Streamlit exposé sur `8501` (`http://localhost:8501`)
- l'authentification du dashboard réutilise la base locale `users.db` montée dans le conteneur

Persistance des nouveaux entraînements en mode Docker :
- les modèles générés par `api-inference` sont persistés dans le volume Docker nommé `trained-models` (monté sur `/app/models/saved`).
- vérifier les volumes : `docker volume ls`

Lancer uniquement la stack nécessaire au dashboard (APIs + dashboard) :

```bash
docker compose up --build api-dataclean api-inference dashboard
```

Profil local optionnel (ngrok + sync config) :

```bash
docker compose --profile local up --build
```

---

## 12) Dépannage rapide

### Erreur `401 Clé API invalide ou manquante`
- Vérifier l'en-tête `X-API-Key`
- Vérifier `INFERENCE_API_KEY` dans `api/api-inference/.env`

### Erreur `503 Base de données non disponible`
- Vérifier les variables DB dans `api/api-dataclean/.env`
- Vérifier l'accès réseau/ODBC vers Fabric/SQL

### Erreur `404 Modèle introuvable`
- En local (hors Docker), vérifier la présence des fichiers `.pkl` dans `models/saved/`
- En Docker, vérifier le volume `trained-models` (modèles dans `/app/models/saved` du conteneur)
- Vérifier le format de nom : `prophet_model_<prm>_latest.pkl`

### Erreur `Identifiants invalides` sur le dashboard Docker
- Vérifier la présence du fichier `users.db` à la racine de `Modeles_TimesSeries`
- Vérifier que le service `dashboard` monte bien `./users.db:/app/users.db`
- Si besoin, redémarrer le service : `docker compose up -d --build dashboard`

---

## 13) Documentation complémentaire

Consulter `docs/` :

- `DATA_ARCHITECTURE.md`
- `MLFLOW_GUIDE.md`
- `LOGGING_AND_API_INTEGRATION.md`
- `WORKFLOW_MULTI_SITES.md`
- `TESTING.md`

---

## 14) Documentation MkDocs

Depuis la racine du projet :

```bash
mkdocs serve
```

Puis ouvrir :

```text
http://127.0.0.1:8000
```

Générer le site statique :

```bash
mkdocs build
```

Le résultat est généré dans le dossier `site/`.

---

## 15) Bonnes pratiques pour étudiants

- Commencer par un seul PRM pour valider le pipeline de bout en bout.
- Versionner vos expériences (métriques, paramètres, modèle).
- Isoler les tests data, tests modèle et tests API.
- Ne pas mélanger données brutes et données transformées dans les mêmes dossiers.

---

## 16) Contribution

Les contributions sont bienvenues :

1. créer une branche,
2. faire un commit clair,
3. ouvrir une pull request avec une description concise du changement.

---

Projet pédagogique Data Science / IA — prévision de consommation énergétique multi-sites.