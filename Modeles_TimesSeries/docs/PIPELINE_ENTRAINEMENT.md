# Pipeline d'entraînement

## Vue d'ensemble

Le pipeline d'entraînement transforme des données brutes (historique Enedis + météo) en un **modèle Prophet prêt à prédire**. Il suit six étapes séquentielles.

```
Données brutes CSV
        │
        ▼
1. Chargement et validation
        │
        ▼
2. Preprocessing (nettoyage, resampling horaire)
        │
        ▼
3. Feature engineering (lags, rolling, encodage cyclique, jours fériés)
        │
        ▼
4. Sélection des features (RandomForest, top N)
        │
        ▼
5. Entraînement Prophet (avec tracking MLflow)
        │
        ▼
6. Évaluation et sauvegarde du modèle
```

---

## Structure des modules `src/`

```
src/
├── data_loader.py          # Chargement et validation des fichiers CSV
├── preprocessing.py        # Nettoyage, gestion des valeurs manquantes, resampling
├── feature_engineering.py  # Construction de toutes les features temporelles
├── train.py                # Entraînement Prophet + MLflow
├── predict.py              # Génération de prédictions à partir d'un modèle sauvegardé
├── grid_search.py          # Optimisation hyperparamètres (voir Guide Grid Search)
├── mlflow_utils.py         # Helpers MLflow
└── utils.py                # Utilitaires divers (chargement config, logs)
```

---

## Étape 1 — Chargement des données

**Module :** `src/data_loader.py`

Les données d'un site sont stockées dans `data/raw/sites/dataclean_prm_<prm>.csv`.

Ce fichier est produit par la synchronisation (endpoint `POST /sync/prm/{prm}` de l'API Inference).

Schéma attendu :

| Colonne | Type | Description |
|---|---|---|
| `timestamp` | datetime | Horodatage (UTC, fréquence horaire) |
| `puissance` | float | Puissance mesurée en kW |
| `temperature` | float | Température en °C |
| Autres colonnes météo | float | Vent, humidité, rayonnement… |

---

## Étape 2 — Preprocessing

**Module :** `src/preprocessing.py`

Actions effectuées :

- suppression des doublons d'horodatage,
- rééchantillonnage forcé à la fréquence horaire (si des trous existent),
- interpolation linéaire des valeurs manquantes (courtes lacunes),
- détection et traitement des outliers par méthode IQR,
- normalisation ou standardisation selon la configuration.

---

## Étape 3 — Feature Engineering

**Module :** `src/feature_engineering.py`

Toutes les features construites :

| Feature | Explication |
|---|---|
| `puissance_lag_1` | Valeur de puissance à T-1h (valeur précédente) |
| `puissance_lag_24` | Valeur de puissance il y a 24h (même heure la veille) |
| `puissance_lag_168` | Valeur de puissance il y a 7 jours (même heure, même jour de semaine) |
| `puissance_roll_24` | Moyenne mobile sur 24h |
| `puissance_roll_168` | Moyenne mobile sur 7 jours |
| `heure_sin`, `heure_cos` | Encodage cyclique de l'heure (cycle 24h) |
| `jour_semaine_sin`, `jour_semaine_cos` | Encodage cyclique du jour de la semaine |
| `mois_sin`, `mois_cos` | Encodage cyclique du mois de l'année |
| `jour_ferie` | Indicateur booléen jour férié français |
| `temperature`, `vent`, ... | Variables météo passées en régresseurs Prophet |

### Pourquoi l'encodage cyclique ?

Une feature comme `heure = 23` et `heure = 0` sont proches dans le temps, mais très éloignées numériquement. L'encodage cyclique résout ce problème :

$$heure\_sin = \sin\left(\frac{2\pi \times heure}{24}\right)$$

$$heure\_cos = \cos\left(\frac{2\pi \times heure}{24}\right)$$

Ainsi, minuit (0h) et 23h sont proches dans l'espace des features.

---

## Étape 4 — Sélection des features

**Module :** `src/feature_engineering.py` (fonction `select_top_features`)

Avec 28+ features potentielles, certaines apportent peu d'information et peuvent bruiter le modèle. Un **RandomForest léger** est entraîné en quelques secondes pour évaluer l'importance relative de chaque feature.

Configuration dans `config.yaml` :

```yaml
prophet:
  feature_selection:
    enabled: true
    top_n: 15
```

Résultat type :

```
1. puissance_lag_1       : 0.2341
2. puissance_roll_24     : 0.1823
3. temperature           : 0.1456
4. puissance_lag_24      : 0.1102
...
15. jour_ferie           : 0.0123
```

---

## Étape 5 — Entraînement Prophet

**Module :** `src/train.py`

Prophet est un modèle additif développé par Meta, conçu pour les séries temporelles avec saisonnalités multiples.

Appel principal :

```python
python src/train.py --prm 30000250086126
```

Ou via la CLI :

```bash
python main.py train --prm 30000250086126
python main.py train --all-sites   # Entraîne tous les sites disponibles
```

Les métriques, paramètres et artefacts sont automatiquement trackés dans MLflow.

---

## Étape 6 — Évaluation et sauvegarde

**Métriques calculées sur l'ensemble de validation :**

| Métrique | Formule | Interprétation |
|---|---|---|
| MAE | $\frac{1}{n}\sum|y_i - \hat{y}_i|$ | Erreur absolue moyenne (en kW) |
| RMSE | $\sqrt{\frac{1}{n}\sum(y_i - \hat{y}_i)^2}$ | Pénalise les grandes erreurs |
| MAPE | $\frac{100}{n}\sum\frac{|y_i - \hat{y}_i|}{y_i}$ | Erreur relative en % |
| R² | $1 - \frac{SS_{res}}{SS_{tot}}$ | Part de variance expliquée (1 = parfait) |

Note sur le MAPE : les valeurs très faibles (< 20W) sont exclues du calcul car elles créent des pourcentages artificiellement élevés (diviser par 0.01 donne 100% d'erreur même pour 1W d'écart).

**Sauvegarde du modèle :**

```
models/saved/prophet_model_<prm>_latest.pkl
```

---

## Prédiction à partir d'un modèle sauvegardé

**Module :** `src/predict.py`

```bash
python main.py predict --prm 30000250086126 --meteo data/raw/meteo/meteo_future.csv
```

Étapes internes :

1. charger le modèle `.pkl`,
2. charger et préparer la météo future,
3. construire le dataframe `future` Prophet avec les régresseurs,
4. appeler `model.predict(future)`,
5. écrire la sortie dans `data/predictions/`.

---

## Configuration du pipeline (`config/config.yaml`)

```yaml
pipeline:
  horizon_days: 14          # Nombre de jours de prédiction
  validation_split: 0.2     # Part des données pour la validation

prophet:
  changepoint_prior_scale: 0.1
  seasonality_prior_scale: 15
  seasonality_mode: multiplicative
  feature_selection:
    enabled: true
    top_n: 15
  filter_low_values:
    enabled: true
    threshold_kw: 0.02

mlflow:
  tracking_uri: mlruns
  experiment_name: Prophet_Energy_Forecast
```
