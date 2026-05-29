# CI/CD et MLOps — Documentation Complète

## 1. Vue d'ensemble

Le projet repose sur une chaîne **CI/CD (Intégration Continue / Déploiement Continu)** entièrement automatisée via **GitHub Actions**, couplée à une démarche **MLOps** pour le suivi des modèles.

### Qu'est-ce que le CI/CD ?

- **CI (Continuous Integration)** : automatise les vérifications à chaque commit (tests, linting)
- **CD (Continuous Deployment)** : automatise la construction et la mise à disposition des artefacts (images Docker)

> Le CI/CD est votre filet de sécurité : si vous cassez quelque chose, GitHub vous le dit avant que ça n'arrive en production.

---

## 2. Architecture générale — 5 workflows GitHub Actions

Cinq workflows YAML définis dans `.github/workflows/` orchestrent la chaîne complète :

| Fichier | Déclencheur | Rôle |
|---|---|---|
| `ci.yml` | Chaque push ou PR vers `main` / `branch-ia` | Intégration continue — linting + tests |
| `cd-api-dataclean.yml` | Push/modification de `api/api-dataclean/**` sur `main` | Build + push image Docker (port 8000) |
| `cd-api-inference.yml` | Push/modification de `api/api-inference/**` ou `src/**` sur `main` | Build + push image Docker (port 8001) |
| `cd-dashboard.yml` | Modification des fichiers `dashboard_*.py` sur `main` | Test streamlit + build Docker |
| `sync_docs.yml` | Modification de `docs/` ou `.md` sur `main` / `branch-ia` | Synchronisation automatique vers dépôt doc partagé |

### Flux complet

```
Push Git (main / branch-ia)
        │
        ▼
  ┌─────────────┐
  │   ci.yml    │  → lint (flake8 + ruff) → tests pytest → rapport couverture
  └─────────────┘
        │ (si tests OK)
        ▼
  ┌──────────────────────┐   ┌───────────────────────┐   ┌────────────────────┐
  │ cd-api-dataclean.yml │   │ cd-api-inference.yml  │   │ cd-dashboard.yml   │
  │ (si api-dataclean/   │   │ (si api-inference/ ou │   │ (si dashboard_*.py │
  │  modifié)            │   │  src/ modifié)        │   │  modifié)          │
  └──────────┬───────────┘   └──────────┬────────────┘   └────────┬───────────┘
             │                          │                          │
             ▼                          ▼                          ▼
       Docker build              Docker build               Test streamlit
       + push Hub                + push Hub                 + build Docker
       (latest + SHA)            (latest + SHA)
        │
        ▼
  ┌──────────────┐
  │ sync_docs.yml│  → rsync docs → commit auto → push repo docs
  └──────────────┘
```

---

## 3. Workflow CI — `ci.yml`

### Déclencheurs

Le workflow CI démarre automatiquement dans trois cas :
- Push sur `main` ou `branch-ia`
- Pull Request vers `main`
- Déclenchement manuel (`workflow_dispatch`)

### Environnement d'exécution

- Runner : `ubuntu-latest` (Ubuntu dernière version)
- Python : 3.11
- Working directory : `Modeles_TimesSeries/` (racine du module Python)
- Cache pip : activé via `cache-dependency-path: Modeles_TimesSeries/requirements.txt`

### Étapes détaillées

#### 1. Récupération et configuration
```bash
actions/checkout@v4              # Clone le dépôt
actions/setup-python@v5          # Installe Python 3.11
```

