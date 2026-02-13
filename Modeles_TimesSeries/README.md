# 📊 Prédiction de Consommation Énergétique

Système de prédiction de consommation énergétique basé sur LSTM pour plusieurs sites avec dashboard interactif.

## 🎯 Fonctionnalités

- ✅ **Multi-sites** : Gestion simultanée de plusieurs sites (PRM)
- ✅ **Prédictions long terme** : 3 ans avec moyennes climatiques
- ✅ **Dashboard interactif** : Visualisation Streamlit
- ✅ **Architecture modulaire** : Prêt pour base de données

---

## 🏗️ Architecture

```
Modeles_TimesSeries/
├── main.py                         # CLI principal
├── config/config.yaml              # Configuration
├── data/
│   ├── raw/
│   │   ├── sites/                  # dataclean_prm_{PRM}.csv
│   │   ├── meteo/                  # meteo_moyennes_{ans}ans_{PRM}.csv
│   │   └── prix/                   # prix_spot.csv
│   ├── processed/                  # data_preprocessed_{PRM}.csv
│   └── predictions/                # predictions_longterm_{ans}ans_{PRM}.csv
├── models/saved/                   # lstm_energy_forecast_latest_{PRM}.h5
├── src/
│   ├── data_loader.py              # Chargement données
│   ├── preprocessing.py            # Nettoyage
│   ├── feature_engineering.py      # Features (lags, rolling)
│   ├── model.py                    # LSTM
│   ├── train.py                    # Entraînement
│   ├── predict_longterm.py         # Prédictions 3 ans
│   └── generate_climate_averages.py # Moyennes climat
├── dashboard_longterm.py           # Dashboard Streamlit
└── generate_all_predictions.py     # Batch tous sites
```

---

## 🚀 Quick Start

### Installation
```bash
pip install -r requirements.txt
```

### Lister les sites
```bash
python main.py list-sites
```

### Entraîner
```bash
# Un site
python main.py train --prm 30000540191777

# Tous les sites
python main.py train --all-sites
```

### Prédictions 3 ans
```bash
# Un site
python main.py predict-longterm --prm 30000540191777 --years 3

# Tous les sites
python generate_all_predictions.py
```

### Dashboard
```bash
streamlit run dashboard_longterm.py
```

---

## 📋 Commandes Principales

| Commande | Description |
|----------|-------------|
| `python main.py list-sites` | Liste sites disponibles |
| `python main.py train --prm XXXXX` | Entraîne un site |
| `python main.py predict-longterm --prm XXXXX --years 3` | Prédictions 3 ans |
| `python generate_all_predictions.py` | Batch tous sites |
| `streamlit run dashboard_longterm.py` | Lance dashboard |

---

## 📊 Pipeline

```
DONNÉES → PREPROCESSING → FEATURE ENGINEERING → ENTRAÎNEMENT → PRÉDICTIONS → DASHBOARD
```

1. **Données brutes** : `data/raw/sites/dataclean_prm_{PRM}.csv`
2. **Preprocessing** : Nettoyage + normalisation
3. **Features** : Lags (1-48h), rolling means, features temporelles
4. **Entraînement** : LSTM → `models/saved/lstm_energy_forecast_latest_{PRM}.h5`
5. **Prédictions** : 3 ans avec moyennes climatiques
6. **Visualisation** : Dashboard Streamlit

---

## 🔧 Modèle LSTM

### Architecture
- **Input** : 48h × 13 features
- **LSTM** : 2 couches (128 → 64 units)
- **Dropout** : 0.2
- **Output** : Prédiction 1h

### Features
- **Temporelles** : heure, jour, mois, weekend
- **Historiques** : lags, rolling means
- **Météo** : température, humidité
- **Interactions** : température × heure

---

## 📁 Fichiers Par Site

Pour le PRM `30000540191777` :

```
data/processed/
  └── data_preprocessed_30000540191777.csv
data/raw/meteo/
  └── meteo_moyennes_3ans_30000540191777.csv
models/saved/
  ├── lstm_energy_forecast_latest_30000540191777.h5
  ├── scalers_latest_30000540191777.pkl
  └── config_latest_30000540191777.json
data/predictions/
  ├── predictions_longterm_3ans_30000540191777.csv
  └── predictions_longterm_3ans_30000540191777_stats.txt
```

---

## 📖 Documentation

- **[QUICK_START.md](QUICK_START.md)** - Démarrage rapide
- **[GUIDE_PREDICTIONS_LONGTERM.md](GUIDE_PREDICTIONS_LONGTERM.md)** - Guide prédictions
- **[DASHBOARD_GUIDE.md](DASHBOARD_GUIDE.md)** - Guide dashboard
- **[WORKFLOW_MULTI_SITES.md](WORKFLOW_MULTI_SITES.md)** - Workflow multi-sites
- **[DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md)** - Architecture données

---

## ⚠️ Notes

- **Prédictions long terme** : Basées sur moyennes climatiques (indicatives)
- **Fenêtre minimum** : 48h d'historique requis
- **Fichiers PRM** : Tous incluent le PRM pour traçabilité
- **Dashboard** : Détecte automatiquement tous les sites

---

**Version** : 2.0 - Multi-Sites
**Mise à jour** : Février 2026
