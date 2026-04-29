# Modèle Prophet — Fonctionnement et Optimisations

## Qu'est-ce que Prophet ?

**Prophet** est un modèle de prévision de séries temporelles développé par Meta (anciennement Facebook), conçu pour s'adapter aux données avec :

- plusieurs saisonnalités (quotidienne, hebdomadaire, annuelle),
- des effets de jours fériés,
- des changements de tendance progressifs ou brusques.

Prophet décompose la série temporelle en composantes additives (ou multiplicatives) :

$$y(t) = T(t) + S(t) + H(t) + \epsilon(t)$$

Où :

| Composante | Symbole | Description |
|---|---|---|
| Tendance | $T(t)$ | Évolution long terme (croissance ou déclin) |
| Saisonnalité | $S(t)$ | Cycles réguliers (jour, semaine, année) |
| Jours fériés | $H(t)$ | Effets ponctuels sur certaines dates |
| Résidu | $\epsilon(t)$ | Erreur non expliquée |

---

## Saisonnalité avec séries de Fourier

Prophet modélise chaque saisonnalité par une somme de termes sinusoïdaux (approximation de Fourier) :

$$S(t) = \sum_{n=1}^{N} \left[ a_n \cos\left(\frac{2\pi n t}{P}\right) + b_n \sin\left(\frac{2\pi n t}{P}\right) \right]$$

Où :

- $P$ est la période (24h pour la journée, 168h pour la semaine, 8760h pour l'année),
- $N$ est l'ordre de Fourier (plus $N$ est grand, plus la saisonnalité est détaillée),
- $a_n$ et $b_n$ sont des coefficients appris pendant l'entraînement.

**Importance pour ce projet :** la consommation électrique a des cycles très marqués (pic matin/soir, différence jour ouvrable/week-end, saisonnalité chauffage/climatisation). Augmenter l'ordre de Fourier permet de capturer ces patterns fins.

---

## Hyperparamètres clés

### `changepoint_prior_scale`

Contrôle la **flexibilité de la tendance**. Un changement de tendance survient quand la consommation augmente ou diminue structurellement (ex : nouveau matériel industriel).

| Valeur | Comportement |
|---|---|
| 0.001 — 0.01 | Tendance presque rigide |
| 0.05 | Comportement par défaut (modéré) |
| 0.1 — 0.3 | Tendance très flexible, réagit vite aux changements |

Valeur recommandée pour ce projet : **0.1**

---

### `seasonality_prior_scale`

Contrôle l'**amplitude des saisonnalités**. Si la consommation varie beaucoup entre les saisons ou entre les heures de la journée, augmenter cette valeur aide le modèle à capturer ces variations.

| Valeur | Comportement |
|---|---|
| 1.0 — 5.0 | Saisonnalité faible |
| 10 | Valeur par défaut |
| 15 — 20 | Saisonnalité marquée (conseillé pour conso électrique) |

Valeur recommandée pour ce projet : **15**

---

### `seasonality_mode`

Détermine si les saisonnalités s'**ajoutent** ou se **multiplient** à la tendance.

- `additive` : $y = T + S$ — adapté si la variance est constante dans le temps.
- `multiplicative` : $y = T \times S$ — adapté si la variance augmente avec le niveau (ex : un site dont la consommation varie du simple au triple selon la saison).

Pour ce projet, le mode est déterminé par le grid search (voir [Guide Grid Search](GRID_SEARCH_GUIDE.md)).

---

### `holidays_prior_scale`

Contrôle l'impact modélisé des jours fériés. Une valeur trop élevée rend le modèle très sensible aux jours fériés, ce qui peut causer du surapprentissage sur les fériés passés.

Valeur recommandée : **10**


---

## Pour aller plus loin

- [Pipeline d'entraînement](PIPELINE_ENTRAINEMENT.md) — comprendre comment les données arrivent à Prophet
- [Grid Search](GRID_SEARCH_GUIDE.md) — optimiser les hyperparamètres automatiquement
- [MLflow](MLFLOW_GUIDE.md) — comparer les runs d'entraînement
- Documentation officielle Prophet : https://facebook.github.io/prophet/
