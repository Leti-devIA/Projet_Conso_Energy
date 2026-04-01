# 📐 Formule de Calcul du Coût Horaire

## Formule complète

```
Coût_heure = volumes_achetés_futur × prix_achetés_volume_futur 
           + prix_spot × (consommation_réelle_heure - volumes_achetés_futur)
```

## Décomposition

### 1. Partie contractuelle (volumes achetés)
```
Coût_contractuel = volumes_achetés × prix_achetés
```

**Exemples** :
- Vous avez un contrat pour acheter 300 kW/h à 45 €/MWh
- Coût contractuel = 300 kW × 45 €/MWh / 1000 = **13.50 €/h**

### 2. Partie spot (écart)
```
Coût_écart = prix_spot × (consommation_réelle - volumes_achetés)
```

**Cas 1 : Sur-consommation** (consommation > volumes achetés)
- Consommation réelle = 350 kW
- Volumes achetés = 300 kW
- Écart = +50 kW (besoin d'acheter 50 kW supplémentaires)
- Prix spot = 70 €/MWh
- Coût écart = 70 × 50 / 1000 = **+3.50 €/h** (achat)

**Cas 2 : Sous-consommation** (consommation < volumes achetés)
- Consommation réelle = 250 kW
- Volumes achetés = 300 kW
- Écart = -50 kW (surplus de 50 kW à revendre)
- Prix spot = 70 €/MWh
- Coût écart = 70 × (-50) / 1000 = **-3.50 €/h** (revente/gain)

### 3. Coût total
```
Coût_total = Coût_contractuel + Coût_écart + Coût_acheminement + Taxes
```

## Exemples concrets

### Exemple 1 : Sur-consommation en heure de pointe

**Données** :
- Volumes achetés : 300 kW
- Prix d'achat contractuel : 45 €/MWh
- Consommation réelle : 380 kW
- Prix spot : 85 €/MWh (heure de pointe)
- TURPE : 0.05 €/kWh
- Taxes : 20%

**Calcul** :
```
Coût_contractuel = 300 × 45 / 1000 = 13.50 €
Coût_écart      = 85 × (380 - 300) / 1000 = 85 × 80 / 1000 = 6.80 €
Coût_énergie    = 13.50 + 6.80 = 20.30 €

Coût_TURPE      = 380 × 0.05 = 19.00 €
Coût_avant_taxe = 20.30 + 19.00 = 39.30 €
Taxes           = 39.30 × 0.20 = 7.86 €

COÛT TOTAL      = 39.30 + 7.86 = 47.16 €
```

### Exemple 2 : Sous-consommation en heure creuse

**Données** :
- Volumes achetés : 300 kW
- Prix d'achat contractuel : 45 €/MWh
- Consommation réelle : 200 kW
- Prix spot : 25 €/MWh (heure creuse)
- TURPE : 0.05 €/kWh
- Taxes : 20%

**Calcul** :
```
Coût_contractuel = 300 × 45 / 1000 = 13.50 €
Coût_écart      = 25 × (200 - 300) / 1000 = 25 × (-100) / 1000 = -2.50 € (gain)
Coût_énergie    = 13.50 - 2.50 = 11.00 €

Coût_TURPE      = 200 × 0.05 = 10.00 €
Coût_avant_taxe = 11.00 + 10.00 = 21.00 €
Taxes           = 21.00 × 0.20 = 4.20 €

COÛT TOTAL      = 21.00 + 4.20 = 25.20 €
```

**Note** : La revente du surplus (100 kW) au prix spot (25 €/MWh) réduit le coût global.

### Exemple 3 : Consommation = Volumes achetés

**Données** :
- Volumes achetés : 300 kW
- Prix d'achat contractuel : 45 €/MWh
- Consommation réelle : 300 kW
- Prix spot : 60 €/MWh (n'a pas d'impact)
- TURPE : 0.05 €/kWh
- Taxes : 20%

**Calcul** :
```
Coût_contractuel = 300 × 45 / 1000 = 13.50 €
Coût_écart      = 60 × (300 - 300) / 1000 = 0.00 € (pas d'écart)
Coût_énergie    = 13.50 + 0.00 = 13.50 €

Coût_TURPE      = 300 × 0.05 = 15.00 €
Coût_avant_taxe = 13.50 + 15.00 = 28.50 €
Taxes           = 28.50 × 0.20 = 5.70 €

COÛT TOTAL      = 28.50 + 5.70 = 34.20 €
```

## Stratégies d'optimisation

### 1. Arbitrage prix contractuel vs prix spot

**Situation** : Prix spot souvent < Prix contractuel

**Action** : 
- Réduire les volumes achetés
- Acheter davantage au spot
- ⚠️ Attention à la volatilité du spot

**Exemple** :
```
Prix contractuel : 45 €/MWh
Prix spot moyen : 35 €/MWh
Économie potentielle : 10 €/MWh sur volumes non contractualisés
```

### 2. Lissage de la consommation

**Situation** : Forte variabilité de la consommation

**Action** :
- Volumes achetés = consommation moyenne
- Évite les écarts importants
- Limite l'exposition au spot

**Exemple** :
```
Consommation min : 200 kW
Consommation moy : 300 kW
Consommation max : 450 kW

Option A : Acheter 300 kW (moyenne)
  → Écart moyen : ±75 kW

Option B : Acheter 450 kW (max)
  → Pas d'achat spot mais beaucoup de revente

Option C : Acheter 200 kW (min)
  → Pas de revente mais beaucoup d'achat spot
```

### 3. Couverture partielle

**Situation** : Incertitude sur la consommation future

**Action** :
- Couvrir 70-80% de la consommation prévue
- Garder de la flexibilité au spot

**Exemple** :
```
Consommation prévue : 350 kW
Volumes achetés : 280 kW (80%)
  → Exposition spot limitée à 20%
  → Bénéficie des baisses de prix spot
  → Couvert contre les hausses sur 80%
```

## Comparaison avec l'approche 100% spot

### Scénario : 1 année, consommation moyenne 350 kW

**Option A : 100% au spot (pas de contrat)**
```
Coût_énergie = consommation × prix_spot_moyen
             = 350 kW × 45 €/MWh × 8760 h / 1000
             = 137 970 €
```
✅ Avantages : Profite des baisses de prix
❌ Risques : Exposé aux hausses (peut atteindre 100-200 €/MWh)

**Option B : 80% contractuel, 20% spot**
```
Volumes achetés : 280 kW à 43 €/MWh (prix négocié)
Écart moyen spot : 70 kW à 45 €/MWh (prix moyen)

Coût_contractuel = 280 × 43 × 8760 / 1000 = 105 451 €
Coût_spot        = 70 × 45 × 8760 / 1000 = 27 594 €
Coût_total       = 133 045 €
```
✅ Avantages : Coût maîtrisé, exposition limitée
✅ Économie : 4 925 € vs 100% spot (3.6%)

**Option C : 100% contractuel**
```
Volumes achetés : 350 kW à 43 €/MWh
Consommation exacte = volumes

Coût_total = 350 × 43 × 8760 / 1000 = 131 814 €
```
✅ Avantages : Coût totalement fixe, aucune surprise
❌ Inconvénients : Pas de revente possible si sous-conso

## Implémentation dans le code

### Cas 1 : Volume fixe
```python
volumes_achetes_kw = 300  # kW constant
prix_achetes_eur_mwh = 45  # €/MWh

df_calcul = calculator.calculer_cout_avec_parametres(
    df_enrichi,
    volumes_achetes_kw=300,
    prix_achetes_eur_mwh=45,
    tarif_acheminement_eur_kwh=0.05,
    taux_taxe_pct=20.0
)
```

### Cas 2 : Volume variable (% de la conso)
```python
# 80% de la consommation prédite
volumes_achetes_kw = df_enrichi['puissance_kw_pred'] * 0.80
prix_achetes_eur_mwh = 45

df_calcul = calculator.calculer_cout_avec_parametres(
    df_enrichi,
    volumes_achetes_kw=volumes_achetes_kw,
    prix_achetes_eur_mwh=45,
    tarif_acheminement_eur_kwh=0.05,
    taux_taxe_pct=20.0
)
```

### Cas 3 : Profil horaire spécifique
```python
# Charger depuis un fichier
df_contrat = pd.read_csv('contrat_achat.csv')
# Colonnes : datetime, volume_achete_kw

# Merger avec les prédictions
df_merged = df_enrichi.merge(df_contrat, on='datetime', how='left')

df_calcul = calculator.calculer_cout_avec_parametres(
    df_merged,
    volumes_achetes_kw=df_merged['volume_achete_kw'],
    prix_achetes_eur_mwh=45,
    tarif_acheminement_eur_kwh=0.05,
    taux_taxe_pct=20.0
)
```

## Analyse des résultats

### Colonnes du DataFrame résultant

Après calcul avec volumes achetés, le DataFrame contient :

```python
df_calcul.columns
```
- `datetime` : Date/heure
- `conso_reelle_kw` : Consommation réelle (après ajustements)
- `volumes_achetes_kw` : Volumes achetés contractuels
- `prix_achetes_eur_mwh` : Prix d'achat contractuel
- `ecart_kw` : Écart = conso_réelle - volumes_achetés
- `prix_spot_eur_mwh` : Prix spot du marché
- `cout_achat_contractuel_eur` : Coût de la partie contractuelle
- `cout_ecart_spot_eur` : Coût/gain de l'écart (+ achat, - vente)
- `cout_energie_eur` : Coût total énergie (contractuel + écart)
- `cout_acheminement_eur` : Coût TURPE
- `cout_avant_taxe_eur` : Coût avant taxes
- `cout_taxe_eur` : Montant des taxes
- `cout_total_eur` : Coût total final

### KPIs clés à surveiller

```python
# 1. Taux de couverture
taux_couverture = (df_calcul['volumes_achetes_kw'].sum() / 
                   df_calcul['conso_reelle_kw'].sum() * 100)

# 2. Heures d'achat spot
nb_heures_achat = (df_calcul['ecart_kw'] > 0).sum()

# 3. Heures de revente spot
nb_heures_vente = (df_calcul['ecart_kw'] < 0).sum()

# 4. Coût moyen spot payé/reçu
cout_moyen_spot_achat = df_calcul[df_calcul['ecart_kw'] > 0]['prix_spot_eur_mwh'].mean()
prix_moyen_spot_vente = df_calcul[df_calcul['ecart_kw'] < 0]['prix_spot_eur_mwh'].mean()

# 5. Économie vs 100% spot
cout_avec_contrat = df_calcul['cout_total_eur'].sum()
cout_sans_contrat = (df_calcul['conso_reelle_kw'] * 
                     df_calcul['prix_spot_eur_mwh'] / 1000).sum()
economie = cout_sans_contrat - cout_avec_contrat
```

## Conclusion

La formule avec volumes achetés permet :
- ✅ De **maîtriser** une partie du budget (partie contractuelle)
- ✅ De **bénéficier** des baisses de prix spot (sur l'écart)
- ✅ De **se protéger** des hausses extrêmes (sur la partie couverte)
- ✅ De **revendre** en cas de sous-consommation

C'est l'approche la plus réaliste pour les entreprises qui ont des contrats d'achat d'électricité à terme.
