# Tests du Projet Prophet Energy Forecast

Ce répertoire contient les tests unitaires et d'intégration du projet.

## Structure des tests

```
tests/
├── __init__.py                 # Package Python
├── conftest.py                 # Fixtures pytest partagées
├── test_utils.py              # Tests pour utils.py
├── test_data_loader.py        # Tests pour data_loader.py
├── test_preprocessing.py       # Tests pour preprocessing.py
├── test_feature_engineering.py # Tests pour feature_engineering.py
└── README.md                   # Ce fichier
```

## Installation des dépendances de test

```bash
# Installer pytest et plugins
pip install pytest pytest-cov pytest-xdist

# Ou via requirements-dev.txt (à créer)
pip install -r requirements-dev.txt
```

## Exécution des tests

### Tous les tests
```bash
pytest
# ou
python -m pytest
```

### Tests d'un fichier spécifique
```bash
pytest tests/test_utils.py
```

### Tests d'une classe spécifique
```bash
pytest tests/test_utils.py::TestLoadConfig
```

### Tests d'une fonction spécifique
```bash
pytest tests/test_utils.py::TestLoadConfig::test_load_config_with_valid_file
```

### Tests avec couverture de code
```bash
pytest --cov=src --cov-report=html
# Ouvre le rapport HTML
start htmlcov/index.html  # Windows
open htmlcov/index.html   # Mac
```

### Tests en parallèle (plus rapide)
```bash
pytest -n auto  # Utilise tous les cœurs disponibles
```

### Tests avec verbose
```bash
pytest -v  # Affiche tous les détails
pytest -vv # Encore plus de détails
```

### Tests sans capture (affiche les print)
```bash
pytest -s
```

### Tests avec marqueurs
```bash
# Uniquement les tests unitaires
pytest -m unit

# Sauf les tests lents
pytest -m "not slow"

# Les tests nécessitant les données
pytest -m requires_data
```

## Markers personnalisés

Les tests peuvent être marqués avec les décorateurs suivants :

```python
@pytest.mark.unit              # Test unitaire
@pytest.mark.integration       # Test d'intégration
@pytest.mark.slow              # Test lent
@pytest.mark.requires_data     # Nécessite les fichiers de données
```

Exemple :
```python
@pytest.mark.unit
def test_something():
    pass
```

## Fixtures disponibles (conftest.py)

### `sample_dates`
Série de dates de test.

### `sample_dataframe`
DataFrame avec données de consommation de test.

### `sample_config`
Configuration de test.

### `temp_config_file`
Fichier de configuration YAML temporaire.

### `sample_prophet_data`
DataFrame au format Prophet (ds, y).

### `data_dir`
Structure de répertoires temporaire pour les données.

## Bonnes pratiques

1. **Un test = une responsabilité** : Chaque test ne doit vérifier qu'une seule chose
2. **Noms explicites** : `test_load_config_returns_dict()` plutôt que `test_1()`
3. **Utiliser les fixtures** : Réutilise `sample_dataframe` au lieu de créer un nouveau DF à chaque fois
4. **Groupe logique** : Utilise les classes Test* pour grouper les tests liés
5. **Gestion d'erreurs** : Teste aussi les cas d'erreur avec `pytest.raises()`

Exemple :
```python
def test_division_by_zero():
    with pytest.raises(ZeroDivisionError):
        result = 1 / 0
```

## Ajouter de nouveaux tests

1. Crée un fichier `test_module_name.py` dans le dossier `tests/`
2. Crée une classe Test* pour chaque groupe logique
3. Crée des méthodes test_*() pour chaque cas
4. Utilise les fixtures du conftest.py

Exemple simple :
```python
import pytest
from my_module import my_function

class TestMyFunction:
    def test_basic_case(self):
        result = my_function(5)
        assert result == 10

    def test_error_case(self):
        with pytest.raises(ValueError):
            my_function(-5)
```

## CI/CD Integration

Pour intégrer les tests dans un pipeline CI/CD :

```bash
# Genère un rapport JUnit XML
pytest --junit-xml=test-results.xml

# Genère un rapport de couverture
pytest --cov=src --cov-report=xml
```

## Troubleshooting

### Les tests ne trouvent pas les modules
Assurez-vous que le chemin src/ est correct dans conftest.py.

### Les tests sont trop lents
- Utilis `-n auto` pour exécuter en parallèle
- Marque les tests lents avec `@pytest.mark.slow` et exécute-les séparément

### Les fixtures ne sont pas trouvées
Vérifiez que conftest.py est dans le dossier tests/ ou dans le dossier parent.

## Contact

Pour toute question sur les tests, consulte le README principal du projet.
