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

## Hyperparamètres

Les valeurs par défaut ci-dessous sont lues depuis `config/config.yaml` par `src/train.py` via `build_prophet_model()`. Chaque PRM peut les surcharger via la section `site_overrides`.

| Paramètre | Valeur par défaut |
|---|---|
| `seasonality_mode` | `additive` |
| `changepoint_prior_scale` | `0.005` |
| `seasonality_prior_scale` | `10.0` |
| `holidays_prior_scale` | `10` |
| `n_changepoints` | `25` |
| `changepoint_range` | `0.8` |
| `daily_fourier_order` | `10` |
| `weekly_fourier_order` | `5` |
| `yearly_fourier_order` | `10` |
| `interval_width` | `0.95` (hardcodé dans `train.py`) |

---

### `seasonality_mode`

Permet de définir la manière dont les variations saisonnières sont appliquées.

- **`additive`** : le modèle ajoute des écarts fixes au niveau de consommation.
- **`multiplicative`** : les variations sont proportionnelles au niveau observé — plus la consommation de base est élevée, plus l'amplitude des variations l'est aussi.

Le mode `multiplicative` est mieux adapté aux sites dont les pics de consommation augmentent fortement lors des périodes de forte activité.

---

### `growth`

Permet de définir la forme générale de la tendance dans le temps.

- **`linear`** : le modèle suppose que la consommation peut progressivement monter ou descendre au fil de l'historique.
- **`flat`** : considère au contraire que le niveau global reste plutôt stable, sans vraie tendance de fond.

---

### `changepoint_prior_scale`

Permet de régler la souplesse de la tendance. Avec une valeur faible, le modèle suit une trajectoire plus lisse et évite de réagir au moindre mouvement. Avec une valeur plus élevée, il accepte plus facilement des ruptures et des changements de direction.

Ce paramètre agit comme un réglage de sensibilité : trop faible, le modèle peut manquer des évolutions réelles ; trop fort, il peut interpréter du bruit comme un changement de comportement.

| Valeur | Comportement |
|---|---|
| `0.001` — `0.01` | Tendance presque rigide |
| `0.05` | Valeur par défaut Prophet |
| `0.1` — `0.5` | Tendance très flexible, réagit vite aux changements |

---

### `seasonality_prior_scale`

Permet de régler l'importance accordée aux effets saisonniers, comme les cycles quotidiens ou hebdomadaires. Avec une valeur faible, le modèle reste prudent et limite l'amplitude de ces motifs répétés. Avec une valeur plus élevée, il leur donne davantage de place dans la prédiction.

Ce paramètre permet d'équilibrer le poids des habitudes de consommation récurrentes.

| Valeur | Comportement |
|---|---|
| `1.0` | Saisonnalité quasi absente |
| `10.0` | Valeur par défaut (saisonnalité modérée) |
| `20.0` — `50.0` | Saisonnalité très marquée |

---

### `daily_seasonality` / `weekly_seasonality` / `yearly_seasonality`

> Dans ce projet, ces trois paramètres natifs Prophet sont **désactivés** (`false`) dans `config.yaml`. Les saisonnalités sont ajoutées manuellement via `add_seasonality` pour contrôler précisément l'ordre de Fourier.

- **`daily_seasonality`** : indique si le modèle doit prendre en compte un rythme journalier. Lorsqu'il est activé, le modèle cherche des motifs qui se répètent d'une heure à l'autre au sein d'une journée.
- **`weekly_seasonality`** : indique si le modèle doit intégrer un rythme hebdomadaire — par exemple une différence récurrente entre les jours ouvrés et le week-end.
- **`yearly_seasonality`** : indique si le modèle doit intégrer un rythme annuel, comme les grandes variations liées aux saisons.

---

### `holidays_prior_scale`

Permet de régler l'influence des jours fériés sur le modèle. Avec une valeur faible, les jours fériés ont un effet limité sur la prévision. Avec une valeur plus élevée, le modèle accepte plus facilement qu'ils provoquent des écarts marqués par rapport au fonctionnement habituel.

Ce réglage est utile lorsque l'activité d'un site change fortement lors de ces journées particulières.

---

### `daily_fourier_order`

Permet de régler le niveau de détail du cycle journalier. Une valeur faible décrit une forme simple, avec quelques variations principales dans la journée. Une valeur plus élevée autorise une courbe plus fine, capable de représenter des pics et creux plus complexes heure par heure.

Ce paramètre agit comme un niveau de précision sur le rythme quotidien.

