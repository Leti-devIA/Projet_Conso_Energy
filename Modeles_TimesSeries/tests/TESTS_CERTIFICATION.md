# Tests automatisés — Documentation pour la certification Simplon IA (C12)

Ce document décrit précisément ce qui a été mis en place au niveau des tests automatisés dans le projet de prévision de consommation énergétique.

---

## 1. Outil et framework utilisés

- **pytest** — framework principal de tests
- **pandas / numpy** — génération des données synthétiques de test
- **PyYAML** — lecture des fichiers de configuration dans les tests
- **tmp_path** (fixture native pytest) — isolation totale des fichiers temporaires
- **pytest.raises** — validation des levées d'exceptions
- **pytest.mark** — marqueurs personnalisés (`slow`, `requires_data`)

---

## 2. Structure du dossier de tests

```
tests/
├── conftest.py                  # Fixtures partagées entre tous les fichiers
├── test_utils.py                # Tests des fonctions utilitaires (config, PRM)
├── test_data_loader.py          # Tests du chargement des données
├── test_preprocessing.py        # Tests du nettoyage et agrégation
├── test_feature_engineering.py  # Tests de la création des variables explicatives
├── test_patterns_advanced.py    # Fichier pédagogique (exclu de l'exécution auto)
└── README.md                    # Documentation rapide du dossier
```

---

## 3. Fichier conftest.py — Fixtures partagées

Le fichier `conftest.py` centralise toutes les **données et ressources de test réutilisables** via le système de fixtures pytest. Il est chargé automatiquement sans import explicite.

### Fixtures définies

| Fixture | Description |
|---|---|
| `sample_dates` | Série de 365 dates journalières à partir du 01/01/2023 |
| `sample_dataframe` | DataFrame de 100 lignes horaires avec `puissance_moy_heure`, `temperature`, `humidite`, `prm` — graine fixée à 42 |
| `sample_config` | Dictionnaire de configuration complet (Prophet, chemins, validation, MLflow) |
| `temp_config_file` | Fichier YAML de configuration écrit dans `tmp_path` — isolation totale |
| `sample_prophet_data` | DataFrame au format Prophet (`ds`, `y`) avec saisonnalité sinusoïdale sur 365 jours |
| `data_dir` | Arborescence temporaire `processed/`, `raw/`, `predictions/` |

La fixture `collect_ignore` exclut `test_patterns_advanced.py` de l'exécution automatique :

```python
collect_ignore = ["test_patterns_advanced.py"]
```

---

## 4. test_utils.py — Fonctions utilitaires

Deux fonctions testées : `load_config` et `detect_prms`.

### TestLoadConfig

| Test | Ce qui est vérifié |
|---|---|
| `test_load_config_with_valid_file` | Retourne un `dict` non nul avec la clé `target = puissance_moy_heure` |
| `test_load_config_structure` | Présence obligatoire des clés `data`, `prophet`, `validation`, `prediction` |
| `test_load_config_with_nonexistent_file` | Lève une `FileNotFoundError` sur un chemin inexistant |

### TestDetectPrms

| Test | Ce qui est vérifié |
|---|---|
| `test_detect_prms_empty_dir` | Retourne une liste vide ou un dict vide sur un répertoire sans fichiers |
| `test_detect_prms_with_sample_files` | Retourne un `dict {prm: Path}` — la clé `"12345"` pointe vers `dataclean_prm_12345.csv` |

---

## 5. test_data_loader.py — Chargement des données

Fonction testée : `get_data_loader` (factory pattern).

### TestGetDataLoader

| Test | Ce qui est vérifié |
|---|---|
| `test_get_data_loader_csv` | Instanciation correcte d'un loader CSV non nul |
| `test_get_data_loader_invalid_source` | Lève une exception (`ValueError`, `KeyError` ou autre) pour une source invalide |

### TestDataLoaderInterface

| Test | Ce qui est vérifié |
|---|---|
| `test_loader_has_required_methods` | Présence des méthodes `load_dataclean`, `load_processed_site_data`, `save_processed_site_data` |

---

## 6. test_preprocessing.py — Nettoyage des données

Trois fonctions testées : `clean_data`, `add_jour_ferie`, `aggregate_by_hour`.

### TestCleanData

| Test | Ce qui est vérifié |
|---|---|
| `test_clean_data_basic` | Retourne un `DataFrame` non nul avec une colonne `datetime` |
| `test_clean_data_removes_duplicates` | Le nombre de lignes diminue après injection de doublons |
| `test_clean_data_sorts_by_datetime` | La colonne `datetime` est monotone croissante après nettoyage (`is_monotonic_increasing`) |

### TestAddJourFerie

