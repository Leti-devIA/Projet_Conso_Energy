# Guide des Tests

## Philosophie de test du projet

Le projet suit une stratégie de test à deux niveaux :

1. **Tests unitaires** (`tests/`) : vérifient que chaque module Python (`data_loader`, `preprocessing`, `feature_engineering`, `utils`) fonctionne correctement de manière isolée.
2. **Tests d'intégration** : vérifient que l'enchaînement des modules (API → pipeline → prédiction) fonctionne de bout en bout.

> Pour un développeur reprenant le projet : avant de modifier un module, lancez les tests pour avoir une baseline. Après modification, relancez-les pour vérifier que vous n'avez rien cassé. C'est la règle de base.

---

## Structure des tests

```
tests/
├── conftest.py                     # Fixtures partagées entre tous les tests
├── test_utils.py                   # Tests pour src/utils.py
├── test_data_loader.py             # Tests pour src/data_loader.py
├── test_preprocessing.py           # Tests pour src/preprocessing.py
├── test_feature_engineering.py     # Tests pour src/feature_engineering.py
└── README.md
```

### Fixtures disponibles (`conftest.py`)

Les fixtures sont des objets préconstruits injectés automatiquement dans vos tests :

| Fixture | Description |
|---|---|
| `sample_dates` | Série de dates de test |
| `sample_dataframe` | DataFrame avec données réalistes de test |
| `sample_config` | Dictionnaire de configuration YAML de test |
| `temp_config_file` | Fichier YAML temporaire (supprimé après le test) |
| `sample_prophet_data` | DataFrame au format Prophet (`ds`, `y`, régresseurs) |
| `data_dir` | Répertoires temporaires pour les tests I/O |

---

## Installation des dépendances de test

```bash
pip install pytest pytest-cov pytest-xdist

# Ou via requirements-dev.txt si présent
pip install -r requirements-dev.txt
```

---

## Lancer les tests

### Via le script dédié (recommandé)

```bash
# Tous les tests
python run_tests.py

# En parallèle (plus rapide sur multi-cœurs)
python run_tests.py --fast

# Avec rapport de couverture HTML
python run_tests.py --coverage

# Tests unitaires uniquement
python run_tests.py --unit

# Mode verbeux (affiche le nom de chaque test)
python run_tests.py -v
```

### Directement avec pytest

```bash
# Tous les tests
pytest

# Verbose
pytest -v

# Avec couverture de code
pytest --cov=src

# En parallèle
pytest -n auto

# Un fichier spécifique
pytest tests/test_utils.py

# Une classe spécifique
pytest tests/test_utils.py::TestLoadConfig

# Une fonction spécifique
pytest tests/test_utils.py::TestLoadConfig::test_load_config_with_valid_file
```

---

## Rapport de couverture

```bash
python run_tests.py --coverage
```

Puis ouvrir le rapport HTML :

```bash
# Windows
start htmlcov/index.html

# macOS
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

Le rapport indique quelle fraction du code est couverte par les tests. L'objectif du projet est de maintenir une couverture > 70% sur les modules `src/`.

---

## Écrire un nouveau test

### Structure recommandée

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
```

### Bonnes pratiques

| Bonne pratique | Exemple |
|---|---|
| Noms explicites | `test_load_config_returns_dict_with_prophet_key` |
| Une responsabilité par test | Un test = un comportement vérifié |
| Utilisez les fixtures | Ne reconstruisez pas les données dans chaque test |
| Testez les cas d'erreur | Vérifier les exceptions est aussi important que les cas nominaux |
| Tests rapides | Évitez les vraies connexions DB dans les tests unitaires (mocker) |

---

## Commandes pytest utiles

```bash
# Afficher les 10 tests les plus lents
pytest --durations=10

# Ne pas capturer les print (utile pour debug)
pytest -s

# Exclure les tests lents
pytest -m "not slow"

# Stopper au premier échec
pytest -x
```

---

## Intégration en CI

Les tests sont exécutés automatiquement à chaque `git push` via GitHub Actions (voir [Guide CI/CD](GUIDE_CICD.md)).

Le workflow CI :

1. installe Python 3.11 et les dépendances,
2. vérifie la syntaxe avec flake8/ruff,
3. lance `pytest --cov=src`,
4. affiche le rapport de couverture dans les logs GitHub Actions.

Si les tests échouent, une croix rouge s'affiche sur le commit GitHub et le déploiement est bloqué.
