# Simulation prix et achats énergie

Cette page décrit la logique de simulation de coûts telle qu'elle est implémentée dans :

- `dashboard_app.py` (interface et calculs métier affichés)
- `src/simulation_engine.py` (moteur horaire générique)

## 1) Entrées utilisées

### Consommation

- Historique et/ou prévisions agrégées à l'heure.
- Conversion en énergie horaire :

$$energy\_mwh = puissance\_kw \times interval\_h / 1000$$

### Prix

- Source `prices_df` avec granularités possibles :
  - `horaire`
  - `mensuel`
  - `trimestriel`
  - `annuel`
- Priorité appliquée : `horaire > mensuel > trimestriel > annuel`.
- Valeur de secours quand indisponible : `55.0 €/MWh`.

### Portefeuille d'achats existants

- Chargé depuis `data/raw/achats/ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv`.
- Colonnes exploitées dans l'UI :
  - `TYPE_ACHAT`
  - `FIXATION_PUISSANCE_ACHAT_MW`
  - `PRIX_FIXATION`
  - `DEB_PERIODE`
  - `FIN_PERIODE`

## 2) Typologies d'achat

### Dans l'interface dashboard

- `Base` : toutes les heures.
- `Peak` : lundi-vendredi, de 08:00 inclus à 20:00 exclus.
- `Sens` : `Achat` ou `Vente`.

### Dans `src/simulation_engine.py`

Le moteur supporte aussi :

- `Base`
- `Peakload`
- `OffPeak`
- plage horaire personnalisée via `hour_start` / `hour_end`
- filtre jours `all | business | weekend`

## 3) Calcul du scénario

Le moteur applique heure par heure :

$$C_h = C_{forward,h} + P_{spot,h} \times (Conso_h - V_{forward,h})$$

où :

- $C_{forward,h}$ = coût des volumes déjà couverts à terme,
- $V_{forward,h}$ = volume couvert (MWh),
- $Conso_h$ = consommation de l'heure (MWh),
- $P_{spot,h}$ = prix spot de l'heure (€/MWh).

## 4) Comparaison « En l'état » vs « Simulé »

Le dashboard calcule :

1. **En l'état** : portefeuille actuel + résiduel spot.
2. **Simulé** : ajout/retrait d'un achat saisi par l'utilisateur.
3. KPIs de comparaison : coût total, écart absolu et écart %.

Pour une vente, le volume simulé est borné par le volume déjà acheté.

## 5) Sorties et KPIs

### Dans le dashboard

- cartes KPI (coût avant/après, écart),
- graphique comparatif achat/spot,
- texte de synthèse (économie ou surcoût).

### Dans le moteur `src/simulation_engine.py`

- séries horaires `scenario_a` / `scenario_b`,
- agrégats journaliers,
- indicateurs : `cout_total_eur`, `cout_forward_eur`, `cout_spot_eur`, `prix_moyen_mwh`, `pct_spot`, etc.

## 6) Schéma de calcul

```text
Consommation horaire + Prix horaire + Portefeuille achats
                    │
                    ▼
            Construction scénario A
                    │
        + achat/vente simulé utilisateur
                    ▼
            Construction scénario B
                    │
                    ▼
          Comparaison coûts et KPIs
```