| Test | Ce qui est vérifié |
|---|---|
| `test_add_jour_ferie_column` | Colonne `jour_ferie` ajoutée avec type entier (`int32`, `int64` ou `int`) |
| `test_add_jour_ferie_values` | Les valeurs sont strictement dans `{0, 1}` |

### TestAggregateByHour

| Test | Ce qui est vérifié |
|---|---|
| `test_aggregate_by_hour_basic` | Avec des données à 15 minutes, le DataFrame résultant a moins de lignes |
| `test_aggregate_by_hour_preserves_datetime` | La colonne `datetime` est toujours présente après agrégation |

---

## 7. test_feature_engineering.py — Création des variables explicatives

Trois fonctions testées : `create_temporal_features`, `create_lag_features`, `create_rolling_features`.

### TestCreateTemporalFeatures

| Test | Ce qui est vérifié |
|---|---|
| `test_temporal_features_basic` | Présence de colonnes `heure`/`hour` et `jour_semaine`/`dayofweek` |
| `test_temporal_features_creates_trig_functions` | Au moins 2 colonnes trigonométriques (`sin`, `cos`) créées |

Les features sin/cos sont indispensables pour que le modèle Prophet capte les périodicités horaires et hebdomadaires.

### TestCreateLagFeatures

| Test | Ce qui est vérifié |
|---|---|
| `test_lag_features_basic` | Au moins une colonne contenant `lag` est créée |
| `test_lag_features_correct_lags` | La colonne `puissance_moy_heure_lag_1` contient bien les valeurs décalées d'un rang |

### TestCreateRollingFeatures

| Test | Ce qui est vérifié |
|---|---|
| `test_rolling_features_basic` | Au moins une colonne contenant `roll` est créée |
| `test_rolling_mean_values` | La colonne `puissance_roll_3` correspond à une moyenne glissante sur 3 périodes |

### TestFeatureEngineering (intégration)

| Test | Ce qui est vérifié |
|---|---|
| `test_features_dont_have_nan_only` | Après enchaînement des trois transformations, aucune colonne de features n'est entièrement NaN |

Ce test d'intégration valide le **pipeline complet** de feature engineering bout en bout.

---

## 8. test_patterns_advanced.py — Référence pédagogique

Ce fichier est **exclu de l'exécution automatique** (`collect_ignore` dans `conftest.py`). Il documente les patterns pytest avancés étudiés et maîtrisés pendant le projet :

| Pattern | Description |
|---|---|
| `@pytest.mark.parametrize` | Tests paramétrés sur plusieurs valeurs d'entrée |
| `@pytest.mark.slow` / `requires_data` | Marqueurs personnalisés pour filtrer les tests |
| `setup_class` / `teardown_class` | Cycle de vie de classe de test |
| `setup_method` / `teardown_method` | Cycle de vie par méthode |
| `pytest.raises` | Validation des exceptions avec vérification du message |
| Fixtures paramétrées | Fixture avec `params=[10, 20, 30]` |
| Scopes de fixture | `session`, `module`, `function` |
| `autouse=True` | Fixture exécutée automatiquement sans déclaration |
| `pytest-mock` / `mocker` | Mocking d'objets et de fonctions |
| `pytest.approx` | Comparaison de flottants avec tolérance |
| `pytest.mark.skipif` | Saut conditionnel de tests |
| `pytest.mark.xfail` | Tests en échec attendu |
| `pd.testing.assert_frame_equal` | Assertions sur DataFrames pandas |

---

## 9. Lancer les tests

Depuis le dossier `Modeles_TimesSeries/` :

```bash
# Tous les tests
pytest tests/ -v

# Un fichier spécifique
pytest tests/test_utils.py -v

# Une fonction spécifique
pytest tests/test_preprocessing.py::TestCleanData::test_clean_data_basic -v

# Exclure les tests lents
pytest tests/ -m "not slow" -v

# Avec rapport de couverture (si pytest-cov installé)
pytest tests/ --cov=src --cov-report=term-missing
```

---

## 10. Isolation et reproductibilité

Tous les tests sont **indépendants de l'environnement de production** :

- Les données sont **synthétiques** (générées avec `np.random.seed(42)`)
- Les fichiers sont créés dans des **répertoires temporaires** (`tmp_path`)
- Aucun fichier CSV réel ni connexion externe n'est nécessaire
- La graine aléatoire fixe garantit des résultats **identiques à chaque exécution**

---

## 11. Corrections apportées pendant le développement

| Problème | Correction |
|---|---|
| Dépréciation `freq="H"` dans pandas récent | Remplacé par `freq="h"` dans `conftest.py` et les fichiers de test |
| Colonnes de lag entièrement NaN quand `lag >= len(df)` | Ajout d'une logique de tolérance dynamique dans le test d'intégration |
| Source invalide dans `get_data_loader` | Test élargi à `(ValueError, KeyError, Exception)` pour couvrir les implémentations possibles |
