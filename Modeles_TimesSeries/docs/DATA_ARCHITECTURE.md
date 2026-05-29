# Architecture des données

Ce document décrit la circulation des données telle qu'elle est utilisée aujourd'hui dans le projet.

## 1) Répertoires de données

```text
Modeles_TimesSeries/data/
├── raw/
│   ├── sites/      (dataclean_prm_<prm>.csv, table_sites.csv)
│   ├── meteo/      (meteo_horaire_<prm>.csv, meteo_horaire_1ans.csv)
│   ├── prix/       (prix_spot.csv)
│   └── achats/     (ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv)
├── processed/      (data_processed_<prm>.csv, data_features_<prm>.csv)
└── predictions/    (prophet_predictions_<prm>.csv, ...)
```

## 2) Sources et points d'entrée

### API Dataclean

- Expose les historiques PRM et référentiels via HTTP.
- Endpoints utilisés côté projet :
  - `/dataclean/allbyprm` (CSV)
  - `/dataclean/allbyprm-json` (JSON)
  - `/dataclean/previsions-meteo`
  - `/dataclean/sites`
  - `/dataclean/prixspot`

### Fichiers locaux

Le projet s'appuie aussi sur des fichiers déposés localement dans `data/raw/` (météo, prix, achats, historiques PRM).

## 3) Chargement des données (module `src/data_loader.py`)

Le loader CSV gère :

- historiques sites : `data/raw/sites/dataclean_prm_<prm>.csv`
- table des sites : `data/raw/sites/table_sites.csv`
- météo : `data/raw/meteo/previsions_meteo.csv`, `meteo.csv` ou `meteo_horaire_<prm>.csv`
- prix : `data/raw/prix/prix_spot.csv`

Fonctions clés :

- `load_dataclean(...)`
- `load_meteo_data(...)`
- `load_prix_data(...)`
- `load_processed_site_data(...)`
- `load_predictions(...)`

## 4) Pipeline de transformation

```text
raw/sites + raw/meteo + raw/prix
              │
              ▼
       preprocessing.py
              │
              ▼
   feature_engineering.py
              │
              ├── data/processed/data_processed_<prm>.csv
              └── data/processed/data_features_<prm>.csv
```

Ensuite :

- `train.py` lit les données enrichies et entraîne Prophet.
- `predict.py` produit les sorties de prévision dans `data/predictions/`.

## 5) Contrats de fichiers (niveau projet)

### Historique site

Nom attendu : `dataclean_prm_<prm>.csv`

Colonnes courantes exploitées par le pipeline :

- `datetime`
- `puissance_moy_heure` (cible)
- variables météo (ex: `temperature`, `humidite`, `vitesse_vent`, `couverture_nuages`)

### Météo future

Fichiers météo utilisés pour la prédiction (colonnes attendues selon disponibilité) :

- `datetime`
- `temperature`
- `humidite`
- `vitesse_vent`
- `couverture_nuages`
- `precipitation` (optionnelle)

### Prix spot

Nom attendu : `prix_spot.csv`.

Utilisé dans le dashboard et les calculs de coût d'approvisionnement.

## 6) Schéma de flux des données

```text
API Dataclean / CSV locaux
          │
          ▼
      data/raw/
          │
          ▼
 preprocessing + features
          │
          ▼
    data/processed/
          │
          ├── train.py   -> models/saved/
          └── predict.py -> data/predictions/
```

## 7) Vérifications recommandées

- Cohérence du PRM entre nom de fichier et contenu.
- Présence de `datetime` et de la colonne cible `puissance_moy_heure`.
- Fréquence temporelle cohérente avant entraînement.
- Disponibilité des colonnes météo nécessaires aux régressions Prophet.
