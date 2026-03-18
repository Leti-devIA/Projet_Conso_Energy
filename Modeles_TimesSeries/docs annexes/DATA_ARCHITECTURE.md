# Architecture de Chargement des Données

Ce document explique la nouvelle architecture mise en place pour gérer le chargement des données avec support CSV (actuel) et préparation pour base de données (futur).

## 📁 Structure des Dossiers

```
Modeles_TimesSeries/
├── data/
│   ├── raw/                    # Données brutes
│   │   ├── sites/             # Données de consommation par site
│   │   │   ├── dataclean_prm_30000250086126.csv
│   │   │   ├── dataclean_prm_30000260159032.csv
│   │   │   └── dataclean_prm_30000540185031.csv
│   │   ├── meteo/             # Données météorologiques
│   │   │   └── previsions_meteo.csv
│   │   └── prix/              # Prix spot de l'électricité
│   │       └── prix_spot.csv
│   ├── processed/             # Données traitées
│   └── predictions/           # Prédictions sauvegardées
├── src/
│   ├── data_loader.py         # 🆕 Module de chargement des données
│   ├── preprocessing.py       # Preprocessing
│   ├── feature_engineering.py # Feature engineering
│   ├── train.py              # Entraînement
│   └── ...
└── config/
    └── config.yaml           # Configuration
```

## 🏗️ Architecture du DataLoader

Le module `data_loader.py` fournit une architecture flexible avec :

### 1. Classe Abstraite `DataLoader`
Interface commune pour tous les loaders, définissant les méthodes :
- `load_site_data()` : Charger les données de consommation
- `load_meteo_data()` : Charger les données météo
- `load_prix_data()` : Charger les prix spot
- `list_available_sites()` : Lister les sites disponibles

### 2. `CSVDataLoader` (Actuel)
Implémentation pour fichiers CSV :
- Scanne automatiquement les fichiers dans `data/raw/sites/`
- Détecte les PRMs depuis les noms de fichiers
- Peut charger un site spécifique ou tous les sites
- Filtre par dates si nécessaire

### 3. `DatabaseDataLoader` (Futur)
Stub préparé pour la future connexion à une base de données :
- Interface identique au CSVDataLoader
- TODO: Implémenter les requêtes SQL
- TODO: Gérer la connexion à la base de données

### 4. Factory Function `get_data_loader()`
Permet de sélectionner le bon loader :
```python
loader = get_data_loader('csv')  # ou 'database'
```

## 🚀 Utilisation

### Lister les sites disponibles

```bash
python main.py list-sites
```

### Entraîner sur un site spécifique

```bash
python main.py train --prm 30000250086126
```

### Entraîner sur tous les sites

```bash
python main.py train --all-sites
```

### Utilisation dans le code

```python
from data_loader import get_data_loader

# Créer le loader
loader = get_data_loader('csv')

# Lister les sites
sites = loader.list_available_sites()
# Retourne: ['30000250086126', '30000260159032', '30000540185031']

# Charger un site spécifique
df = loader.load_site_data(prm='30000250086126')

# Charger tous les sites
df_all = loader.load_site_data()  # prm=None charge tous les sites

# Charger avec filtre de dates
df = loader.load_site_data(
    prm='30000250086126',
    start_date='2023-01-01',
    end_date='2023-12-31'
)

# Charger données météo
df_meteo = loader.load_meteo_data()

# Charger prix spot
df_prix = loader.load_prix_data()
```

## ⚙️ Configuration

Dans `config/config.yaml` :

```yaml
# Source des données ('csv' ou 'database')
data_source: "csv"

# Chemins des données
data:
  raw: "data/raw"
  processed: "data/processed"
  predictions: "data/predictions"

# Configuration pour la base de données (FUTURE)
# database:
#   host: "localhost"
#   port: 5432
#   name: "energy_db"
#   user: "user"
#   password: "password"

# Sites à traiter (vide = tous)
sites:
  prms: []  # ou ["30000250086126", "30000260159032"]
```

## 📊 Format des Fichiers CSV

