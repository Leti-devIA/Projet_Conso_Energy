# Grid Search Prophet

## Objectif

Le grid search permet de trouver automatiquement les **meilleurs hyperparamètres Prophet pour chaque site (PRM)**, plutôt que d'en choisir manuellement.

Le moteur d'optimisation utilisé est **Mango** (`arm-mango`), un algorithme de recherche bayésienne plus efficace qu'une recherche par grille exhaustive.

---

## Principe de fonctionnement

La recherche se dérule en **deux phases séquentielles** :

### Phase 1 — Optimisation de la tendance (Trend)

Hyperparamètres explorés :

- `growth` : type de croissance (`flat`, `linear`, `logistic`)
- `changepoint_prior_scale` : flexibilité de la tendance
- `n_changepoints` : nombre de points de changement potentiels
- `changepoint_range` : fraction de l'historique où chercher des changements

### Phase 2 — Optimisation de la saisonnalité (Seasonality)

Hyperparamètres explorés :

- `seasonality_mode` : `additive` ou `multiplicative`
- `seasonality_prior_scale` : amplitude des cycles
- `holidays_prior_scale` : impact des jours fériés
- `daily_fourier_order` : détail du cycle journalier
- `weekly_fourier_order` : détail du cycle hebdomadaire
- `yearly_fourier_order` : détail du cycle annuel

---

## Configuration (`config/config.yaml`)

```yaml
grid_search:
  random_seed: 42

  # Nombre d'essais par phase
  n_iter_trend: 10
  n_iter_season: 12

  # Mode accéléré (recommandé pour débuter)
  fast_mode: true
  train_window_days: 365   # Utilise seulement 1 an d'historique pour l'entraînement
  max_train_rows: 5000
  uncertainty_samples: 0   # Désactive intervalles de confiance (plus rapide)
  fit_algorithm: LBFGS
  fit_iter: 300
  fit_seed: 42

  # Espace de recherche — Trend
  growth: [flat]
  changepoint_prior_scale: [0.001, 0.01, 0.05, 0.1, 0.3]
  n_changepoints: [10, 25, 50]
  changepoint_range: [0.8, 0.9, 0.95]

  # Espace de recherche — Seasonality
  seasonality_mode: [additive, multiplicative]
  seasonality_prior_scale: [1.0, 5.0, 10.0, 20.0]
  holidays_prior_scale: [5, 10, 20]
  daily_fourier_order: [5, 15, 20]
  weekly_fourier_order: [5, 15, 20]
  yearly_fourier_order: [5, 15, 20]

  # Métrique à minimiser
  metric: [mae, rmse]
```

### Calcul de la loss

Quand `metric: [mae, rmse]`, Mango minimise la somme `mae + rmse`, cherchant un compromis entre les deux erreurs simultanément.

---

## Lancer le grid search

```bash
# Un seul site (recommandé pour tester)
python -m src.grid_search --prm 30000250086126

# Plusieurs sites
python -m src.grid_search --prm 30000250086126 30000650805048

# Tous les sites disponibles dans data/processed/
python -m src.grid_search
```

---

## Lire les résultats en console

À chaque essai, la console affiche :

```
[trend batch 2/10 | essai 4/10] {changepoint_prior_scale: 0.05, n_changepoints: 25, ...}
→ mae = 0.038 | rmse = 0.041
   Objective loss: 0.079
   Temps essai: 12s | Temps total: 2.1min | ETA: 3.5min
```

---

## Résultats produits

Après le grid search, plusieurs fichiers sont générés :

| Fichier | Contenu |
|---|---|
| `exports/grid_search_<prm>_best.json` | Meilleurs paramètres trouvés |
| `exports/grid_search_<prm>_all_trials.csv` | Détail de tous les essais |
| `config/config.yaml` (section `site_overrides`) | Mise à jour automatique du config |

### Exemple de mise à jour automatique du config

```yaml
site_overrides:
  "30000250086126":
    changepoint_prior_scale: 0.1
    n_changepoints: 25
    seasonality_mode: multiplicative
    seasonality_prior_scale: 15.0
    holidays_prior_scale: 10
    daily_fourier_order: 15
    weekly_fourier_order: 15
    yearly_fourier_order: 5
```

Ces paramètres sont automatiquement utilisés lors du prochain entraînement de ce PRM.

---

## Visualiser les essais dans MLflow

Si MLflow est activé, chaque essai est tracké comme un run indépendant :

```bash
mlflow ui --port 5000
# Ouvrir http://localhost:5000
```

Vous pouvez filtrer par PRM, comparer les loss des différents essais et voir quels paramètres donnent les meilleurs résultats.

---

## Conseils pratiques

- Commencer avec `fast_mode: true` et `n_iter_trend: 10` pour vérifier que tout fonctionne.
- Augmenter `n_iter_trend` et `n_iter_season` pour une recherche plus approfondie (ex: 30/40) au prix d'un temps plus long.
- Si les résultats semblent instables, augmenter `train_window_days` (plus d'historique = meilleure évaluation).
- Le grid search est à relancer uniquement quand les patterns de consommation changent significativement ou lors de l'ajout d'un nouveau site.
