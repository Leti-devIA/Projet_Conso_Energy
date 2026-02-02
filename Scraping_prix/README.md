# Scraping Prix Électricité EEX

Module de scraping des prix de l'électricité depuis la plateforme **EEX (European Energy Exchange)** pour le marché français.

## 📋 Description

Ce projet permet de récupérer automatiquement les prix du marché de l'électricité (futures) via l'API publique d'EEX. Il collecte les données sur différentes périodes (mensuel, trimestriel, annuel) et génère un historique des prix pour les 3 prochaines années.

**Données collectées :**
- Prix Base (charge de base)
- Prix Peak (heures de pointe) - disponible dans la version v1
- Prix pour le marché français (FR)
- Périodes : mois, trimestres, années calendaires

## 🗂️ Structure du Projet

```
Scraping_prix/
├── scraping.ipynb           # Version 1 : scraper avec gestion Base + Peak
├── scrapingv02.ipynb        # Version 2 : scraper optimisé (Base uniquement)
├── prix_energie_3_ans.csv   # Données scrapées (sortie principale)
├── prix_electricite.csv     # Données historiques
├── eex_prices.csv           # Export des prix
├── eex_data.json            # Données brutes JSON
├── eex_prices.json          # Prix au format JSON
├── README.md                # Ce fichier
└── scrap_env/               # Environnement virtuel Python
```

## 🏗️ Architecture

### Classe `EEXScraper`

```
EEXScraper
│
├── API
│   ├── fetch_market_data()   # Appel API EEX
│   └── get_latest_price()    # Extraction dernier prix
│
├── Parsing métier
│   ├── parse_delivery()      # Conversion format livraison → maturity
│   ├── compute_period_dates()# Calcul dates début/fin période
│   └── format_periode_label()# Formatage étiquette en français
│
├── Construction métier
│   ├── build_price_row()     # Construction d'une ligne de prix
│   └── build_prices_table()  # Construction table complète
│
└── Mappings
    ├── SHORT_CODES           # Codes produits (F7BM, F7BQ, F7BY)
    ├── MONTHS                # Mois EN → numéro
    └── MONTHS_FR             # Traduction mois EN → FR
```

## 🚀 Installation

### 1. Créer l'environnement virtuel

```powershell
# Dans le dossier Scraping_prix
python -m venv scrap_env
.\scrap_env\Scripts\Activate.ps1
```

### 2. Installer les dépendances

```bash
pip install requests pandas
```

## 💻 Utilisation

### Méthode 1 : Via Jupyter Notebook

Ouvrir [scrapingv02.ipynb](scrapingv02.ipynb) (version recommandée) et exécuter toutes les cellules :

```python
# Le script génère automatiquement les périodes sur 3 ans
scraper = EEXScraper()
configs = generate_next_3_years_periods()
df = scraper.build_prices_table(configs)
df.to_csv("prix_energie_3_ans.csv", index=False)
```

### Méthode 2 : Script Python

```python
from scrapingv02 import EEXScraper

# Initialiser le scraper
scraper = EEXScraper()

# Récupérer un prix spécifique
row = scraper.build_price_row("Month", "March 2026")
print(f"Prix Base : {row['prix_base']} €/MWh")

# Récupérer plusieurs périodes
configs = [
    ("Month", "February 2026"),
    ("Quarter", "Q2 2026"),
    ("Year", "Cal_27")
]
df = scraper.build_prices_table(configs)
```

## 📊 Format des Données

### CSV de sortie (`prix_energie_3_ans.csv`)

| Colonne | Type | Description |
|---------|------|-------------|
| `periode` | str | Période en français (ex: "Fevrier 2026", "2eme trimestre 2026") |
| `prix_base` | float | Prix Base en €/MWh |
| `type` | str | Type de période ("mensuel", "trimestriel", "annuel") |
| `date_maj` | datetime | Date de mise à jour |
| `date_deb` | datetime | Date de début de la période de livraison |
| `date_fin` | datetime | Date de fin de la période de livraison |
| `id_prev_prix` | str | Identifiant unique (UUID) |

