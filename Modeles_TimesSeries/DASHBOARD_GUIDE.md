# 📊 Guide du Dashboard Long Terme

## Vue d'ensemble

Le dashboard `dashboard_longterm.py` est un outil interactif de visualisation des prédictions énergétiques à long terme (3 ans), avec comparaison des données historiques.

## 🚀 Lancement Rapide

```bash
# 1. Installer les dépendances
pip install streamlit plotly

# 2. Générer les prédictions pour un site
python main.py predict-longterm --prm 30000540191777 --years 3 --add-trend

# OU générer pour tous les sites
python generate_all_predictions.py

# 3. Lancer le dashboard
streamlit run dashboard_longterm.py
```

Le dashboard s'ouvre automatiquement dans votre navigateur sur http://localhost:8501

### 🔍 Sélection du site

Le dashboard détecte automatiquement tous les sites avec des prédictions disponibles dans `data/predictions/`.
Utilisez le menu déroulant en haut à gauche pour **sélectionner le site** que vous souhaitez visualiser.

## 📋 Fonctionnalités Principales

### 🤖 Section 1 : Qualité du Modèle

**Pour non-initiés** : Cette section explique si le modèle est fiable avec :
- **MAE (Erreur Moyenne)** : L'écart moyen entre prédiction et réalité
- **RMSE (Écart-type)** : Pénalise les grosses erreurs
- **R² (Coefficient)** : % de variations expliquées (0.94 = excellent !)
- **MAPE (% Erreur)** : Erreur en pourcentage

✅ **Votre modèle actuel** :
- R² = 0.9430 → **EXCELLENT** (explique 94% des variations)
- MAE = 32.44 kW → **EXCELLENT** (erreur moyenne très faible)
- RMSE = 43.45 kW → **EXCELLENT**
- MAPE = 30.54% → **BON** (acceptable pour ce type de données)

**Cliquez sur "Comprendre ces métriques"** pour des explications détaillées.

### � Section 2 : Pilotage Budgétaire

**Analyse complète des coûts d'achat d'électricité** selon votre stratégie de couverture contractuelle (Base/Peak) et les achats complémentaires sur le marché spot.

#### Configuration des paramètres

Dans la sidebar, définissez :
- **Volumes Base** (kW) : Volume contractuel permanent (24h/24, 7j/7)
- **Volumes Peak** (kW) : Volume contractuel additionnel en heures pleines (8h-20h, lundi-vendredi)
- **Prix Base** (€/MWh) : Prix contractuel pour le volume Base
- **Prix Peak** (€/MWh) : Prix contractuel pour le volume Peak
- **TURPE** (€/kWh) : Tarif d'acheminement réseau
- **Taxes** (%) : TVA et autres taxes

#### Vue d'ensemble budgétaire

**5 KPIs essentiels** :
- **Volume total** : Consommation totale prévue (MWh)
- **Coût total** : Budget électricité total (€)
- **Prix moyen** : Coût moyen au MWh (€/MWh)
- **Taux de couverture** : % de la consommation couverte par les contrats Base/Peak
- **Exposition spot** : % de la consommation achetée sur le marché spot

#### 3 onglets d'analyse

**📦 Onglet Volumes** :
- Graphique empilé : Base / Peak / Achat Spot / Vente Spot par mois
- Diagramme circulaire : Répartition globale des volumes

**💰 Onglet Coûts** :
- Graphique empilé : Coût couverture / Achat spot / Crédit vente par mois
- 3 métriques : Coût couverture (%) / Achat Spot (%) / Crédit Vente (%)

**📈 Onglet Prix** :
- Évolution prix moyen global vs prix contractuels (Base/Peak) vs prix spot
- Évolution du taux de couverture mensuel (ligne à 100% = couverture complète)

#### Export du rapport

Téléchargez un fichier CSV avec le détail mensuel :
- Volumes : consommation réelle, base, peak, spot (achat/vente)
- Coûts : total, couverture, spot (achat/vente)
- Prix : moyens (global, spot) et taux de couverture

### 📊 Section 3 : Comparaison Historique vs Prédictions

**3 onglets de comparaison** :

1. **Évolution Annuelle**
   - Courbes historiques (🟢 vert) vs prédictions (🟠 orange)
   - Bandes min/max pour voir la dispersion
   - Tableau comparatif des moyennes par année
   - Calcul de l'évolution prévue (% de croissance)

2. **Comparaison Mensuelle**
   - Profils saisonniers : le modèle reproduit-il bien les tendances ?
   - Identification des pics de consommation (été/hiver)

