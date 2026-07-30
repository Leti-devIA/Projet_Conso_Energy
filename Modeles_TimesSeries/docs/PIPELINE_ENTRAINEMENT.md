# Pipeline d'entraînement

## Vue d'ensemble

Le pipeline d'entraînement transforme les données brutes Enedis en un modèle Prophet prêt à produire des prévisions.

```text
Données brutes CSV (data/raw/sites)
        │
        ▼
1. Chargement des données
        │
        ▼
2. Preprocessing
   - agrégation horaire
   - nettoyage
   - sauvegarde des données traitées
        │
        ▼
3. Feature engineering
   - variables temporelles
   - lags
   - variables météo
   - jours fériés
   - variables thermiques
        │
        ▼
4. Préparation Prophet
   - sélection des régresseurs
   - filtrage des faibles consommations
        │
        ▼
5. Entraînement Prophet
        │
        ▼
6. Évaluation
        │
        ▼
7. Sauvegarde du modèle et des métriques
```

---

## Étape 2 — Preprocessing

**Module :** `src/preprocessing.py`

Pour chaque PRM :

```python
preprocess_pipeline(prm=prm)
```

Le pipeline :

1. charge le fichier :

```text
data/raw/sites/dataclean_prm_<PRM>.csv
```

2. réalise une agrégation horaire si nécessaire ;
3. applique les règles de nettoyage ;
4. sauvegarde les données préparées dans `data/processed`.

---

## Étape 3 — Feature Engineering

**Module :** `src/feature_engineering.py`

Principales features utilisées par Prophet :

| Feature | Description |
|----------|-------------|
| `temperature` | Température extérieure |
| `humidite` | Humidité relative |
| `precipitation` | Précipitations |
| `couverture_nuages` | Couverture nuageuse |
| `vitesse_vent` | Vitesse du vent |
| `is_holiday` | Jour férié français |
| `heure_sin`, `heure_cos` | Encodage cyclique de l'heure |
| `jour_sin`, `jour_cos` | Encodage cyclique du jour de semaine |
| `is_weekend` | Week-end |
| `temp_x_heure_sin` | Interaction température × heure |
| `temp_x_heure_cos` | Interaction température × heure |
| `dju_chauffage` | Degrés-jours de chauffage |
| `grand_froid` | Température négative |
| `puissance_lag_24` | Consommation observée à J-1 |
| `puissance_lag_168` | Consommation observée à J-7 |

---

## Étape 4 — Préparation Prophet

Les données sont converties au format attendu par Prophet :

| Colonne | Description |
|----------|-------------|
| `ds` | Horodatage |
| `y` | Variable cible |
| autres colonnes | Régresseurs Prophet |

Un filtrage optionnel des faibles consommations est appliqué :

```yaml
prophet:
  filter_low_values:
    enabled: true
    threshold_kw: 20
```

Toutes les observations dont la puissance est inférieure à 20 W sont retirées avant l'entraînement.

---

## Étape 5 — Entraînement Prophet

**Module :** `src/train.py`

Commande :

```bash
python -m src.train --prm 30000250086126
```

Tous les sites :

```bash
python -m src.train
```

Le modèle est construit à partir de la configuration globale puis éventuellement surchargé par les paramètres spécifiques au site :

```yaml
site_overrides:
  "30000650805048":
    growth: flat
    seasonality_mode: multiplicative
    changepoint_prior_scale: 0.1
```

Un découpage temporel est ensuite réalisé :

- données anciennes → entraînement ;
- derniers `validation.days` jours → validation.

Par défaut :

```yaml
validation:
  days: 120
```

---

## Étape 6 — Évaluation

Les métriques sont calculées sur la fenêtre de validation :

| Métrique | Description |
|-----------|-------------|
| MAE | Erreur absolue moyenne |
| RMSE | Racine de l'erreur quadratique moyenne |
| MAPE | Erreur moyenne en pourcentage |
| WAPE | Erreur absolue pondérée |
| R² | Coefficient de détermination |

Une baseline naïve utilisant la valeur observée à J-7 est également calculée à titre de comparaison.

---

## Étape 7 — Sauvegarde

Pour chaque site :

```text
models/saved/
├── prophet_model_<PRM>_<timestamp>.pkl
├── prophet_model_<PRM>_latest.pkl
└── prophet_metrics_<PRM>.json
```

Le fichier `latest.pkl` est automatiquement remplacé à chaque nouvel entraînement.

---

# Prédiction

**Module :** `src/predict.py`

Prédiction d'un seul site :

```bash
python -m src.predict --prm 30000650805048
```

Prédiction de tous les sites disposant d'un modèle :

```bash
python -m src.predict --all-sites
```

Le mode multi-sites :

1. détecte tous les fichiers `prophet_model_*_latest.pkl` ;
2. génère une météo future à partir des moyennes climatiques ;
3. reconstruit les features nécessaires ;
4. exécute `model.predict()` ;
5. sauvegarde les résultats dans :

```text
data/predictions/predictions_3ans_<PRM>.csv
```

La durée de projection est contrôlée par :

```bash
python -m src.predict --all-sites --years 3
```