---

### `weekly_fourier_order`

Permet de régler le niveau de détail du cycle hebdomadaire. Une valeur faible représente une semaine avec une structure simple — par exemple une différence générale entre jours ouvrés et week-end. Une valeur plus élevée permet de distinguer plus finement les comportements propres à certains jours.

Ce paramètre est utile lorsque la consommation ne suit pas le même profil du lundi au dimanche.

---

### `yearly_fourier_order`

Permet de régler le niveau de détail du cycle annuel. Une valeur faible décrit de grandes tendances saisonnières, comme l'hiver plus consommateur que l'été. Une valeur plus élevée permet de capter des variations plus fines au cours de l'année.

Ce réglage est particulièrement pertinent lorsque la consommation dépend fortement des saisons ou des conditions climatiques.

---

### `n_changepoints`

Permet de définir le nombre de points de rupture potentiels que le modèle peut examiner dans l'historique. Plus cette valeur est élevée, plus le modèle dispose d'occasions de détecter des changements de tendance. À l'inverse, une valeur plus faible le conduit à rester plus simple et plus stable.

Ce paramètre revient à fixer combien d'endroits le modèle est autorisé à surveiller pour repérer une évolution du comportement.

---

### `changepoint_range`

Permet de définir sur quelle partie de l'historique le modèle recherche ces changements de tendance. Par exemple, une valeur de `0.8` signifie qu'il cherchera surtout dans les 80 % initiaux des données, en laissant la fin de la série plus stable. Une valeur plus élevée étend cette recherche plus près de la période récente.

Ce réglage évite que le modèle s'ajuste trop fortement sur les derniers points observés.

---

## Overrides par site

Chaque PRM peut avoir ses propres paramètres dans la section `site_overrides` du `config.yaml`. Ces overrides remplacent les valeurs par défaut lors de l'entraînement de ce PRM.

Exemple extrait de la config réelle :

| PRM | `seasonality_mode` | `changepoint_prior_scale` | `daily_fourier_order` | `growth` |
|---|---|---|---|---|
| 30000250086126 | `multiplicative` | `0.01` | `5` | `flat` |
| 30000650805048 | `multiplicative` | `0.1` | `10` | `flat` |
| 30000540185031 | `multiplicative` | `0.1` | `10` | `linear` |
| 30000260159032 | `multiplicative` | `0.05` | `18` | `flat` |
| 30000651139165 | `multiplicative` | `0.5` | `20` | `flat` |
| 30000651332664 | `multiplicative` | `0.01` | `10` | `flat` |
| 50009082209764 | `multiplicative` | `0.01` | `10` | `flat` |
| 30001210305252 | `multiplicative` | `0.1` | `10` | `flat` |
| 50003424619289 | `additive` | `0.005` | `10` | `linear` |
| 30000651046024 | `additive` | `0.005` | `10` | `linear` |
| 30000650060080 | `multiplicative` | `0.1` | `20` | `flat` |

---

## Régresseurs ajoutés au modèle

Les colonnes suivantes sont ajoutées comme régresseurs externes (`add_regressor`) :

```text
temperature, humidite, precipitation, couverture_nuages, vitesse_vent,
is_holiday, heure_sin, heure_cos, jour_sin, jour_cos, is_weekend,
temp_x_heure_sin, temp_x_heure_cos,
puissance_lag_24, puissance_lag_168,
dju_chauffage, grand_froid
```

> Certains régresseurs sont standardisés avant d'être passés à Prophet (colonnes météo et interactions) pour équilibrer les échelles.

---

## Saisonnalités

Les trois saisonnalités sont ajoutées via `add_seasonality` (les paramètres natifs `daily_seasonality`, `weekly_seasonality`, `yearly_seasonality` sont désactivés) :

| Nom | Période | Ordre Fourier |
|---|---|---|
| `daily` | 1 jour (en jours) | `daily_fourier_order` |
| `weekly` | 7 jours | `weekly_fourier_order` |
| `yearly` | 365.25 jours | `yearly_fourier_order` |

---

## Pour aller plus loin

- [Pipeline d'entraînement](PIPELINE_ENTRAINEMENT.md) — comprendre comment les données arrivent à Prophet
- [Grid Search](GRID_SEARCH_GUIDE.md) — optimiser les hyperparamètres automatiquement
- [MLflow](MLFLOW_GUIDE.md) — comparer les runs d'entraînement
- Documentation officielle Prophet : https://facebook.github.io/prophet/