3. **Profils Horaires**
   - Patterns journaliers moyens
   - Vérification des pics matin/soir

### 📈 Section 4 : Évolution Temporelle

**Visualisations détaillées** :
- **Vue Mensuelle** : Moyennes, max, min par mois
- **Vue Hebdomadaire** : Tendances semaine par semaine
- **Vue Horaire** : Profils par heure pour chaque année

🟢 **Historique** = trait plein vert
🟠 **Prédictions** = trait pointillé orange

### 📊 Section 5 : Comparaison par Année

- **Tableaux détaillés** : Statistiques séparées historique/prédictions
- **Graphiques barres** : Comparaison visuelle des moyennes
- **Croissance annuelle** : % d'évolution année par année

### 🔥 Section 6 : Analyses Avancées

**Heatmaps et distributions** :
- **Heatmap Mois × Heure** : Identifier les pics de consommation
- **Distributions** : Histogrammes et box plots par année
- **Patterns Hebdomadaires** : Jour × Heure pour voir les différences semaine/weekend

### 💾 Section 7 : Export

- **Télécharger données filtrées** : CSV avec les années sélectionnées
- **Télécharger statistiques** : Résumé des métriques par année

## ⚙️ Configuration Sidebar

### 📂 Fichier de prédictions
Le dashboard détecte automatiquement vos fichiers dans `data/predictions/`

**Note** : Le fichier s'appelle `predictions_longterm_2ans.csv` à cause d'un bug de calcul corrigé.
Le fichier contient bien **3 ans** de prédictions (26,280 heures = 1,095 jours).

### 📚 Données Historiques
- ✅ **Cochez "Charger les données historiques"** pour activer la comparaison
- Par défaut : `dataFE_prm_30000250086126.csv`
- Le dashboard fusionne automatiquement historique + prédictions
- Distinction visuelle : 🟢 Historique | 🟠 Prédictions

### 💰 Module Budgétaire
- ✅ **Cochez "Activer module budgétaire"** pour afficher l'analyse des coûts
- **Charger fichier prix spot** : CSV avec colonnes `datetime` et `prix_spot_eur_mwh`
- **Paramètres de couverture** :
  - Volumes Base/Peak (kW)
  - Prix Base/Peak (€/MWh)
  - TURPE (€/kWh) : Tarif d'acheminement
  - Taxes (%) : TVA et autres taxes

💡 **Info heures Peak** : Lundi-Vendredi 8h-20h (autres heures = Base)

### 🔍 Filtres
- **Années à afficher** : Sélectionnez les années à analyser
- Par défaut : toutes les années disponibles

### 📈 Statistiques générales
- **Prédictions** : Période, nombre d'heures, jours
- **Historique** : Même détail si chargé
- **Global** : Total des années couvertes

## 🎯 Cas d'Usage

### 1. Vérifier la qualité du modèle
**Question** : "Mon modèle est-il fiable ?"

👉 Regardez la **Section 1** (Qualité du Modèle)
- R² > 0.90 = Excellent
- MAE < 40 kW = Excellent
- Lisez les explications détaillées

### 2. Analyser les coûts budgétaires
**Question** : "Combien va me coûter l'électricité avec ma stratégie de couverture ?"

👉 Activez le **Module Budgétaire** (Section 2)
1. Chargez un fichier de prix spot
2. Configurez vos volumes/prix contractuels Base/Peak
3. Définissez TURPE et taxes
4. Consultez les 5 KPIs globaux
5. Explorez les 3 onglets (Volumes, Coûts, Prix)
6. Exportez le rapport mensuel

**Exemple d'analyse** :
- Taux de couverture = 85% → 15% de la consommation est achetée au spot
- Si exposition spot > 20% → envisager d'augmenter les volumes contractuels
- Si crédit vente important → volume contractuel trop élevé

### 3. Comparer historique et prédictions
**Question** : "Les prédictions sont-elles cohérentes avec le passé ?"

👉 Regardez la **Section 3** (Comparaison)
- **Onglet Évolution Annuelle** : Les courbes se prolongent-elles logiquement ?
- **Onglet Mensuelle** : Les patterns saisonniers sont-ils respectés ?
- **Onglet Horaire** : Les pics journaliers sont-ils similaires ?

### 4. Identifier les tendances
**Question** : "Ma consommation va-t-elle augmenter ou diminuer ?"

