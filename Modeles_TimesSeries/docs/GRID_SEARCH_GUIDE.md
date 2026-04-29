# Guide Grid Search Prophet (Mango)

## 🎯 Objectif

Le script `src/grid_search.py` sert à trouver automatiquement les meilleurs hyperparamètres Prophet par site (PRM), puis à :

- sauvegarder les meilleurs paramètres,
- mettre à jour `site_overrides` dans `config/config.yaml`,
- exporter un résumé et le détail des essais,
- tracer les essais dans MLflow (si activé).

La recherche est faite en 2 phases :

1. **Trend** (growth, changepoints)
2. **Seasonality** (mode + priors + fourier orders)

Le moteur d’optimisation est **Mango** (`arm-mango`).

---

## ✅ Prérequis

Depuis le dossier `Modeles_TimesSeries` :

```bash
pip install -r requirements.txt
```

Vérifier que `arm-mango` est bien présent (déjà ajouté dans `requirements.txt`).

---

## ⚙️ Configuration `grid_search` (config.yaml)

Exemple recommandé (rapide et stable) :

```yaml
grid_search:
  random_seed: 42

  # Nombre d'essais par phase
  n_iter_trend: 10
  n_iter_season: 12

  # Accélération
  fast_mode: true
  train_window_days: 365
  max_train_rows: 5000
  uncertainty_samples: 0
  fit_algorithm: LBFGS
  fit_iter: 300
  fit_seed: 42

  # Espace de recherche trend
  growth: [flat]
  changepoint_prior_scale: [0.001, 0.01, 0.05, 0.1, 0.3]
  n_changepoints: [10, 25, 50]
  changepoint_range: [0.8, 0.9, 0.95]

  # Espace de recherche seasonality
  seasonality_mode: [additive, multiplicative]
  seasonality_prior_scale: [1.0, 5.0, 10.0, 20.0]
  holidays_prior_scale: [5, 10, 20]
  daily_fourier_order: [5, 15, 20]
  weekly_fourier_order: [5, 15, 20]
  yearly_fourier_order: [5, 15, 20]

  # Métriques à minimiser
  metric: [mae, rmse]
```

### Comment la loss est calculée

- Si `metric: [mae, rmse]` → Mango optimise `mae + rmse`.
- Sinon → Mango optimise la somme des métriques demandées.

Cela permet de chercher un compromis **simultané** entre MAE et RMSE.

---

## ▶️ Lancer le grid search

### Un seul site (recommandé pour valider)

```bash
python -m src.grid_search --prm 30000250086126
```

### Plusieurs sites

```bash
python -m src.grid_search --prm 30000250086126 30000650805048
```

### Tous les sites trouvés dans `data/processed`

```bash
python -m src.grid_search
```

---

## 📈 Lire la sortie console

À chaque essai, tu verras :

- les paramètres testés,
- les métriques (`mae`, `rmse`, etc.),
- `Objective loss` (ce que Mango minimise),
- le temps de l’essai,
- l’ETA estimé.

Exemple :

```text
[trend batch item 2/10 | essai 4/10] {...}
→ mae = ... | rmse = ...
   Objective loss: ...
   Temps essai: ...s | Temps total: ...min | ETA: ...min
```

---

## 💾 Fichiers générés

Le script écrit :

- `models/saved/prophet_best_params_<PRM>.json`
- `models/saved/grid_search_summary_<timestamp>.csv`
- `models/saved/grid_search_trials_<timestamp>.csv`

et met à jour :

- `config/config.yaml` → `site_overrides[<PRM>]`

---

## 🔬 MLflow (optionnel)

Si `mlflow.enabled: true` dans la config :

- création d’un run par PRM,
- log des meilleurs paramètres,
- log des métriques globales,
- artifact CSV des essais.

---

## 🐢 « Ça freeze » : diagnostic rapide

En pratique, ce n’est pas un freeze UI : c’est souvent un essai Prophet (Stan) qui calcule longtemps.

### Réglages anti-lenteur

1. Baisser `n_iter_trend` / `n_iter_season` (ex: 4 et 6 pour debug)
2. Garder `fast_mode: true`
3. Réduire `train_window_days` (ex: 180)
4. Limiter `max_train_rows` (ex: 2000-5000)
5. Laisser `uncertainty_samples: 0`
6. Utiliser `fit_algorithm: LBFGS`
7. Baisser `fit_iter` (ex: 150-300)

### Profil « debug ultra rapide »

```yaml
grid_search:
  n_iter_trend: 4
  n_iter_season: 6
  fast_mode: true
  train_window_days: 180
  max_train_rows: 2000
  uncertainty_samples: 0
  fit_algorithm: LBFGS
  fit_iter: 150
  metric: [mae, rmse]
```

---

## 🧭 Workflow conseillé

1. Lancer sur **1 PRM** avec profil rapide
2. Vérifier que les résultats sont cohérents
3. Augmenter progressivement les itérations
4. Étendre aux autres PRM

---

## ❗ Notes importantes

- Le script suppose des données preprocessées disponibles dans `data/processed`.
- Si aucun regressor configuré n’est présent, le script s’arrête.
- Les meilleurs paramètres Prophet sont réinjectés automatiquement dans `site_overrides`.

---

## Commande type (production légère)

```bash
python -m src.grid_search --prm 30000250086126
```

Puis vérifier :

1. le JSON des best params,
2. la ligne correspondante dans `site_overrides`,
3. les CSV de summary/trials.
