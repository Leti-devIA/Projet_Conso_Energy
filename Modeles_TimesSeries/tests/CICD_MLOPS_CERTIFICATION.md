# CI/CD et démarche MLOps — Documentation pour la certification Simplon IA (C13)

Ce document décrit précisément ce qui a été mis en place au niveau de la chaîne d'intégration continue, de livraison continue et de la démarche MLOps dans le projet de prévision de consommation énergétique.

---

## 1. Vue d'ensemble de la chaîne CI/CD

La chaîne CI/CD repose entièrement sur **GitHub Actions**. Cinq workflows YAML sont définis dans le dossier `.github/workflows/` :

| Fichier | Rôle |
|---|---|
| `ci.yml` | Intégration continue — lint + tests à chaque push |
| `cd-api-dataclean.yml` | Livraison continue — API de nettoyage de données |
| `cd-api-inference.yml` | Livraison continue — API de prédiction Prophet |
| `cd-dashboard.yml` | Livraison continue — Dashboard Streamlit |
| `sync_docs.yml` | Synchronisation automatique de la documentation |

---

## 2. Workflow CI — `ci.yml`

### Déclencheurs

Le workflow CI se déclenche automatiquement dans trois cas :
- Push sur les branches `main` ou `branch-ia`
- Pull Request vers `main`
- Déclenchement manuel via `workflow_dispatch`

### Environnement d'exécution

L'exécution se fait sur un runner Ubuntu (`ubuntu-latest`) avec Python 3.11. Le cache pip est activé via `cache-dependency-path: Modeles_TimesSeries/requirements.txt` pour accélérer les builds successifs. Le `working-directory` est fixé à `Modeles_TimesSeries/` pour tous les steps, ce qui correspond à la racine du module Python du projet.

### Étapes du pipeline CI

**1. Récupération du code**
`actions/checkout@v4` clone le dépôt dans le runner.

**2. Configuration Python**
`actions/setup-python@v5` installe Python 3.11 avec cache pip.

