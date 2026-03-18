# 📊 Projet de prévision énergétique (Prophet)

Projet de fin d’année orienté **apprentissage** : prévoir la consommation électrique horaire de plusieurs sites (PRM) avec **Prophet**, puis visualiser les résultats dans un dashboard Streamlit.

## 🎓 Pourquoi ce projet (version pédagogique)

Ce projet permet de montrer concrètement :
- la construction d’un pipeline data (chargement → nettoyage → features → modèle),
- l’évaluation d’un modèle de séries temporelles,
- l’optimisation d’hyperparamètres (grid search),
- la production de livrables utilisables (CSV, dashboard, métriques).

## 🧱 Architecture du projet

```text
Modeles_TimesSeries/
├── main.py                     # CLI principal (list-sites / train / predict)
├── dashboard_app.py            # Dashboard Streamlit
├── generate_meteo_all.py       # Génération météo long terme (optionnel)
├── config/config.yaml          # Paramétrage global du pipeline
├── data/
│   ├── raw/                    # Données brutes (sites, météo, prix)
│   ├── processed/              # Données nettoyées + enrichies
│   └── predictions/            # Prédictions exportées en CSV
├── models/saved/               # Modèles entraînés + exports grid search
├── src/                        # Logique métier
└── tests/                      # Tests unitaires
```

## ⚙️ Installation (Windows PowerShell)

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 🚀 Commandes essentielles

### 1) Lister les sites disponibles

```bash
python main.py list-sites
```

### 2) Entraîner Prophet

Un site :

```bash
python main.py train --prm 30000250086126
```

Tous les sites :

```bash
python main.py train --all-sites
```

### 3) Prédire avec un fichier météo futur

```bash
python main.py predict --prm 30000250086126 --meteo data/raw/meteo/meteo_horaire_30000250086126.csv
```

### 4) Optimiser les hyperparamètres (grid search)

Un site :

```bash
python -m src.grid_search --prm 30000250086126 --config config/config.yaml
```

Tous les sites :

```bash
python -m src.grid_search --config config/config.yaml
```

### 5) Dashboard

```bash
streamlit run dashboard_app.py
```

## 🌦️ Cas long terme (important)

Le CLI `main.py` expose aujourd’hui `predict` (pas `predict-longterm`).

Pour un scénario long terme :
1. Générer une météo climatique synthétique (optionnel) :

```bash
python generate_meteo_all.py --prm 30000250086126 --nb-annees 3
```

2. Lancer ensuite `predict` avec le CSV météo produit.

## 🧪 Métriques de performance

Le projet suit :
- **MAE** : erreur moyenne absolue,
- **RMSE** : sensible aux grosses erreurs,
- **MAPE** : erreur relative moyenne,
- **WAPE** : erreur relative globale pondérée,
- **R²** : part de variance expliquée.

Exemple de config multi-métriques pour le grid search :

```yaml
grid_search:
  metric:
    - rmse
    - wape
```

Le tri se fait d’abord sur `rmse`, puis `wape` sert de départage.

## 📁 Livrables générés

### Entraînement
- `models/saved/prophet_model_{PRM}_{timestamp}.pkl`
- `models/saved/prophet_model_{PRM}_latest.pkl`
- `models/saved/prophet_metrics_{PRM}.json`

### Grid search
- `models/saved/prophet_best_params_{PRM}.json`
- `models/saved/grid_search_summary_YYYYMMDD_HHMMSS.csv` (meilleur essai/site)
- `models/saved/grid_search_trials_YYYYMMDD_HHMMSS.csv` (tous les essais)

### Prédictions
- `data/predictions/*.csv`

## 🔍 Pipeline (vue simple)

1. Charger les données (`src/data_loader.py`)
2. Nettoyer / agréger (`src/preprocessing.py`)
3. Créer les variables explicatives (`src/feature_engineering.py`)
4. Entraîner Prophet (`src/train.py`)
5. Évaluer les métriques
6. Sauvegarder modèle et résultats
7. Produire des prédictions (`src/predict.py`)
8. Visualiser (`dashboard_app.py`)

## ✅ Tests

```bash
python run_tests.py
```

ou

```bash
pytest -q
```

## 🧑‍🏫 Conseils pour ta présentation de fin d’année

- Explique la logique du pipeline étape par étape avec un schéma simple.
- Montre un exemple de PRM : données d’entrée → modèle → CSV de sortie → dashboard.
- Justifie le choix de Prophet (interprétable, rapide, robuste en projet pédagogique).
- Commente au moins 2 limites (qualité météo, dérive, données manquantes).
- Présente une amélioration future (ex: meilleure validation temporelle, enrichissement prix/activité).

---

**Version** : 3.1 (Prophet-only, pédagogique)
