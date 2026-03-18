# Guide des Tests - Prophet Energy Forecast

## 🚀 Démarrage rapide

### 1️⃣ Installation des dépendances de test

```bash
# Installer pytest et les tools de test
pip install -r requirements-dev.txt

# Ou juste pytest si c'est tout ce que tu veux
pip install pytest pytest-cov
```

### 2️⃣ Lancer les tests

```bash
# Tous les tests (recommandé)
python run_tests.py

# Tests en parallèle (plus rapide)
python run_tests.py --fast

# Avec rapport de couverture
python run_tests.py --coverage

# Uniquement les tests unitaires
python run_tests.py --unit

# Mode verbose (affiche tout)
python run_tests.py -v

# Ou directement avec pytest
pytest                  # Tous les tests
pytest -v             # Verbose
pytest --cov=src      # Avec coverage
pytest -n auto        # Parallèle
```

### 3️⃣ Voir le rapport de couverture

Après avoir lancé `python run_tests.py --coverage` :

```bash
# Windows
start htmlcov/index.html

# Mac
open htmlcov/index.html

# Linux
xdg-open htmlcov/index.html
```

## 🔧 Structure des tests

```
tests/
├── conftest.py                 # Fixtures réutilisables
├── test_utils.py              # Tests pour utils.py
├── test_data_loader.py        # Tests pour data_loader.py
├── test_preprocessing.py       # Tests pour preprocessing.py
├── test_feature_engineering.py # Tests pour feature_engineering.py
└── README.md                   # Documentation détaillée
```

## 📝 Exemples de commandes

```bash
# Tests d'un fichier spécifique
pytest tests/test_utils.py

# Tests d'une classe spécifique
pytest tests/test_utils.py::TestLoadConfig

# Tests d'une fonction spécifique
pytest tests/test_utils.py::TestLoadConfig::test_load_config_with_valid_file

# Tests sans affichage des print (plus rapide)
pytest tests/

# Tests avec affichage des print (pour debug)
pytest tests/ -s

# Tests lents aussi
pytest tests/ -m "not slow"

# Afficher les 10 tests les plus lents
pytest --durations=10
```

## 🧪 Fixtures disponibles

Toutes les fixtures sont dans `tests/conftest.py` :

- `sample_dates` : Série de dates
- `sample_dataframe` : DataFrame avec données de test
- `sample_config` : Configuration YAML de test
- `temp_config_file` : Fichier config temporaire
- `sample_prophet_data` : DataFrame format Prophet
- `data_dir` : Répertoires temporaires

Exemple d'utilisation :
```python
def test_something(sample_dataframe):
    # sample_dataframe est automatiquement injecté
    assert len(sample_dataframe) > 0
```

## ✅ Bonnes pratiques

1. **Écrire des tests dès le début** : Un test = une responsabilité
2. **Noms explicites** :
   ```python
   # ✅ Bon
   def test_load_config_returns_dict_with_prophet_key():
       pass

   # ❌ Mauvais
   def test_1():
       pass
   ```

3. **Utiliser les fixtures** :
   ```python
   # ✅ Bon (réutilise sample_dataframe)
   def test_with_data(sample_dataframe):
       pass

   # ❌ Mauvais (crée un nouveau DF à chaque fois)
   def test_with_data():
       df = pd.DataFrame(...)
       pass
   ```

4. **Tester les cas d'erreur** :
   ```python
   def test_error_handling():
       with pytest.raises(FileNotFoundError):
           load_config("nonexistent.yaml")
   ```

5. **Grouper les tests logiquement** :
   ```python
   class TestLoadConfig:
       def test_basic(self): pass
       def test_error(self): pass
   ```

## 🔍 Ajouter des tests

Pour ajouter des tests à un nouveau module :

1. Crée un fichier `tests/test_module_name.py`
2. Ajoute des classes `class Test*`
3. Ajoute des méthodes `def test_*()`
4. Utilise les fixtures du conftest.py

Exemple :
```python
import pytest
from src.my_module import my_function

class TestMyFunction:
    def test_basic_case(self):
        result = my_function(5)
        assert result == 10

    def test_error_case(self):
        with pytest.raises(ValueError):
            my_function(-5)

    def test_with_fixture(self, sample_dataframe):
        # Utilise une fixture
        assert len(sample_dataframe) > 0
        result = my_function(sample_dataframe)
        assert result is not None
```

## 📊 Rapports et Métriques

### Coverage Report
```bash
pytest --cov=src --cov-report=html
# Ouvre htmlcov/index.html pour voir le détail par fichier
```

### Rapport JUnit XML (pour CI/CD)
```bash
pytest --junit-xml=test-results.xml
```

### Tests les plus lents
```bash
pytest --durations=10  # Top 10 des tests les plus lents
```

## 🐛 Troubleshooting

### Les tests ne trouvent pas les modules
- Assure-toi que `sys.path.insert(0, ...)` est correct dans conftest.py
- Essaie : `python -m pytest tests/` au lieu de `pytest tests/`

### Les tests prennent trop de temps
```bash
# Utilise la parallélisation
pip install pytest-xdist
pytest -n auto
```

### TestError pendant l'import
```bash
# Mode verbose pour voir l'erreur exacte
pytest --tb=long -v
```

### Une fixture n'est pas trouvée
- Vérifie que conftest.py est dans le dossier `tests/` ou parent
- Redémarre ton IDE/terminal

## 🚦 CI/CD

Pour intégrer les tests dans un pipeline (GitHub Actions, GitLab CI, etc.) :

```yaml
- name: Run tests
  run: pytest --junit-xml=results.xml --cov=src --cov-report=xml

- name: Upload coverage
  uses: codecov/codecov-action@v3
```

## 📚 Ressources

- [Documentation pytest](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest plugins](https://docs.pytest.org/en/latest/plugins.html)

## Questions ?

Pour toute question sur les tests, consulte :
- `tests/README.md` pour la doc détaillée
- Exemples dans `tests/test_*.py`