**3. Installation des dépendances**
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest pytest-cov ruff flake8
```
Les outils de qualité de code (`ruff`, `flake8`) et de tests (`pytest`, `pytest-cov`) sont installés en plus des dépendances du projet.

**4. Vérification de la qualité du code (lint)**
Deux outils sont utilisés en séquence :
- `flake8 src/` — vérifie les erreurs critiques (E9, F63, F7, F82) : erreurs de syntaxe, imports non définis, noms non définis
- `ruff check src/ tests/ --ignore E501` — vérification plus large avec tolérance sur la longueur des lignes (le `|| true` empêche l'échec du pipeline sur les warnings non bloquants)

**5. Lancement des tests**
```bash
pytest tests/ -v --cov=src --cov-report=term --maxfail=1 --disable-warnings
```
- `-v` : mode verbeux pour voir chaque test individuellement
- `--cov=src` : mesure de couverture sur le dossier `src/`
- `--maxfail=1` : le pipeline s'arrête dès le premier échec
- `--disable-warnings` : supprime les warnings non critiques dans les logs CI

**6. Rapport de couverture**
Le step `if: always()` affiche le rapport même si les tests ont échoué, pour permettre le diagnostic.

---

## 3. Workflow CD — `cd-api-dataclean.yml`

### Déclencheurs ciblés

Ce workflow se déclenche uniquement si les fichiers suivants sont modifiés sur `main` :
- `api/api-dataclean/**`
- `.github/workflows/cd-api-dataclean.yml`

Il peut aussi être déclenché manuellement. Ce ciblage évite des déploiements inutiles quand seul le code du dashboard ou de l'autre API change.

### Étapes

1. **Checkout** du code source
2. **Configuration Docker Buildx** — `docker/setup-buildx-action@v3` pour le build multi-plateforme
3. **Authentification Docker Hub** — via les secrets `DOCKER_USERNAME` et `DOCKER_PASSWORD` stockés dans GitHub Secrets (jamais dans le code)
4. **Build de l'image Docker** depuis `./api/api-dataclean/` avec deux tags :
   - `latest` — tag stable
   - `${{ github.sha }}` — tag versionné sur le hash du commit Git
5. **Push vers Docker Hub** des deux tags
6. **Déploiement** conditionnel (`if: github.ref == 'refs/heads/main'`) — uniquement sur la branche principale

L'API DataClean expose ses données sur le **port 8000** et est construite avec Python 3.10-slim.

---

## 4. Workflow CD — `cd-api-inference.yml`

### Déclencheurs ciblés

Ce workflow surveille :
- `api/api-inference/**`
- `src/**` — si le code métier (feature engineering, preprocessing) change, l'API de prédiction est redéployée
- `.github/workflows/cd-api-inference.yml`

### Spécificités du Dockerfile

L'image Docker de l'API Inference est construite depuis la racine `Modeles_TimesSeries/` car elle embarque deux modules distincts :
- `api/api-inference/app/` — le code de l'API FastAPI
- `src/` — les modules Python partagés (preprocessing, feature engineering, data_loader)

Des dépendances système sont installées pour supporter **pyodbc** (connexion SQL Server) et le **driver Microsoft SQL Server ODBC 18**.

### Double versionnement des images

Chaque image est taguée avec `latest` ET `${{ github.sha }}`, ce qui permet de toujours avoir une image identifiable par commit et de revenir en arrière si nécessaire.

---

## 5. Workflow CD — `cd-dashboard.yml`

### Déclencheurs ciblés

Le workflow surveille les fichiers `dashboard_*.py` et `requirements.txt`. Seule une modification des fichiers dashboard déclenche ce workflow, pas un changement dans les APIs.

### Étapes spécifiques

Un step de test est réalisé avant déploiement :
```bash
timeout 10 streamlit run dashboard_app.py --server.headless true || true
```
Cette commande vérifie que le dashboard se lance sans erreur d'import ni erreur Python, en mode headless (sans interface graphique), avec un timeout de 10 secondes.

Un build Docker conditionnel est prévu (`if: hashFiles('Dockerfile') != ''`) — il ne s'exécute que si un `Dockerfile` est présent dans le répertoire.

---

## 6. Workflow de synchronisation — `sync_docs.yml`

### Rôle

Ce workflow automatise la synchronisation de la documentation technique vers un dépôt Git séparé (`LaetitiaProLacroix/Lacroix-dev-docs`). Il se déclenche sur push vers `main` ou `branch-ia` si des fichiers `docs/` ou des fichiers `.md` sont modifiés.

### Fonctionnement

1. Checkout du dépôt projet
2. Checkout du dépôt de documentation partagée avec un token `PAT_DOC_REPO` (Personal Access Token stocké dans les secrets GitHub)
3. Copie des fichiers via `rsync --delete` vers `shared-docs/docs/projet-conso-energ/`
4. Commit automatique avec le message `docs: sync Projet Conso Energ (${{ github.sha }})` et push

Ce workflow garantit que la documentation reste **toujours synchronisée** avec le code, sans intervention manuelle.

---

## 7. Gestion des secrets et variables d'environnement

Aucune donnée sensible n'est présente dans le code source. Les informations confidentielles sont gérées à deux niveaux :

**GitHub Secrets** (pour les workflows CI/CD) :
- `DOCKER_USERNAME` / `DOCKER_PASSWORD` — authentification Docker Hub
- `PAT_DOC_REPO` — token d'accès au dépôt de documentation

**Variables d'environnement Docker** (pour le runtime) :
- `DB_SERVER`, `DB_DATABASE`, `DB_USER`, `DB_PASSWORD` — connexion SQL Server
- `NGROK_AUTHTOKEN` — exposition de l'API en local
- `MLFLOW_TRACKING_URI` — chemin vers le tracking MLflow

Ces variables sont injectées via `env_file` dans `docker-compose.yml` et lues depuis des fichiers `.env` locaux non versionnés.

---

## 8. Architecture Docker et docker-compose

### docker-compose.yml

Le fichier `docker-compose.yml` orchestre trois services principaux :

**`api-dataclean`** (port 8000) :
- Expose les données historiques nettoyées
- Healthcheck Python : vérifie que `/health` répond en moins de 5 secondes, avec 5 tentatives espacées de 30 secondes
- Redémarre automatiquement (`restart: unless-stopped`)

**`api-inference`** (port 8001) :
- Démarre uniquement quand `api-dataclean` est `healthy` (`depends_on` avec `condition: service_healthy`)
- Partage un réseau interne `conso-network` (les services communiquent par nom, pas par IP)
- Volumes montés en live : code API, modèles Prophet sauvegardés, runs MLflow, prédictions
- Healthcheck curl : vérifie `/health` toutes les 15 secondes

**`ngrok`** (profil `local` uniquement) :
- Expose l'API Inference sur internet via un tunnel
- S'active uniquement avec `docker compose --profile local up`, pas en production

**`ngrok-config-sync`** (one-shot) :
- Lit l'URL du tunnel ngrok via son API interne (`http://ngrok:4040/api/tunnels`)
- Génère automatiquement le fichier `config/fabric_runtime.env`
- S'exécute une seule fois et s'arrête (`restart: "no"`)

### docker-compose.ci.yml

Un fichier séparé est prévu pour les tests en CI. Il définit un service `app` qui exécute `scripts/run_ci_tests.sh` et un service `db` PostgreSQL pour les tests d'intégration nécessitant une base de données.

---

## 9. Démarche MLOps — Tracking avec MLflow

### Intégration MLflow dans l'API Inference

MLflow est intégré directement dans l'API d'inférence (`app/main.py`). L'URI de tracking est configurée via variable d'environnement :

```python
_mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", str(PROJECT_ROOT / "mlruns"))
```

Si l'URI ne pointe pas vers un serveur distant (HTTP/HTTPS), elle est automatiquement convertie en URI de fichier local (`file://...`). Cela permet de fonctionner en local (dossier `mlruns/`) comme en production (serveur MLflow distant).

### Métriques tracées

Le router `models.py` expose une fonction `get_mlflow_metrics(prm)` qui lit les métriques du dernier run MLflow associé à un PRM. Les métriques suivies sont :
- `val_mae` — Mean Absolute Error sur la validation
- `val_rmse` — Root Mean Square Error sur la validation
- `val_mape` — Mean Absolute Percentage Error sur la validation
- `val_r2` — coefficient de détermination R²

### Affichage dans le dashboard

Le dashboard Streamlit (`dashboard_app.py`) intègre une fonction `load_mlflow_metrics(prm)` qui lit directement le dossier `mlruns/` en parsant les fichiers de métriques MLflow. Ces métriques sont affichées dans l'interface pour chaque site (PRM), permettant de suivre la qualité du modèle sans outil externe.

### Versionnement des modèles

Les modèles Prophet entraînés sont sauvegardés dans `models/saved/` et montés dans le conteneur Docker via un volume. Chaque image Docker de l'API Inference est taguée avec le hash du commit Git (`${{ github.sha }}`), ce qui lie chaque image à un état précis du code et des modèles.

---

## 10. Configuration pytest — `pytest.ini`

Le fichier `pytest.ini` centralise la configuration de l'exécution des tests :

```ini
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -q --tb=short -ra
```

Les marqueurs personnalisés déclarés correspondent exactement à ceux utilisés dans le code :
- `slow` — tests lents, filtrables avec `-m "not slow"`
- `integration` — tests d'intégration
- `unit` — tests unitaires
- `requires_data` — tests nécessitant des fichiers de données réels

---

## 11. Script `run_tests.py` — Lanceur pédagogique

Un script Python `run_tests.py` a été développé pour faciliter l'exécution des tests pendant le développement et la soutenance. Il expose une interface en ligne de commande avec les options suivantes :

| Option | Comportement |
|---|---|
| `python run_tests.py` | Lance tous les tests |
| `python run_tests.py --coverage` | Génère un rapport de couverture HTML |
| `python run_tests.py --fast` | Tests en parallèle |
| `python run_tests.py --unit` | Uniquement les tests unitaires (`-m unit`) |
| `python run_tests.py --integration` | Uniquement les tests d'intégration (`-m integration`) |
| `python run_tests.py --specific test_utils.py` | Un fichier de test précis |

Ce script encapsule les appels `subprocess.run(pytest ...)` avec des messages clairs, ce qui le rend utilisable sans connaître la syntaxe pytest.

---

## 12. Résumé de la chaîne complète

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
  │ (si api-dataclean/   │   │ (si api-inference/    │   │ (si dashboard_*.py │
  │  modifié)            │   │  ou src/ modifié)     │   │  modifié)          │
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
