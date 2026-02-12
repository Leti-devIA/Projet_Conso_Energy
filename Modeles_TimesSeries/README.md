# Projet de Prédiction de Consommation Énergétique

Modèle LSTM pour la prédiction horaire de consommation énergétique avec 48h de fenêtre glissante.

## � Nouveautés - Architecture Multi-Sites

- ✅ **Support multi-sites** : Entraînez des modèles pour plusieurs sites (PRM) automatiquement
- ✅ **DataLoader modulaire** : Architecture flexible pour CSV (actuel) et base de données (futur)
- ✅ **Organisation améliorée** : Structure `data/raw` avec sous-dossiers (sites, meteo, prix)
- ✅ **Migration facile** : Script de migration pour organiser vos fichiers existants

📖 **Documentation complète** : Voir [DATA_ARCHITECTURE.md](DATA_ARCHITECTURE.md)

## 🏗️ Structure du Projet

```
Modeles_TimesSeries/
├── config/
│   └── config.yaml              # Configuration centralisée
├── data/
│   ├── raw/                     # 🆕 Données brutes organisées
│   │   ├── sites/              # Fichiers dataclean_prm_*.csv
│   │   ├── meteo/              # Fichiers météo
│   │   └── prix/               # Fichiers prix spot
│   ├── processed/               # Données prétraitées
│   └── predictions/             # Prédictions sauvegardées
├── models/
│   └── saved/                   # Modèles entraînés (par site)
├── src/
│   ├── __init__.py
│   ├── data_loader.py          # 🆕 Chargement des données (CSV/DB)
│   ├── preprocessing.py         # Nettoyage et conversion
│   ├── feature_engineering.py  # Création des features
│   ├── model.py                # Architecture LSTM
│   ├── train.py                # Entraînement
│   ├── predict.py              # Prédiction itérative
│   └── utils.py                # Fonctions utilitaires
├── notebooks/                   # Notebooks d'exploration
├── main.py                      # Point d'entrée CLI
├── migrate_data.py             # 🆕 Script de migration des données
├── DATA_ARCHITECTURE.md        # 🆕 Documentation architecture
└── requirements.txt             # Dépendances
```

## 🚀 Installation

```bash
pip install -r requirements.txt
```

## 📂 Préparation des Données

### Option 1 : Migration automatique (recommandé)

Si vous avez déjà des fichiers CSV dans `../data/dataclean/` :

```bash
python migrate_data.py
```

Ce script copiera automatiquement vos fichiers dans la nouvelle structure.

### Option 2 : Copie manuelle

Copiez vos fichiers dans la nouvelle structure :

```bash
# Sites (fichiers dataclean_prm_*.csv)
cp ../data/dataclean/dataclean_prm_*.csv data/raw/sites/

# Météo
cp ../data/dataclean/previsions_meteo.csv data/raw/meteo/

# Prix
cp ../data/dataclean/prix_spot.csv data/raw/prix/
```

### Vérification

```bash
python main.py list-sites
```

## 📊 Utilisation

### Lister les sites disponibles

```bash
python main.py list-sites
```

### Entraînement

```bash
# Entraîner un site spécifique
python main.py train --prm 30000250086126

# Entraîner tous les sites disponibles
python main.py train --all-sites

# Sans preprocessing/features (déjà fait)
python main.py train --prm 30000250086126 --skip-preprocessing --skip-features
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
