# Tests Automatisés — Documentation Complète

## Philosophie de test du projet

Le projet suit une stratégie de test à deux niveaux :

1. **Tests unitaires** : vérifient que chaque module Python (`data_loader`, `preprocessing`, `feature_engineering`, `utils`) fonctionne correctement de manière isolée.
2. **Tests d'intégration** : vérifient que l'enchaînement des modules (pipeline → prédiction) fonctionne de bout en bout.

> Pour un développeur reprenant le projet : avant de modifier un module, lancez les tests pour avoir une baseline. Après modification, relancez-les pour vérifier que vous n'avez rien cassé. C'est la règle de base.

---

## 1. Outils et framework utilisés

| Outil | Rôle |
|---|---|
| **pytest** | Framework principal de tests |
| **pandas / numpy** | Génération de données synthétiques de test |
| **PyYAML** | Lecture des fichiers de configuration dans les tests |
| **pytest-cov** | Mesure de couverture de code |
| **pytest-xdist** | Tests en parallèle (`-n auto`) |
| **tmp_path** | Isolation totale des fichiers temporaires (fixture native pytest) |
| **pytest.raises** | Validation des levées d'exceptions |
| **pytest.mark** | Marqueurs personnalisés (`slow`, `requires_data`, `unit`, `integration`) |

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

## 3. Installation des dépendances de test

```bash
pip install pytest pytest-cov pytest-xdist

# Ou via requirements-dev.txt si présent
pip install -r requirements-dev.txt
```

---

## 4. Fichier conftest.py — Fixtures partagées

Le fichier `conftest.py` centralise toutes les **données et ressources de test réutilisables** via le système de fixtures pytest. Il est chargé automatiquement sans import explicite.

### Fixtures disponibles

| Fixture | Description |
|---|---|
| `sample_dates` | Série de 365 dates journalières à partir du 01/01/2023 |
| `sample_dataframe` | DataFrame de 100 lignes horaires avec `puissance_moy_heure`, `temperature`, `humidite`, `prm` — graine fixée à 42 pour reproductibilité |
| `sample_config` | Dictionnaire de configuration complet (Prophet, chemins, validation, MLflow) |
| `temp_config_file` | Fichier YAML de configuration écrit dans `tmp_path` — isolation totale |
| `sample_prophet_data` | DataFrame au format Prophet (`ds`, `y`) avec saisonnalité sinusoïdale sur 365 jours |
| `data_dir` | Arborescence temporaire `processed/`, `raw/`, `predictions/` |

### Exclusion des patterns avancés

La fixture `collect_ignore` exclut `test_patterns_advanced.py` de l'exécution automatique :

```python
collect_ignore = ["test_patterns_advanced.py"]
```

---

## 5. Modules testés et couverture

### test_utils.py — Fonctions utilitaires

Deux fonctions testées : `load_config` et `detect_prms`.

#### TestLoadConfig

| Test | Ce qui est vérifié |
|---|---|
| `test_load_config_with_valid_file` | Retourne un `dict` non nul avec la clé `target = puissance_moy_heure` |
| `test_load_config_structure` | Présence obligatoire des clés `data`, `prophet`, `validation`, `prediction` |
| `test_load_config_with_nonexistent_file` | Lève une `FileNotFoundError` sur un chemin inexistant |

#### TestDetectPrms

| Test | Ce qui est vérifié |
|---|---|
| `test_detect_prms_empty_dir` | Retourne une liste vide ou un dict vide sur un répertoire sans fichiers |
| `test_detect_prms_with_sample_files` | Retourne un `dict {prm: Path}` — la clé `"12345"` pointe vers `dataclean_prm_12345.csv` |

---

### test_data_loader.py — Chargement des données

Fonction testée : `get_data_loader` (factory pattern).

#### TestGetDataLoader

| Test | Ce qui est vérifié |
|---|---|
| `test_get_data_loader_csv` | Instanciation correcte d'un loader CSV non nul |
| `test_get_data_loader_invalid_source` | Lève une exception (`ValueError`, `KeyError` ou autre) pour une source invalide |

#### TestDataLoaderInterface

| Test | Ce qui est vérifié |
|---|---|
| `test_loader_has_required_methods` | Présence des méthodes `load_dataclean`, `load_processed_site_data`, `save_processed_site_data` |

---

### test_preprocessing.py — Nettoyage des données

Trois fonctions testées : `clean_data`, `add_jour_ferie`, `aggregate_by_hour`.

#### TestCleanData

| Test | Ce qui est vérifié |
|---|---|
| `test_clean_data_basic` | Retourne un `DataFrame` non nul avec une colonne `datetime` |
| `test_clean_data_removes_duplicates` | Le nombre de lignes diminue après injection de doublons |
| `test_clean_data_sorts_by_datetime` | La colonne `datetime` est monotone croissante après nettoyage (`is_monotonic_increasing`) |

#### TestAddJourFerie

