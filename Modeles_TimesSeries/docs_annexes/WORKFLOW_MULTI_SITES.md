# 🎯 Workflow Multi-Sites : Prédictions → Dashboard

## ✅ Ce qui a été modifié

### 1. Commande `predict-longterm` simplifiée
**Avant** :
```bash
python main.py predict-longterm --historique data/processed/data_preprocessed_30000540191777.csv --years 3
```

**Maintenant** :
```bash
python main.py predict-longterm --prm 30000540191777 --years 3
```

Le script construit **automatiquement** les chemins vers :
- Historique : `data/processed/data_preprocessed_{prm}.csv`
- Modèle : `models/saved/lstm_energy_forecast_latest_lstm_energy_forecast_{prm}.h5`
- Sortie : `data/predictions/predictions_longterm_3ans_{prm}.csv`

### 2. Nouveau script `generate_all_predictions.py`
Génère les prédictions pour **tous les sites** en une seule commande :
```bash
python generate_all_predictions.py
```

### 3. Dashboard multi-sites
Le dashboard détecte automatiquement tous les fichiers de prédictions et affiche un menu déroulant pour sélectionner le site.

---

## 🚀 Workflow Complet

### Étape 1 : Lister vos sites
```bash
python main.py list-sites
```

### Étape 2 : Générer les prédictions

**Option A : Site par site**
```bash
python main.py predict-longterm --prm 30000540191777 --years 3 --add-trend
python main.py predict-longterm --prm 30000650805048 --years 3 --add-trend
python main.py predict-longterm --prm 30000651139165 --years 3 --add-trend
...
```

**Option B : Tous les sites en une fois (Recommandé)**
```bash
python generate_all_predictions.py
```

### Étape 3 : Visualiser dans le dashboard
```bash
streamlit run dashboard_longterm.py
```

Le dashboard :
1. Détecte automatiquement tous les fichiers `predictions_longterm_*_{prm}.csv`
2. Affiche un menu déroulant pour sélectionner le site
3. Charge les données du site sélectionné
4. Affiche les graphiques et statistiques

---

## 📂 Structure des fichiers générés

```
data/
  predictions/
    predictions_longterm_3ans_30000540191777.csv      # Prédictions site 1
    predictions_longterm_3ans_30000540191777_stats.txt
    predictions_longterm_3ans_30000650805048.csv      # Prédictions site 2
    predictions_longterm_3ans_30000650805048_stats.txt
    predictions_longterm_3ans_30000651139165.csv      # Prédictions site 3
    predictions_longterm_3ans_30000651139165_stats.txt
    ...
```

Chaque fichier contient le **PRM** dans son nom pour faciliter l'identification.

---

## 🔍 Vérifications automatiques

Quand vous lancez `predict-longterm --prm XXXXX`, le script vérifie :

✅ **Historique existe** : `data/processed/data_preprocessed_{prm}.csv`
- Si absent → message d'erreur avec suggestion : `python main.py train --prm {prm}`

✅ **Modèle existe** : `models/saved/lstm_energy_forecast_latest_lstm_energy_forecast_{prm}.h5`
- Si absent → message d'erreur avec suggestion : `python main.py train --prm {prm}`

---

## 💡 Exemples

### Générer pour un nouveau site
```bash
# 1. Entraîner le modèle
python main.py train --prm 30000651332664

# 2. Générer les prédictions
python main.py predict-longterm --prm 30000651332664 --years 3 --add-trend

# 3. Visualiser
streamlit run dashboard_longterm.py
# → Sélectionnez le site 30000651332664 dans le menu déroulant
```

### Régénérer pour tous les sites
```bash
# Régénérer toutes les prédictions
python generate_all_predictions.py

# Visualiser
streamlit run dashboard_longterm.py
```

---

## ❓ Aide et Documentation

- **Guide complet** : [`GUIDE_PREDICTIONS_LONGTERM.md`](GUIDE_PREDICTIONS_LONGTERM.md)
- **Dashboard** : [`DASHBOARD_GUIDE.md`](DASHBOARD_GUIDE.md)
- **Architecture** : [`DATA_ARCHITECTURE.md`](DATA_ARCHITECTURE.md)
- **Quick Start** : [`QUICK_START.md`](QUICK_START.md)

---

## 🎉 Avantages de la nouvelle approche

✅ **Plus simple** : Juste le PRM, pas de chemins compliqués
✅ **Plus sûr** : Vérifications automatiques des fichiers
✅ **Multi-sites** : Dashboard avec sélection de site
✅ **Traçabilité** : PRM dans les noms de fichiers
✅ **Batch** : Script pour tous les sites en une fois