### Fichiers de sites
Format : `dataclean_prm_XXXXXXXXXXXXX.csv`

Colonnes attendues :
- `datetime` : Date et heure (ISO format)
- `puissance_moy_heure` : Puissance moyenne horaire (Wh)
- Autres colonnes : température, humidité, etc.

### Fichiers météo
Format : `previsions_meteo.csv` ou `meteo.csv`

Colonnes attendues :
- `datetime` : Date et heure
- `temperature` : Température (°C)
- `humidite` : Humidité (%)
- `vitesse_vent` : Vitesse du vent
- `couverture_nuages` : Couverture nuageuse

## 🔄 Migration vers Base de Données

Quand vous serez prêt à migrer vers une base de données :

1. **Implémenter DatabaseDataLoader** dans `data_loader.py` :
   ```python
   def load_site_data(self, prm=None, start_date=None, end_date=None):
       # Connexion à la DB
       # Requête SQL
       # Retourner DataFrame
   ```

2. **Configurer la connexion** dans `config.yaml` :
   ```yaml
   data_source: "database"
   database:
     host: "localhost"
     port: 5432
     name: "energy_db"
   ```

3. **Aucun changement nécessaire** dans le reste du code !
   L'interface abstraite garantit la compatibilité.

## 🎯 Avantages de cette Architecture

✅ **Flexibilité** : Changement de source facile (CSV ↔ Database)
✅ **Multi-sites** : Traite plusieurs sites automatiquement
✅ **Isolation** : La logique de chargement est séparée du reste
✅ **Maintenance** : Code plus propre et modulaire
✅ **Évolutivité** : Prêt pour la migration DB
✅ **Testabilité** : Chaque loader peut être testé indépendamment

## 📝 Exemples Complets

### Exemple 1 : Entraîner tous les sites automatiquement

```bash
# Copier vos fichiers CSV dans data/raw/sites/
cp ../data/dataclean/dataclean_prm_*.csv data/raw/sites/

# Lister les sites détectés
python main.py list-sites

# Entraîner tous les sites
python main.py train --all-sites
```

Chaque site aura son propre modèle sauvegardé avec le PRM dans le nom.

### Exemple 2 : Workflow complet pour un site

```bash
# 1. Lister les sites
python main.py list-sites

# 2. Entraîner un site spécifique
python main.py train --prm 30000250086126

# 3. Le modèle est sauvegardé avec le PRM :
# - models/saved/lstm_energy_forecast_20260212_143000_30000250086126.h5
# - models/saved/scalers_20260212_143000_30000250086126.pkl
# - models/saved/config_20260212_143000_30000250086126.json
```

### Exemple 3 : Utiliser le DataLoader dans un script custom

```python
from data_loader import get_data_loader
import pandas as pd

# Créer le loader
loader = get_data_loader('csv', config_path='config/config.yaml')

# Charger plusieurs sites pour analyse
sites = ['30000250086126', '30000260159032']
for prm in sites:
    df = loader.load_site_data(prm=prm)
    print(f"Site {prm}: {len(df)} lignes, consommation moyenne: {df['puissance_moy_heure'].mean():.2f} Wh")

# Combiner avec données météo
df_meteo = loader.load_meteo_data()
df_site = loader.load_site_data(prm='30000250086126')
df_merged = pd.merge(df_site, df_meteo, on='datetime', how='inner')
```

## 🐛 Troubleshooting

### Erreur : "Aucun fichier de site trouvé"
- Vérifiez que les fichiers sont dans `data/raw/sites/`
- Format attendu : `dataclean_prm_XXXXX.csv`

### Erreur : "Features manquantes"
- Assurez-vous que les colonnes requises sont présentes
- Vérifiez que la colonne `datetime` existe
- La colonne `puissance_moy_heure` doit être présente

### Les sites ne sont pas détectés
```bash
# Vérifier manuellement
ls data/raw/sites/

# Lister avec Python
python -c "from src.data_loader import get_data_loader; print(get_data_loader('csv').list_available_sites())"
```