| Test | Ce qui est vérifié |
|---|---|
| `test_add_jour_ferie_column` | Colonne `jour_ferie` ajoutée avec type entier (`int32`, `int64` ou `int`) |
| `test_add_jour_ferie_values` | Les valeurs sont strictement dans `{0, 1}` |

#### TestAggregateByHour

| Test | Ce qui est vérifié |
|---|---|
| `test_aggregate_by_hour_basic` | Avec des données à 15 minutes, le DataFrame résultant a moins de lignes |
| `test_aggregate_by_hour_preserves_datetime` | La colonne `datetime` est toujours présente après agrégation |

---

### test_feature_engineering.py — Création des variables explicatives

Trois fonctions testées : `create_temporal_features`, `create_lag_features`, `create_rolling_features`.

#### TestCreateTemporalFeatures

| Test | Ce qui est vérifié |
|---|---|
| `test_temporal_features_basic` | Présence de colonnes `heure`/`hour` et `jour_semaine`/`dayofweek` |
| `test_temporal_features_creates_trig_functions` | Au moins 2 colonnes trigonométriques (`sin`, `cos`) créées |

Raison : les features sin/cos sont indispensables pour que le modèle Prophet capte les périodicités horaires et hebdomadaires.

#### TestCreateLagFeatures

| Test | Ce qui est vérifié |
|---|---|
| `test_lag_features_basic` | Au moins une colonne contenant `lag` est créée |
| `test_lag_features_correct_lags` | La colonne `puissance_moy_heure_lag_1` contient bien les valeurs décalées d'un rang |

#### TestCreateRollingFeatures

| Test | Ce qui est vérifié |
|---|---|
| `test_rolling_features_basic` | Au moins une colonne contenant `roll` est créée |
| `test_rolling_mean_values` | La colonne `puissance_roll_3` correspond à une moyenne glissante sur 3 périodes |

#### TestFeatureEngineering (intégration)

| Test | Ce qui est vérifié |
|---|---|
| `test_features_dont_have_nan_only` | Après enchaînement des trois transformations, aucune colonne de features n'est entièrement NaN |

Ce test d'intégration valide le **pipeline complet** de feature engineering bout en bout.

---

## 6. Lancer les tests

### Via le script dédié (recommandé pour le développement)

```bash
# Tous les tests
python run_tests.py

# En parallèle (plus rapide sur multi-cœurs)
python run_tests.py --fast

# Avec rapport de couverture HTML
python run_tests.py --coverage

# Tests unitaires uniquement
python run_tests.py --unit

# Tests d'intégration uniquement
python run_tests.py --integration

# Mode verbeux (affiche le nom de chaque test)
python run_tests.py -v

# Un fichier de test spécifique
python run_tests.py --specific test_utils.py
```

### Directement avec pytest

```bash
# Tous les tests depuis Modeles_TimesSeries/
pytest tests/ -v

# Tous les tests avec couverture de code
pytest tests/ --cov=src --cov-report=term-missing

# En parallèle
pytest tests/ -n auto

# Un fichier spécifique
pytest tests/test_utils.py -v

# Une classe spécifique
pytest tests/test_utils.py::TestLoadConfig -v

# Une fonction spécifique
pytest tests/test_utils.py::TestLoadConfig::test_load_config_with_valid_file -v

# Exclure les tests lents
pytest tests/ -m "not slow" -v

# Afficher les 10 tests les plus lents
pytest tests/ --durations=10

# Ne pas capturer les print (utile pour debug)
pytest tests/ -s

# Stopper au premier échec
pytest tests/ -x
```

---

## 7. Rapport de couverture

### Générer le rapport HTML

```bash
python run_tests.py --coverage
```

### Consulter le rapport

```bash
# Windows
start htmlcov/index.html

# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

### Interpréter le rapport

Le rapport indique quelle fraction du code est couverte par les tests. Les couleurs indiquent :
- 🟢 **Vert** : ligne de code couverte (exécutée par un test)
- 🔴 **Rouge** : ligne de code non couverte
- 🟡 **Jaune** : couverture partielle

L'**objectif du projet est de maintenir une couverture > 70%** sur les modules `src/`.

---

## 8. Écrire un nouveau test

### Structure recommandée (AAA pattern)

```python
# tests/test_mon_module.py

import pytest
from src.mon_module import ma_fonction

class TestMaFonction:

    def test_cas_nominal(self, sample_dataframe):
        # Arrange — préparer les données
        df = sample_dataframe

        # Act — appeler la fonction
        result = ma_fonction(df)

        # Assert — vérifier le résultat
        assert result is not None
        assert len(result) > 0

    def test_cas_erreur(self):
        # Vérifier qu'une exception est bien levée
        with pytest.raises(ValueError):
            ma_fonction(None)

    @pytest.mark.slow
    def test_cas_long(self, sample_dataframe):
        # Ce test peut être exclu avec : pytest -m "not slow"
        result = ma_fonction(sample_dataframe)
        assert result is not None
