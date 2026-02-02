# Guide d'utilisation pour les prédictions long terme (3 ans)

## 🎯 Objectif

Prédire la consommation énergétique sur **3 ans** en utilisant des **moyennes climatiques** calculées depuis l'historique.

⚠️ **IMPORTANT** : Ces prédictions sont moins précises que celles à court terme car elles utilisent des moyennes au lieu de vraies prévisions météo.

---

## 📋 Prérequis

1. **Modèle entraîné** : Avoir un modèle LSTM déjà entraîné dans `models/saved/`
2. **Historique complet** : Fichier CSV avec au moins 1 an d'historique (idéalement 2-3 ans)
3. **Dépendances installées** : `pip install -r requirements.txt`

---

## 🚀 Utilisation

### Option 1 : Via ligne de commande (Recommandé)

```bash
python main.py predict-longterm \
    --historique dataFE_prm_30000250086126.csv \
    --years 3 \
    --add-trend
```

**Arguments disponibles** :
- `--historique` : Chemin vers le fichier historique complet (REQUIS)
- `--years` : Nombre d'années à prédire (défaut: 3)
- `--batch-size` : Taille des batchs (défaut: 1000)
- `--add-trend` : Ajoute une tendance de croissance de 1%/an
- `--output` : Chemin du fichier de sortie (optionnel)
- `--model-dir` : Répertoire des modèles (défaut: models/saved)
- `--config` : Chemin vers config.yaml

### Option 2 : Via script Python

```python
from src.predict_longterm import predict_longterm, save_longterm_predictions

# Prédire 3 ans
predictions_3ans = predict_longterm(
    historique_path="dataFE_prm_30000250086126.csv",
    nb_annees=3,
    batch_size=1000,
    add_trend=True
)

# Sauvegarder
output_path = save_longterm_predictions(predictions_3ans)
print(f"Prédictions sauvegardées : {output_path}")
```

---

## 📊 Fichiers générés

### 1. `predictions_longterm_3ans.csv`
Contient toutes les prédictions horaires :
- `datetime` : Date et heure
- `puissance_kw_pred` : Consommation prédite en kW
- `annee` : Année (pour filtrage)

### 2. `predictions_longterm_3ans_stats.txt`
Statistiques résumées :
- Période couverte
- Consommation min/max/moyenne
- Consommation moyenne par année
- Avertissements sur la précision

---

## 🔍 Comment ça marche ?

### Étape 1 : Calcul des moyennes climatiques
Le script analyse l'historique et calcule la température/humidité **moyenne** pour chaque combinaison (mois, heure).

Exemple :
- Janvier à 8h → température moyenne : 5°C
- Juillet à 14h → température moyenne : 28°C

### Étape 2 : Génération des données futures
Pour les 3 prochaines années, le script génère des données météo en :
- Utilisant les moyennes calculées
- Ajoutant une variabilité aléatoire (±30% de l'écart-type historique)
- Incluant les jours fériés français

### Étape 3 : Prédiction itérative
Le modèle prédit heure par heure en :
- Utilisant ses propres prédictions comme historique
- Créant les features nécessaires (lags, rolling)
- Appliquant une tendance de croissance (+1%/an)

### Étape 4 : Prédiction par batchs
Pour éviter les problèmes mémoire, les 26 280 heures (3 ans × 365 × 24) sont prédites par **batchs de 1000 heures**.

---

## ⚠️ Limitations et précisions

### ✅ Ce qui fonctionne bien
- Capturer les patterns saisonniers (hiver/été)
- Capturer les patterns hebdomadaires (semaine/weekend)
- Projections macro à long terme

### ❌ Limites importantes
- **Précision réduite** : MAE attendue ~60-80 kW (vs 41 kW à court terme)
- **Pas de vraie météo** : Utilise des moyennes, pas de vraies prévisions
- **Événements imprévus** : Ne peut pas prévoir canicules, vagues de froid, etc.
- **Évolution de consommation** : La tendance de +1%/an est fixe et simpliste

### 📉 Attendez-vous à :
- **R² : 0.70-0.75** (vs 0.89 à court terme)
- **MAE : 60-80 kW** (vs 41 kW à court terme)
- **MAPE : 50-60%** (vs 36% à court terme)

---

## 💡 Recommandations d'usage

### ✅ **Bon usage**
- Projections budgétaires annuelles
- Planification d'investissements
- Études de faisabilité
- Tendances macro

### ❌ **Mauvais usage**
- Pilotage opérationnel quotidien
- Achats d'énergie sur marchés spot
- Optimisation fine de production
- Prévisions contractuelles

### 🎯 **Conseil**
Pour les **15 prochains jours**, utilisez toujours la commande `predict` standard avec de vraies prévisions météo !

---

## 🔧 Personnalisation

### Modifier la tendance de croissance

Dans `src/predict_longterm.py`, ligne ~220 :
```python
croissance_annuelle = 0.01  # 1% par an → Modifiez cette valeur
```

### Ajuster la variabilité météo

Dans `src/generate_climate_averages.py`, ligne ~100 :
```python
noise = np.random.normal(0, meteo_future[col_std] * 0.3, len(meteo_future))
# Modifiez 0.3 pour plus/moins de variabilité
```

### Modifier les jours fériés

Dans `src/generate_climate_averages.py`, ligne ~145, ajoutez/retirez des dates.

---

## 📞 Support

Si les prédictions semblent aberrantes :
1. Vérifier que l'historique contient au moins 1 an de données
2. Vérifier que le modèle est bien entraîné (MAE < 50 kW)
3. Vérifier les moyennes climatiques calculées
4. Réduire `batch_size` si problèmes mémoire

---

## 📈 Exemple de résultats

```
Année 2026 : 142.5 kW (moyenne)
Année 2027 : 143.9 kW (+1.0% vs 2026)
Année 2028 : 145.3 kW (+1.0% vs 2027)

Consommation totale prédite : 3,748,000 kWh
```

---

**Date de création** : Janvier 2026  
**Version** : 1.0