### Exemple de données

```csv
periode,prix_base,type,date_maj,date_deb,date_fin,id_prev_prix
Fevrier 2026,85.50,mensuel,2026-02-02 14:30:00,2026-02-01,2026-02-28,a1cfea50-71e4-4a21-8e22-fc48bb4a2f72
2eme trimestre 2026,82.30,trimestriel,2026-02-02 14:30:15,2026-04-01,2026-06-30,b2dfeb61-82f5-5b32-9f33-gd59cc5b3f83
Annee 2027,79.90,annuel,2026-02-02 14:30:30,2027-01-01,2027-12-31,c3egfc72-93g6-6c43-af44-he6add6c4g94
```

## 🔧 Paramètres API EEX

L'API EEX utilise les paramètres suivants :

| Paramètre | Valeurs | Description |
|-----------|---------|-------------|
| `shortCode` | F7BM, F7BQ, F7BY | Month, Quarter, Year |
| `commodity` | POWER | Type de commodité |
| `pricing` | F | Futures |
| `area` | FR | Zone géographique (France) |
| `product` | Base, Peak | Type de produit |
| `maturity` | YYYYMM | Code de maturité (ex: 202602) |
| `isRolling` | true | Contrat roulant |

## 📝 Formats de Livraison Supportés

### Mensuel (`Month`)
- Format : `"February 2026"`
- Génère : `shortCode=F7BM, maturity=202602`

### Trimestriel (`Quarter`)
- Format : `"Q2 2026"`
- Génère : `shortCode=F7BQ, maturity=202604` (début du trimestre)

### Annuel (`Year`)
- Format : `"Cal_27"`
- Génère : `shortCode=F7BY, maturity=202701`

## ⚡ Fonctionnalités

✅ Scraping automatique des prix EEX
✅ Support multi-périodes (mois, trimestres, années)
✅ Génération automatique des 3 prochaines années
✅ Formatage des dates et périodes en français
✅ Export CSV et JSON
✅ Gestion des erreurs et retry
✅ Anti-rate limiting (délai entre requêtes)
✅ Identifiants uniques (UUID) pour chaque enregistrement

## 🔄 Versions

### Version 1 : `scraping.ipynb`
- Support Base + Peak
- Retry mechanism
- API complète avec tous les paramètres

### Version 2 : `scrapingv02.ipynb` ⭐ (Recommandée)
- Optimisée et simplifiée
- Focus sur prix Base
- Meilleure organisation du code
- Fonction de génération automatique des périodes

## 🎯 Cas d'Usage

Ce module est utilisé dans le cadre du projet de **prévision de consommation énergétique** pour :
- Alimenter les modèles de prévision avec les prix futurs
- Analyser les tendances du marché électrique
- Intégrer les données de prix dans les dashboards
- Corrélation prix/consommation

## 📚 Dépendances

```
requests>=2.31.0
pandas>=2.0.0
```

## 🤝 Intégration

Les données scrapées sont utilisées par :
- [Modeles_TimesSeries](../Modeles_TimesSeries/) : modèles de prévision LSTM
- [enedis-meteo-api](../enedis-meteo-api/) : API de prévision
- [database_dataclean](../database_dataclean/) : stockage en base de données

## 📅 Mise à Jour

Les prix sont mis à jour quotidiennement sur EEX. Il est recommandé d'exécuter le scraper :
- **Quotidiennement** pour suivre l'évolution des prix
- **Après 16h CET** pour avoir les prix de settlement du jour

## ⚠️ Notes Importantes

- L'API EEX est publique mais pensez à respecter les limites de taux
- Un délai de 0.5s entre requêtes est appliqué par défaut
- Les prix sont en €/MWh
- Les dates sont au format ISO 8601

## 📞 Contact

Projet : **Prévision Consommation Énergétique**
Module : **Scraping Prix Électricité**
Date : Février 2026
