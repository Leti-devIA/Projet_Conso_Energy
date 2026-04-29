# Calcul du Coût Horaire de l'Énergie

## Contexte métier

Un consommateur industriel achète de l'énergie via deux canaux :

1. **Contrat à terme** : il achète à l'avance un certain volume à un prix fixé.
2. **Marché spot** : l'écart entre sa consommation réelle et son volume acheté est régularisé au prix du marché en temps réel.

La prévision de consommation est donc directement liée à un enjeu financier : mieux prévoir, c'est mieux calibrer ses achats à terme et éviter des achats spot coûteux en période de pointe.

---

## Formule complète

$$C_{heure} = V_{achetés} \times P_{achetés} + P_{spot} \times (C_{réelle} - V_{achetés})$$

Où :

| Variable | Unité | Description |
|---|---|---|
| $C_{heure}$ | € | Coût total de l'heure |
| $V_{achetés}$ | kW | Volume d'énergie acheté à terme pour cette heure |
| $P_{achetés}$ | €/MWh | Prix contractuel de l'achat à terme |
| $P_{spot}$ | €/MWh | Prix spot du marché à cette heure |
| $C_{réelle}$ | kW | Consommation réelle mesurée |

---

## Décomposition

### Partie contractuelle

$$C_{contractuelle} = V_{achetés} \times \frac{P_{achetés}}{1000}$$

Le diviseur par 1000 convertit les €/MWh en €/kWh.

### Partie spot (écart)

$$C_{spot} = P_{spot} \times \frac{C_{réelle} - V_{achetés}}{1000}$$

- Si $C_{réelle} > V_{achetés}$ → l'écart est positif → **achat spot** à un coût supplémentaire.
- Si $C_{réelle} < V_{achetés}$ → l'écart est négatif → **revente d'excédent** (gain ou coût réduit).

### Coût complet avec acheminement et taxes

$$C_{total} = (C_{contractuelle} + C_{spot} + C_{TURPE}) \times (1 + t_{taxes})$$

Où $C_{TURPE}$ représente les frais d'acheminement réseau.

---

## Exemples chiffrés

### Exemple 1 — Sur-consommation en heure de pointe

**Données :**

- Volumes achetés : 300 kW à 45 €/MWh
- Consommation réelle : 380 kW
- Prix spot : 85 €/MWh
- TURPE : 0.05 €/kWh
- Taxes : 20%

**Calcul :**

```
C_contractuelle = 300 × 45 / 1000          = 13.50 €
C_spot          = 85 × (380 - 300) / 1000  =  6.80 €   ← achat de 80 kW supplémentaires
C_énergie       = 13.50 + 6.80             = 20.30 €

C_TURPE         = 380 × 0.05               = 19.00 €
C_avant_taxes   = 20.30 + 19.00            = 39.30 €
Taxes           = 39.30 × 0.20             =  7.86 €

COÛT TOTAL      = 39.30 + 7.86             = 47.16 €
```

**Analyse :** la sur-consommation de 80 kW à 85 €/MWh (heure de pointe) coûte 6.80 € supplémentaires, soit +33% par rapport à la partie contractuelle seule.

---

### Exemple 2 — Sous-consommation en heure creuse

**Données :**

- Volumes achetés : 300 kW à 45 €/MWh
- Consommation réelle : 200 kW
- Prix spot : 25 €/MWh
- TURPE : 0.05 €/kWh
- Taxes : 20%

**Calcul :**

```
C_contractuelle = 300 × 45 / 1000           = 13.50 €
C_spot          = 25 × (200 - 300) / 1000   = -2.50 €  ← revente de 100 kW (gain)
C_énergie       = 13.50 - 2.50              = 11.00 €

C_TURPE         = 200 × 0.05                = 10.00 €
C_avant_taxes   = 11.00 + 10.00             = 21.00 €
Taxes           = 21.00 × 0.20              =  4.20 €

COÛT TOTAL      = 21.00 + 4.20              = 25.20 €
```

**Analyse :** la revente de l'excédent au prix spot réduit le coût. Cependant, l'achat contractuel (300 kW) est payé en totalité même si seulement 200 kW sont consommés — d'où l'importance d'une prévision précise pour calibrer les volumes achetés.

---

### Exemple 3 — Achat parfaitement calibré

**Données :**

- Volumes achetés : 300 kW = Consommation réelle : 300 kW
- Prix d'achat contractuel : 45 €/MWh
- Prix spot : 70 €/MWh (peu importe, écart = 0)

**Calcul :**

```
C_spot    = 70 × (300 - 300) / 1000 = 0 €   ← aucun écart à réguler
C_énergie = 300 × 45 / 1000         = 13.50 €
```

**Analyse :** avec une prédiction parfaite, le coût est minimal et prévisible. C'est l'objectif du modèle Prophet.

---

## Lien avec le modèle Prophet

Le modèle prévoit $\hat{C}_{réelle}$ pour les prochaines heures. Cette prévision est utilisée pour :

1. décider des volumes à acheter à terme ($V_{achetés} \approx \hat{C}_{réelle}$),
2. calculer le coût estimé affiché dans le dashboard,
3. alerter si une sur-consommation importante est prévue pendant des heures de pointe spot.

---

## Implémentation

La formule est implémentée dans le dashboard Streamlit (`dashboard_app.py`) et dans le module `src/budget_helper.py`.

Les prix spot sont importés depuis `api-dataclean` via l'endpoint `GET /dataclean/prixspot`.
