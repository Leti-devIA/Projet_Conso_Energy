# Guide MLflow - Projet Consommation Énergétique

## 🎯 Qu'est-ce que MLflow apporte ?

MLflow remplace TensorBoard et ajoute des fonctionnalités MLOps pour Prophet :

| Fonctionnalité | Description |
|----------------|-------------|
| **Tracking** | Historique de tous les entraînements avec métriques |
| **Comparaison** | Compare facilement plusieurs modèles |
| **Versioning** | Gestion des versions de modèles |
| **Artéfacts** | Stockage des graphiques et rapports |
| **Registry** | Registre centralisé des modèles |
| **Reproductibilité** | Environnements et paramètres sauvegardés |

## 📦 Installation

```powershell
pip install mlflow
```

## 🚀 Utilisation

### 1. Entraîner avec tracking MLflow

Le tracking est **automatique** lors de l'entraînement :

```powershell
python src/train.py
```

MLflow enregistre automatiquement :
- ✅ Paramètres Prophet (seasonality_mode, prior scales...)
- ✅ Métriques de validation (MAE, RMSE, MAPE, R²)
- ✅ Le modèle Prophet complet
- ✅ Graphiques des prédictions et composantes
- ✅ Résumé texte

### 2. Visualiser avec l'UI MLflow

Lancer l'interface web :

```powershell
mlflow ui --port 5000
```

Puis ouvrir dans le navigateur : **http://localhost:5000**

Vous verrez :
- 📊 Tableau de tous les runs avec métriques
- 📈 Graphiques de comparaison
- 🔍 Détails de chaque entraînement
- 📁 Artefacts (modèles, graphiques)

### 3. Comparer plusieurs modèles

```python
from src.mlflow_utils import compare_models

# Comparer tous les modèles par RMSE
results = compare_models(
    experiment_name="Prophet_Energy_Forecast",
    metric="val_rmse"
)

# Affiche le meilleur modèle et le classement
print(results[['run_id', 'metrics.val_rmse', 'metrics.val_mae', 'params.site_prm']])
```

### 4. Charger un modèle depuis MLflow

```python
from src.mlflow_utils import load_model_from_mlflow

# Charger le modèle d'un run spécifique
model = load_model_from_mlflow(run_id="abc123...")

# Faire des prédictions
forecast = model.predict(future_df)
```

### 5. Logger des prédictions long terme

```python
from src.mlflow_utils import log_longterm_predictions

# Après génération de prédictions 3 ans
log_longterm_predictions(
    df_predictions=predictions,
    prm="30000250086126",
    nb_annees=3
)
```

## 📂 Structure MLflow

```
Modeles_TimesSeries/
├── mlruns/                    # Dossier MLflow
│   ├── 0/                     # Experiment ID
│   │   ├── <run_id>/          # Run individuel
│   │   │   ├── artifacts/     # Modèle + graphiques
│   │   │   ├── metrics/       # Métriques
│   │   │   ├── params/        # Paramètres
│   │   │   └── tags/          # Tags
│   └── .trash/
└── mlflow.db                  # Base de données (si backend SQL)
```

## 🔧 Configuration

Voir [config/config.yaml](../config/config.yaml) :

```yaml
mlflow:
  tracking_uri: "mlruns"              # Local ou distant
  experiment_name: "Prophet_Energy_Forecast"
  artifact_location: "mlruns"
```

### Tracking distant (optionnel)

Pour un serveur MLflow distant :

```yaml
mlflow:
  tracking_uri: "http://mlflow-server:5000"
```

## 📊 Métriques trackées

### Entraînement
- `val_mae` : Mean Absolute Error sur validation
- `val_rmse` : Root Mean Squared Error
- `val_mape` : Mean Absolute Percentage Error
- `val_r2` : Coefficient de détermination R²

### Prédictions long terme
- `pred_mean_kw` : Consommation moyenne prédite
- `pred_std_kw` : Écart-type
- `pred_mean_kw_2026`, `pred_mean_kw_2027`, etc. : Par année
- `confidence_interval_width` : Largeur moyenne intervalle confiance

## 🎯 Workflow type

1. **Expérimenter** : Entraîner plusieurs modèles avec différents paramètres
```powershell
# Modifier config/config.yaml (ex: seasonality_mode: additive)
python src/train.py

# Modifier à nouveau et ré-entraîner
python src/train.py
```

2. **Comparer** : Visualiser dans l'UI MLflow
```powershell
mlflow ui --port 5000
```

3. **Sélectionner** : Identifier le meilleur run

4. **Déployer** : Charger le modèle et générer prédictions
```python
model = load_model_from_mlflow(run_id="best_run_id")
```

## 🔗 Intégration avec vos scripts

### `train.py`
✅ Déjà intégré automatiquement

### `predict_longterm.py`
Ajoutez ceci après génération des prédictions :

```python
from mlflow_utils import log_longterm_predictions

# À la fin de predict_longterm()
if MLFLOW_AVAILABLE:
    log_longterm_predictions(df_predictions, prm=prm, nb_annees=nb_annees)
```

## 📚 Ressources

- [Documentation MLflow](https://mlflow.org/docs/latest/index.html)
- [MLflow Prophet Flavor](https://mlflow.org/docs/latest/python_api/mlflow.prophet.html)
- [Tutoriel MLflow](https://mlflow.org/docs/latest/tutorials-and-examples/index.html)

## ⚡ Commandes rapides

```powershell
# Lancer l'UI
mlflow ui

# Avec port spécifique
mlflow ui --port 8080

# Comparer modèles (Python)
python -c "from src.mlflow_utils import compare_models; compare_models()"

# Nettoyer les runs (attention !)
# rm -r mlruns
```

## 🎁 Bonus : Registry de modèles

Pour mettre un modèle en production :

```python
import mlflow

# Enregistrer le meilleur modèle
mlflow.register_model(
    model_uri=f"runs:/{run_id}/model",
    name="Prophet_Production"
)

# Promouvoir en production
client = mlflow.tracking.MlflowClient()
client.transition_model_version_stage(
    name="Prophet_Production",
    version=1,
    stage="Production"
)
```

---

**Auteur** : GitHub Copilot
**Date** : Février 2026
**Projet** : Prédiction Consommation Énergétique (Prophet + MLflow)
