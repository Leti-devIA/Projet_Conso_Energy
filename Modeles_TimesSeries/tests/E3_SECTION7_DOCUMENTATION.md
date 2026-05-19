# E3 — Section 7 : Documentation technique et accessibilité

## Ce qui a été réellement produit dans le projet

---

## 1. Une documentation structurée avec MkDocs

Dès le début du projet, j'ai pris la décision de ne pas limiter la documentation à un simple `README.md` à la racine. J'ai mis en place une documentation navigable avec **MkDocs**, un générateur de site statique pensé pour les projets techniques.

Le fichier `mkdocs.yml` définit la navigation complète du site :

```
Accueil
APIs
  ├── API Dataclean
  └── API Inference
Infrastructure
  ├── Docker & Ngrok
  └── CI/CD
Machine Learning
  ├── Pipeline d'entraînement
  ├── Modèle Prophet
  ├── Grid Search
  └── MLflow
Application
  ├── Dashboard
  └── Formule coût horaire
Tests
MkDocs
```

Le site peut être lancé localement en une commande (`mkdocs serve`), ce qui rend la documentation aussi simple à consulter qu'un site web. Cette approche facilite la prise en main du projet pour n'importe quel développeur ou jury qui reprend le travail.

---

## 2. Les fichiers de documentation produits

Voici ce qui a été réellement écrit dans le dossier `docs/` :

### `index.md` — Point d'entrée global

Ce fichier est la porte d'entrée de toute la documentation. Il décrit sans ambiguïté :
- ce que fait le projet (prévision de consommation énergétique horaire multi-sites),
- les technologies utilisées (Prophet, FastAPI, Streamlit, Microsoft Fabric),
- le schéma d'architecture ASCII qui montre le flux de données entre les composants,
- la structure complète du dépôt Git avec le rôle de chaque dossier,
- les prérequis systèmes et les commandes de démarrage rapide.

Ce document s'adresse explicitement à toute personne reprenant le projet : « Ce document s'adresse à toute personne reprenant le projet : développeur, data scientist ou data engineer. »

### `QUICK_START.md` — Démarrage en 4 commandes

Ce fichier répond à une question précise : comment lancer le projet de zéro, sans lire l'intégralité de la documentation ? Il liste quatre étapes séquentielles : installer les dépendances, lancer l'API DataClean, lancer l'API d'inférence, lancer le dashboard.

### `API Dataclean.md` — Documentation de la première API

Ce document couvre en détail l'architecture interne de l'API DataClean, ses endpoints, ses prérequis, la configuration des variables d'environnement (fichier `.env`), les commandes d'installation et de lancement local, et les comportements attendus en cas de connexion absente à Microsoft Fabric (réponse `503`). Il inclut un schéma de l'architecture dossier/fichiers de l'API.

### `API Inference.md` — Documentation de la seconde API

Même niveau de détail pour l'API d'inférence (Prophet), qui gère la synchronisation des données, l'entraînement du modèle et la génération des prédictions.

### `GUIDE_CICD.md` — Guide de la chaîne CI/CD

Ce guide explique ce qu'est le CI/CD pour un développeur qui reprendrait le projet, détaille les quatre workflows GitHub Actions actifs, et donne les instructions pour configurer les secrets Docker Hub dans le dépôt. Il explique aussi comment tester le CI en local avant de pousser du code.

### `TESTING.md` — Guide des tests

Ce document présente la philosophie de test du projet (deux niveaux : unitaire et intégration), la structure du dossier `tests/`, les fixtures disponibles dans `conftest.py`, et toutes les commandes pour lancer les tests (via le script `run_tests.py` ou directement avec `pytest`). Il inclut aussi les commandes pour générer un rapport de couverture HTML.

### `MLFLOW_GUIDE.md` — Suivi des expériences MLflow

Ce guide explique le rôle de MLflow dans le projet (tracking des entraînements, comparaison de runs, registre de modèles), ce qui est enregistré automatiquement à chaque run (paramètres, métriques, artefacts, tags Git), et comment consulter l'interface web.

### `DATA_ARCHITECTURE.md` — Architecture de données

Ce document explique le pattern `DataLoader` mis en place : la classe abstraite, l'implémentation CSV active, le stub de `DatabaseDataLoader` préparé pour une future connexion base de données, et la factory function `get_data_loader()`.

### `PIPELINE_ENTRAINEMENT.md` — Pipeline d'entraînement