#### 2. Installation des dépendances
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov ruff flake8
```

#### 3. Vérification de la qualité du code (lint)

Deux outils en séquence :

**flake8** — détecte les erreurs critiques
```bash
flake8 src/  # Erreurs E9, F63, F7, F82 (syntaxe, imports non définis, noms non définis)
```

**ruff** — vérification plus large
```bash
ruff check src/ tests/ --ignore E501 || true  # Tolère les warnings non bloquants
```

#### 4. Lancement des tests
```bash
pytest tests/ -v --cov=src --cov-report=term --maxfail=1 --disable-warnings
```

| Flag | Utilisé pour |
|---|---|
| `-v` | Mode verbeux — voir chaque test individuellement |
| `--cov=src` | Mesurer la couverture sur le dossier `src/` |
| `--cov-report=term` | Afficher le rapport dans les logs |
| `--maxfail=1` | Arrêter au premier échec |
| `--disable-warnings` | Supprimer les warnings non critiques |

#### 5. Rapport de couverture
Affiché même si les tests échouent (step `if: always()`), pour permettre le diagnostic.

---

## 4. Workflows CD — Intégration continue

### `cd-api-dataclean.yml`

**Déclencheurs ciblés :**
- Modification de `api/api-dataclean/**`
- Modification du fichier `.github/workflows/cd-api-dataclean.yml`
- Uniquement sur la branche `main`

**Étapes :**
1. Checkout du code
2. Configuration Docker Buildx (`docker/setup-buildx-action@v3`)
3. Authentification Docker Hub via secrets
4. Build de l'image depuis `./api/api-dataclean/` avec deux tags :
   - `latest` — tag stable
   - `${{ github.sha }}` — tag versionné (hash du commit)
5. Push vers Docker Hub
6. Déploiement (uniquement si `main`)

**Spécificités :** API DataClean sur port **8000**, image Python 3.10-slim.

---

### `cd-api-inference.yml`

**Déclencheurs ciblés :**
- Modification de `api/api-inference/**`
- Modification de `src/**` (code métier partagé)
- Modification du fichier `.github/workflows/cd-api-inference.yml`
- Uniquement sur la branche `main`

**Particularité du Dockerfile :**
- Build depuis la racine `Modeles_TimesSeries/` car l'image embarque deux modules :
  - `api/api-inference/app/` — code FastAPI
  - `src/` — modules partagés (preprocessing, feature engineering, data_loader)
- Dépendances système pour **pyodbc** et **driver Microsoft SQL Server ODBC 18** (connexion SQL Server)

**Double versionnement :** chaque image taguée avec `latest` ET `${{ github.sha }}`, permettant de revenir en arrière si nécessaire.

---

### `cd-dashboard.yml`

**Déclencheurs ciblés :**
- Modification de `dashboard_*.py`
- Modification de `requirements.txt`

**Étape de test avant déploiement :**
```bash
timeout 10 streamlit run dashboard_app.py --server.headless true || true
```
Vérifie que le dashboard se lance sans erreur, en mode headless, avec timeout 10s.

**Build Docker :** conditionnel — s'exécute uniquement si `Dockerfile` existe.

---

### `sync_docs.yml` — Synchronisation automatique

**Déclencheurs :**
- Modification de `docs/` ou fichiers `.md`
- Sur `main` ou `branch-ia`

**Fonctionnement:**
1. Checkout du dépôt projet
2. Checkout du dépôt de documentation (token `PAT_DOC_REPO`)
3. Copie via `rsync --delete` vers `shared-docs/docs/projet-conso-energ/`
4. Commit automatique et push

**Résultat :** documentation toujours synchronisée, sans intervention manuelle.

---

## 5. Configuration initiale (à faire une seule fois)

### Configurer les secrets GitHub

Aller dans le dépôt GitHub → **Settings** → **Secrets and variables** → **Actions**.

Ajouter obligatoirement :

| Secret | Valeur | Utilisé pour |
|---|---|---|
| `DOCKER_USERNAME` | Votre nom d'utilisateur Docker Hub | Authentification Docker |
| `DOCKER_PASSWORD` | Votre mot de passe Docker Hub | Authentification Docker |
| `PAT_DOC_REPO` | Personal Access Token GitHub | Sync automatique docs |

⚠️ **Important :** les secrets ne sont jamais visibles en clair dans les logs.

### Créer un compte Docker Hub (si nécessaire)

[https://hub.docker.com](https://hub.docker.com) — gratuit pour les images publiques.

---

## 6. Docker Compose — Orchestration locale

### `docker-compose.yml` — Production locale

Orchestre trois services principaux :

#### `api-dataclean` (port 8000)
```yaml
services:
  api-dataclean:
    image: ${DOCKER_USERNAME}/conso-api-dataclean:latest
    ports:
      - "8000:8000"
    healthcheck:
      test: python -c "import requests; requests.get('http://localhost:8000/health', timeout=5)"
      interval: 30s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    env_file: config/fabric_runtime.env
```
- Expose les données historiques nettoyées
- Healthcheck Python : vérifie `/health` en moins de 5s
- Redémarre automatiquement

#### `api-inference` (port 8001)
```yaml
  api-inference:
    image: ${DOCKER_USERNAME}/conso-api-inference:latest
    ports:
      - "8001:8001"
    depends_on:
      api-dataclean:
        condition: service_healthy
    networks:
      - conso-network
    volumes:
      - ./api/api-inference:/app
      - ./models/saved:/app/models
      - ./mlruns:/app/mlruns
      - ./exports:/app/exports
    healthcheck:
      test: curl -f http://localhost:8001/health || exit 1
      interval: 15s
      timeout: 5s
      retries: 3
    restart: unless-stopped
```
- Démarre uniquement quand `api-dataclean` est `healthy`
- Communique via réseau interne `conso-network`
- Volumes montés en direct : code API, modèles, runs MLflow, résultats
- Healthcheck curl

#### `ngrok` (profil `local` uniquement)
```bash
docker compose --profile local up
```
- Expose l'API Inference sur internet via tunnel
- Profil `local` uniquement (pas en prod)

#### `ngrok-config-sync` (one-shot)
- Lit l'URL du tunnel ngrok via son API (`http://ngrok:4040/api/tunnels`)
- Génère automatiquement `config/fabric_runtime.env`
- S'exécute une seule fois (`restart: "no"`)

### `docker-compose.ci.yml` — Tests en CI

Utilisé **uniquement pendant les tests** CI. Démarre les services sans données réelles ni connexions Fabric, permettant aux tests de tourner dans un environnement contrôlé.

```bash
docker compose -f docker-compose.ci.yml up --abort-on-container-exit
```

---

## 7. Gestion des secrets et variables d'environnement

### Aucune donnée sensible dans le code source

Les informations confidentielles sont gérées à deux niveaux :

**GitHub Secrets** (pour les workflows CI/CD) :
- `DOCKER_USERNAME` / `DOCKER_PASSWORD` — authentification Docker Hub
- `PAT_DOC_REPO` — token d'accès au dépôt de documentation

**Variables d'environnement Docker** (pour le runtime) :
- `DB_SERVER`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD` — connexion SQL Server
- `NGROK_AUTHTOKEN` — exposition de l'API en local
- `MLFLOW_TRACKING_URI` — chemin vers le tracking MLflow

Ces variables sont injectées via `env_file` dans `docker-compose.yml` et lues depuis des fichiers `.env` locaux non versionnés.

---

## 8. Tests et qualité de code

### Configuration pytest — `pytest.ini`

```ini
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -q --tb=short -ra
```

**Marqueurs personnalisés :**
- `slow` — tests lents, filtrables avec `-m "not slow"`
- `integration` — tests d'intégration
- `unit` — tests unitaires
- `requires_data` — tests nécessitant des fichiers de données réels

### Script `run_tests.py` — Lanceur des tests

Interface CLI pour faciliter l'exécution des tests :

```bash
python run_tests.py                    # Tous les tests
python run_tests.py --coverage         # Avec rapport HTML
python run_tests.py --fast             # Tests en parallèle
python run_tests.py --unit             # Uniquement unitaires
python run_tests.py --integration      # Uniquement intégration
python run_tests.py --specific test_utils.py
```

### Script `run_ci_tests.sh` — Tester en local avant de pusher

```bash
bash scripts/run_ci_tests.sh
```

Exécute localement les mêmes vérifications que le workflow GitHub Actions (tests + linting). Si ce script passe ✅, le pipeline passera aussi.

---

## 9. Scripts utilitaires

| Script | Rôle |
|---|---|
| `scripts/run_ci_tests.sh` | Teste localement (tests + linting) comme dans GitHub Actions |
| `scripts/build_and_push.sh` | Build et push les images Docker manuellement |
| `scripts/deploy.sh` | Déploie le projet en local (docker compose up) |

---

## 10. Flux de développement recommandé

```
1. Développer sur une branche feature/fix
       │
       ▼
2. Tester localement : bash scripts/run_ci_tests.sh
       │
       ▼
3. git push origin ma-branche
  → GitHub Actions CI démarre automatiquement
       │
       ▼
4. Si tests passent ✅ → ouvrir Pull Request
  Si tests échouent ❌ → corriger et re-pusher
       │
       ▼
5. Merge sur main
  → Workflows CD déclenchés (selon fichiers modifiés)
  → Images Docker buildées et pushées sur Docker Hub
       │
       ▼
6. Déploiement serveur : docker pull + docker compose up
```

---

## 11. MLOps — Tracking avec MLflow

### Intégration MLflow dans l'API Inference

MLflow est intégré directement dans l'API d'inférence (`app/main.py`). Configuration :

```python
_mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", str(PROJECT_ROOT / "mlruns"))
```

Si l'URI ne pointe pas vers un serveur distant (HTTP/HTTPS), elle est convertie en URI de fichier local (`file://...`). Permet de fonctionner en local (dossier `mlruns/`) comme en production (serveur MLflow distant).

### Métriques tracées

Le router `models.py` expose `get_mlflow_metrics(prm)` qui lit les métriques du dernier run :
- `val_mae` — Mean Absolute Error (validation)
- `val_rmse` — Root Mean Square Error (validation)
- `val_mape` — Mean Absolute Percentage Error (validation)
- `val_r2` — Coefficient de détermination R²

### Affichage dans le dashboard

Le dashboard Streamlit (`dashboard_app.py`) intègre `load_mlflow_metrics(prm)` qui lit le dossier `mlruns/` en parsant les fichiers de métriques. Permet de suivre la qualité du modèle pour chaque site (PRM) sans outil externe.

### Versionnement des modèles

- Modèles Prophet entraînés sauvegardés dans `models/saved/`
- Montés dans Docker via volume
- Chaque image Docker taguée avec `${{ github.sha }}` (hash du commit) — lie l'image à un état précis du code et des modèles

---

## 12. Dépannage

| Problème | Solution |
|---|---|
| Tests échouent sur GitHub mais passent en local | Vérifier les versions de dépendances (`pip freeze`) |
| Build Docker échoue | Vérifier `DOCKER_USERNAME` et `DOCKER_PASSWORD` dans les secrets GitHub |
| Workflow ne se déclenche pas | Vérifier le `on:` du fichier YAML (branche correcte ? filtres de fichiers ?) |
| Coverage trop basse | Écrire des tests pour les modules non couverts |
| API ne démarre pas | Vérifier les logs : `docker logs nom-du-service` |
| Healthcheck échoue | Vérifier que le port HTTP est exposé et l'endpoint `/health` existe |

---

## 13. Résumé des points clés

✅ **Automatisation complète** — chaque push déclenche vérifications et déploiement
✅ **Déploiement sans intervention manuelle** — images Docker buildées et pushées automatiquement
✅ **Suivi de la qualité** — couverture de code, métriques MLflow intégrées
✅ **Versionnement des artefacts** — images taguées par commit Git et `latest`
✅ **Gestion des secrets centralisée** — aucune donnée sensible dans le code
✅ **Documentation synchronisée** — mise à jour automatique vers dépôt partagé
✅ **Facilité de diagnostic** — logs clairs, healthchecks, rapports de test
