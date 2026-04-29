# MLflow — Tracking et registre de modèles

## Qu'est-ce que MLflow ?

MLflow est une plateforme open-source de **gestion du cycle de vie des modèles ML**. Dans ce projet, il remplit trois rôles :

1. **Tracking** : enregistrer les paramètres, métriques et artefacts de chaque entraînement.
2. **Comparaison** : comparer visuellement plusieurs runs pour identifier le meilleur modèle.
3. **Registry** : versionner et promouvoir des modèles (Staging → Production).

> Pour un développeur reprenant le projet : MLflow est votre journal de bord scientifique. Chaque fois que vous entraînez un modèle, une entrée est créée avec tous les paramètres et résultats. Vous pouvez revenir en arrière, comparer et reproduire n'importe quel run.

---

## Ce qui est tracké automatiquement

À chaque entraînement (`python src/train.py`), MLflow enregistre :

| Catégorie | Exemples |
|---|---|
| Paramètres | `changepoint_prior_scale`, `seasonality_mode`, `top_n_features`, `prm` |
| Métriques | `val_mae`, `val_rmse`, `val_mape`, `val_r2` |
| Artefacts | Modèle Prophet `.pkl`, graphiques de prédiction, graphiques des composantes, résumé texte |
| Tags | `prm`, `git_commit`, `python_version` |

---

## Installation

```bash
pip install mlflow
# (déjà inclus dans requirements.txt)
```

---

## Lancer l'interface web MLflow

```bash
# Depuis Modeles_TimesSeries/
mlflow ui --port 5000
```

Ouvrir dans le navigateur : **http://localhost:5000**

Vous verrez :

- la liste de tous les runs avec leurs métriques,
- des graphiques de comparaison entre runs,
- les détails (paramètres, métriques, artefacts) de chaque run,
- la possibilité de télécharger le modèle depuis un run spécifique.

---

## Structure des fichiers MLflow

```
Modeles_TimesSeries/
├── mlruns/
│   ├── <experiment_id>/
│   │   ├── <run_id>/
│   │   │   ├── artifacts/          # Modèle + graphiques
│   │   │   │   ├── model/
│   │   │   │   ├── forecast_plot.png
│   │   │   │   └── components_plot.png
│   │   │   ├── metrics/            # Fichiers texte avec valeurs
│   │   │   │   ├── val_mae
│   │   │   │   └── val_rmse
│   │   │   ├── params/             # Fichiers texte avec paramètres
│   │   │   └── tags/
│   └── .trash/
```

---

## Comparer plusieurs modèles (Python)

```python
from src.mlflow_utils import compare_models

results = compare_models(
    experiment_name="Prophet_Energy_Forecast",
    metric="val_rmse"
)

# Affiche le classement par RMSE
print(results[["run_id", "metrics.val_rmse", "metrics.val_mae", "params.site_prm"]])
```

---

## Charger un modèle depuis un run MLflow

```python
from src.mlflow_utils import load_model_from_mlflow

# Charger par run_id (visible dans l'UI MLflow)
model = load_model_from_mlflow(run_id="abc123def456...")

# Faire des prédictions
future_df = ...  # DataFrame Prophet avec colonne 'ds' + régresseurs
forecast = model.predict(future_df)
```

---

## Logger des prédictions long terme

```python
from src.mlflow_utils import log_longterm_predictions

log_longterm_predictions(
    df_predictions=predictions_df,
    prm="30000250086126",
    nb_annees=3
)
```

---

## Configuration MLflow (`config/config.yaml`)

```yaml
mlflow:
  tracking_uri: "mlruns"                    # Répertoire local (ou URI distante)
  experiment_name: "Prophet_Energy_Forecast"
  artifact_location: "mlruns"
```

Pour utiliser un serveur MLflow distant (partagé en équipe) :

```yaml
mlflow:
  tracking_uri: "http://mlflow-server:5000"
```

---

## Bonnes pratiques

- Chaque entraînement doit avoir un **nom d'expérience cohérent** (`experiment_name` dans config).
- Toujours vérifier les métriques dans MLflow avant de valider un modèle en production.
- Utiliser les **tags** pour filtrer facilement par PRM dans l'interface.
- Archiver les runs non pertinents plutôt que de les supprimer (ils peuvent servir de référence).