Documentation du pipeline ML complet : de la donnée brute jusqu'au modèle sérialisé `.pkl`, avec les étapes de preprocessing, feature engineering, entraînement Prophet, validation croisée et sauvegarde MLflow.

### `AMELIORATIONS_PROPHET.md` et `GRID_SEARCH_GUIDE.md`

Ces deux documents couvrent les décisions techniques liées à l'optimisation du modèle : les paramètres Prophet testés, la logique de grid search, les métriques utilisées pour comparer les runs.

### `DOCKER_NGROK.md` — Infrastructure Docker et exposition ngrok

Guide d'utilisation du `docker-compose.yml` pour lancer l'ensemble du système en containers, et explication du mécanisme ngrok pour exposer l'API d'inférence à Microsoft Fabric depuis un réseau local.

### `DASHBOARD_GUIDE.md` et `FORMULE_COUT_HORAIRE.md`

Documentation de l'interface Streamlit : les pages disponibles, les paramètres de filtrage, et le détail de la formule de calcul du coût horaire (TRV, heures pleines/creuses, puissance souscrite).

---

## 3. La documentation des tests (dossier `tests/`)

En plus de la documentation MkDocs, j'ai produit une documentation spécifique au niveau du dossier de tests.

### `tests/README.md`

Ce fichier explique en termes simples ce qui est testé, comment lancer les tests, et une règle de base pour écrire un bon test. Il s'adresse à un développeur qui n'a jamais vu le projet et veut comprendre en moins de deux minutes comment contribuer.

### `tests/TESTS_CERTIFICATION.md`

Ce document est une description précise et exhaustive de tout ce qui a été mis en place pour la certification (C12). Il documente :
- les outils utilisés (pytest, fixtures `tmp_path`, marqueurs `slow` et `requires_data`),
- la structure complète du dossier `tests/` avec le rôle de chaque fichier,
- les fixtures définies dans `conftest.py` avec leur description et leur usage,
- pour chaque fichier de test, un tableau listant chaque test, ce qui est vérifié, et pourquoi.

Ce niveau de détail garantit que n'importe quel évaluateur peut comprendre la stratégie de test sans avoir à lire le code source.

### `tests/CICD_MLOPS_CERTIFICATION.md`

Document de référence pour la certification (C13). Il décrit :
- les cinq workflows GitHub Actions du projet et leur rôle respectif,
- les déclencheurs, les étapes et les options de chaque pipeline,
- la logique de ciblage des déploiements (un workflow ne se déclenche que si les fichiers qu'il concerne ont changé),
- la gestion des secrets (jamais dans le code, stockés dans GitHub Secrets),
- le double tagging des images Docker (`latest` et hash de commit pour la traçabilité).

---

## 4. Organisation du dépôt Git

Le dépôt est structuré de façon à ce que chaque collaborateur sache où trouver ce dont il a besoin sans chercher. Les dossiers principaux ont chacun leur utilité claire :

| Dossier | Contenu |
|---|---|
| `src/` | Modules Python métier (preprocessing, feature engineering, train, predict) |
| `api/` | Code source des deux APIs FastAPI |
| `tests/` | Tests automatisés + documentation de test |
| `docs/` | Documentation MkDocs navigable |
| `config/` | Fichiers de configuration YAML et environnement |
| `models/` | Modèles sérialisés Prophet (.pkl) |
| `data/` | Données brutes, traitées et prédictions |
| `.github/workflows/` | Pipelines CI/CD GitHub Actions |

Le fichier `config/config.yaml` centralise tous les paramètres du pipeline (horizon de prédiction, liste des features, seuils de validation, paramètres MLflow). Tout changement de paramètre se fait dans ce fichier unique, sans modifier le code source.

---

## 5. Ce que cette documentation permet concrètement

Un développeur qui reprend le projet sans contexte peut :
- comprendre l'architecture en lisant `docs/index.md`,
- lancer le projet en suivant `docs/QUICK_START.md`,
- comprendre les tests en lisant `tests/README.md` puis `tests/TESTS_CERTIFICATION.md`,
- reproduire un entraînement en suivant `docs/PIPELINE_ENTRAINEMENT.md`,
- comprendre le CI/CD en lisant `docs/GUIDE_CICD.md`,
- retrouver n'importe quel run MLflow grâce à `docs/MLFLOW_GUIDE.md`.

La documentation n'est pas un ajout de fin de projet. Elle a été produite au fur et à mesure, en même temps que le code, et elle est versionnée dans le même dépôt Git. Un jury technique peut donc retrouver l'historique de chaque document via `git log`.
