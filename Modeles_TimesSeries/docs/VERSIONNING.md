# Versionning du projet

Cette page décrit les mécanismes de versionning **actifs dans le dépôt** : code, images, modèles et documentation.

## 1) Versionning Git (code)

Les workflows CI sont déclenchés sur :

- `main`
- `branch-ia`

Fichier concerné : `.github/workflows/ci.yml`.

Le CD API est déclenché sur `main` avec filtres de chemins :

- `.github/workflows/cd-api-dataclean.yml`
- `.github/workflows/cd-api-inference.yml`

## 2) Versionning des images Docker

Les workflows CD construisent et poussent 2 tags :

- `latest`
- `${github.sha}`

Exemple (DataClean / Inference) :

```text
<docker_user>/api-dataclean:latest
<docker_user>/api-dataclean:<commit_sha>

<docker_user>/api-inference:latest
<docker_user>/api-inference:<commit_sha>
```

Ce mécanisme permet :

- rollback vers une version précise,
- traçabilité code ↔ image déployée.

## 3) Versionning des modèles Prophet

Le script `src/train.py` sauvegarde pour chaque PRM :

- version horodatée : `prophet_model_<prm>_<YYYYMMDD_HHMMSS>.pkl`
- alias courant : `prophet_model_<prm>_latest.pkl`
- métriques : `prophet_metrics_<prm>.json`

Répertoire : `models/saved/`.

Schéma logique :

```text
train.py
  ├─ écrit une version immuable timestampée
  ├─ met à jour l'alias latest du PRM
  └─ écrit le JSON de métriques associé
```

## 4) Versionning des artefacts de recherche

Les runs de recherche d'hyperparamètres produisent notamment :

- `grid_search_trials_<timestamp>.csv`
- `grid_search_summary_<timestamp>.csv`
- `prophet_best_params_<prm>.json`

Le dossier `mlruns/` conserve également l'historique des runs MLflow.

## 5) Versionning de la documentation

Le workflow `.github/workflows/sync_docs.yml` synchronise `Modeles_TimesSeries/docs/` vers un dépôt documentaire partagé.

Message de commit utilisé :

```text
docs: sync Projet Conso Energ (<commit_sha>)
```

## 6) Recommandations d'usage (équipe)

- Référencer un modèle par nom timestampé pour les analyses reproductibles.
- Réserver `*_latest.pkl` aux usages opérationnels.
- En production, déployer des images taguées SHA plutôt que `latest`.