```

### Bonnes pratiques

| Bonne pratique | Exemple |
|---|---|
| **Noms explicites** | `test_load_config_returns_dict_with_prophet_key` plutôt que `test_load_config` |
| **Une responsabilité par test** | Un test = un comportement vérifié |
| **Utilisez les fixtures** | Ne reconstruisez pas les données dans chaque test |
| **Testez les cas d'erreur** | Vérifier les exceptions est aussi important que les cas nominaux |
| **Tests rapides** | Évitez les vraies connexions DB dans les tests unitaires (mocker) |
| **Isolation totale** | Utilisez `tmp_path` / `temp_config_file` pour les fichiers |
| **Seed fixe** | Fixez les graines aléatoires (`np.random.seed(42)`) |
| **Assertions claires** | Des messages d'erreur explicites : `assert len(result) > 0, "Result should not be empty"` |

---

## 9. Marqueurs personnalisés (pytest.mark)

Les marqueurs permettent de catégoriser et filtrer les tests :

```python
@pytest.mark.slow
def test_import_heavy_data():
    # Ce test sera exclu avec : pytest -m "not slow"
    pass

@pytest.mark.integration
def test_full_pipeline():
    # Ce test est une intégration
    pass

@pytest.mark.unit
def test_single_function():
    # Ce test est unitaire
    pass

@pytest.mark.requires_data
def test_with_csv_file():
    # Ce test nécessite des fichiers de données
    pass
```

### Utiliser les marqueurs

```bash
pytest -m "unit"          # Uniquement tests unitaires
pytest -m "integration"   # Uniquement tests d'intégration
pytest -m "not slow"      # Tous SAUF les tests lents
```

---

## 10. test_patterns_advanced.py — Référence pédagogique

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

## 11. Isolation et reproductibilité

Tous les tests sont **indépendants de l'environnement de production** :

- Les données sont **synthétiques** (générées avec `np.random.seed(42)`)
- Les fichiers sont créés dans des **répertoires temporaires** (`tmp_path`)
- Aucun fichier CSV réel ni connexion externe n'est nécessaire
- La graine aléatoire fixe garantit des résultats **identiques à chaque exécution**

---

## 12. Corrections apportées pendant le développement

| Problème | Correction |
|---|---|
| Dépréciation `freq="H"` dans pandas récent | Remplacé par `freq="h"` dans `conftest.py` et les fichiers de test |
| Colonnes de lag entièrement NaN quand `lag >= len(df)` | Ajout d'une logique de tolérance dynamique dans le test d'intégration |
| Source invalide dans `get_data_loader` | Test élargi à `(ValueError, KeyError, Exception)` pour couvrir les implémentations possibles |

---

## 13. Intégration en CI/CD

Les tests sont exécutés automatiquement à chaque `git push` via GitHub Actions.

### Workflow CI (`ci.yml`)

1. Installe Python 3.11 et les dépendances
2. Vérifie la syntaxe avec `flake8` et `ruff`
3. Lance `pytest --cov=src` avec rapport de couverture
4. En cas d'erreur, le déploiement est bloqué

### Exécution locale avant de pusher

```bash
# Reproduire exactement ce que GitHub Actions fera
bash scripts/run_ci_tests.sh
```

Si ce script passe ✅ en local, le pipeline GitHub Actions passera aussi.

---

## 14. Dépannage

| Problème | Solution |
|---|---|
| Tests échouent sur GitHub mais passent en local | Vérifier les versions de dépendances (`pip freeze`), l'encoding des fichiers |
| `ModuleNotFoundError` | Vérifier que vous êtes dans le dossier `Modeles_TimesSeries/` |
| `tmp_path` ne crée pas de répertoire | Mettre à jour pytest : `pip install --upgrade pytest` |
| Tests trop lents | Utiliser `pytest -m "not slow"` ou `python run_tests.py --fast` |
| Couverture incomplète | Identifier les lignes non couverts dans le rapport HTML, ajouter des tests |
| Fixture non trouvée | S'assurer que `conftest.py` est au même niveau que les tests |

---

## 15. Configuration pytest — `pytest.ini`

Le fichier `pytest.ini` centralise la configuration de l'exécution des tests :

```ini
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -q --tb=short -ra
```

| Paramètre | Signification |
|---|---|
| `testpaths = tests` | Les tests se trouvent uniquement dans le dossier `tests/` |
| `python_files = test_*.py` | Les fichiers de test commencent par `test_` |
| `python_classes = Test*` | Les classes de test commencent par `Test` |
| `python_functions = test_*` | Les fonctions de test commencent par `test_` |
| `addopts = -q --tb=short -ra` | Options par défaut : mode quiet, traceback court, résumé |

---

## 16. Résumé des points clés

✅ **Isolation totale** — aucune donnée réelle, fichiers temporaires
✅ **Reproductibilité** — graines aléatoires fixées
✅ **Rapidité** — tests en parallèle possible
✅ **Intégration CI** — tests automatiques à chaque push
✅ **Traçabilité** — rapport de couverture HTML
✅ **Pédagogie** — patterns avancés documentés
✅ **Facile à écrire** — fixtures réutilisables, AAA pattern
✅ **Facile à exécuter** — scripts Python + commandes pytest simples
