# Projet de Prédiction de Consommation Énergétique

Modèle LSTM pour la prédiction horaire de consommation énergétique avec 48h de fenêtre glissante.

## 🏗️ Structure du Projet

```
Modeles_TimesSeries/
├── config/
│   └── config.yaml              # Configuration centralisée
├── data/
│   ├── raw/                     # Données brutes
│   ├── processed/               # Données prétraitées
│   └── predictions/             # Prédictions sauvegardées
├── models/
│   └── saved/                   # Modèles entraînés
├── src/
│   ├── __init__.py
│   ├── preprocessing.py         # Nettoyage et conversion
│   ├── feature_engineering.py  # Création des features
│   ├── model.py                # Architecture LSTM
│   ├── train.py                # Entraînement
│   ├── predict.py              # Prédiction itérative
│   └── utils.py                # Fonctions utilitaires
├── notebooks/                   # Notebooks d'exploration
├── main.py                      # Point d'entrée CLI
└── requirements.txt             # Dépendances
```

## 🚀 Installation

```bash
pip install -r requirements.txt
```

## 📊 Utilisation

### Entraînement

```bash
# Pipeline complet
python main.py train --data dataFE_prm_30000250086126.csv

# Sans preprocessing/features (déjà fait)
python main.py train --data data/processed/data_with_features.csv --skip-preprocessing --skip-features
```

### Prédiction

```bash
python main.py predict \
    --historique data/raw/historique_48h.csv \
    --meteo data/raw/meteo_15jours.csv \
    --horizon 360
```

## 🧠 Architecture du Modèle

- **Bidirectional LSTM** (96 unités)
- **LSTM** (48 unités)
- **LSTM** (24 unités)
- **Dense** (16 unités)
- **Dense** (1 unité) - sortie

**Hyperparamètres optimaux:**
- Window: 48h
- Dropout: 0.25
- L2 Reg: 0.005
- Learning Rate: 0.0005
- Batch Size: 64

## 📈 Performances

- **MAE**: 41.30 kW
- **R²**: 0.8953
- **MAPE**: 36.40%

## 🔑 Features (14 sélectionnées)

- Temporelles cycliques: `jour_sin`, `heure_sin`, `jour_cos`, `heure_cos`, `jour_ferie`
- Météo: `temperature`, `humidite`
- Historiques: `puissance_lag_1`, `puissance_roll_12`, `puissance_std_24`, `puissance_max_24`
- Interactions: `temp_x_heure_sin`, `temp_x_heure_cos`

## 📝 Notes

- Besoin d'au moins **48h d'historique** pour les prédictions
- Les prédictions utilisent un **processus itératif** : chaque prédiction alimente les features de la suivante
- Les valeurs négatives sont automatiquement clippées à 0