👉 Regardez la **Section 5** (Comparaison par Année)
- Tableau "Croissance annuelle" : % d'évolution
- Graphique barres : Visualisation immédiate

### 5. Analyser les pics
**Question** : "Quand sont mes pics de consommation ?"

👉 Regardez la **Section 6** (Analyses Avancées)
- **Heatmap Mois × Heure** : Zones rouges = pics
- **Patterns Hebdomadaires** : Différences semaine/weekend

### 6. Planifier le budget
**Question** : "Combien d'énergie vais-je consommer l'an prochain ?"

👉 Regardez :
- **Section 1 - Métriques Clés** : Énergie totale (MWh)
- **Section 5 - Statistiques détaillées** : Énergie par année
- **Section 2 - Module Budgétaire** : Coûts détaillés avec stratégie contractuelle
- Exportez les données pour vos calculs Excel

## 💡 Conseils d'Interprétation

### ✅ Points positifs de votre modèle
- **R² = 0.9430** : Le modèle capture 94% des variations → très fiable
- **MAE = 32.44 kW** : Erreur moyenne faible
- **Données depuis 2023** : 3+ années d'historique pour validation

### ⚠️ Limitations à connaître

1. **Moyennes climatiques**
   - Les prédictions utilisent des **moyennes mensuelles** de météo
   - ❌ Ne capturent pas : canicules, vagues de froid, événements exceptionnels
   - ✅ Fiables pour : tendances globales, planification annuelle

2. **Précision par horizon**
   - Court terme (< 15 jours) : ⭐⭐⭐⭐⭐ (avec vraies prévisions météo)
   - Moyen terme (1-3 mois) : ⭐⭐⭐⭐
   - Long terme (1-3 ans) : ⭐⭐⭐ (tendances indicatives)

3. **Métriques calculées sur test**
   - Les métriques (MAE, R², etc.) sont calculées sur données de **test avec vraie météo**
   - Les prédictions long terme auront une **marge d'erreur supérieure**

### 🎯 Recommandations

**Pour des décisions stratégiques** :
- ✅ Utilisez les **tendances annuelles** (fiables)
- ✅ Identifiez les **patterns saisonniers** (fiables)
- ✅ Planifiez les **budgets annuels** (fiables)

**Pour des décisions opérationnelles** :
- ⚠️ Ne vous fiez pas aux **valeurs horaires exactes**
- ⚠️ Ajoutez une **marge de sécurité** (±15-20%)
- ✅ Utilisez plutôt les **prédictions court terme** (15 jours)

## 🔧 Personnalisation

### Modifier le fichier historique par défaut
Dans le code, ligne ~75 :
```python
hist_file = st.sidebar.text_input(
    "Fichier historique",
    value="VOTRE_FICHIER.csv"  # ← Modifiez ici
)
```

### Ajouter des années au filtre
Les années sont détectées automatiquement dans les données.
Pour afficher uniquement certaines années par défaut, modifiez ligne ~95 :
```python
annees_selectionnees = st.sidebar.multiselect(
    "Années à afficher",
    annees_disponibles,
    default=[2025, 2026, 2027]  # ← Spécifiez les années
)
```

### Changer les couleurs
- 🟢 Historique : `#2ca02c` (vert)
- 🟠 Prédictions : `#ff7f0e` (orange)

Modifiez dans le code les valeurs `color = '#2ca02c'` etc.

## 📞 Support

**Problèmes fréquents** :

1. **"Aucun fichier de prédictions trouvé"**
   - Lancez d'abord : `python main.py predict-longterm --prm XXXXX --years 3`

2. **"Fichier historique introuvable"**
   - Vérifiez le chemin dans la sidebar
   - Assurez-vous que le fichier est dans le dossier Modeles_TimesSeries

3. **"Données vides ou erreur de chargement"**
   - Vérifiez que le CSV contient bien une colonne `datetime`
   - Pour l'historique : doit avoir `puissance_moy_heure` ou `puissance`

4. **"Le dashboard est lent"**
   - Normal avec 3 ans de données (26,000+ lignes)
   - Réduisez le nombre d'années affichées dans les filtres

## 🎉 Résumé

Le dashboard vous permet de :
- ✅ **Vérifier** la qualité de votre modèle (pour non-initiés)
- ✅ **Comparer** historique et prédictions (cohérence)
- ✅ **Identifier** les tendances d'évolution (croissance)
- ✅ **Analyser** les patterns de consommation (pics, saisonnalité)
- ✅ **Exporter** les données pour analyses externes

Bon dashboard ! 📊✨
