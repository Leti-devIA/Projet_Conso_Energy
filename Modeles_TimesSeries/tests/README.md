# Tests (version simple)

Objectif : avoir des tests faciles à lancer et à comprendre.

## Ce qui est testé

- `test_utils.py` : config + détection PRM
- `test_data_loader.py` : chargement des données
- `test_preprocessing.py` : nettoyage / agrégation
- `test_feature_engineering.py` : création des features

Le fichier `test_patterns_advanced.py` est **pédagogique** et n'est pas exécuté par défaut.

## Lancer les tests

Depuis `Modeles_TimesSeries/` :

```bash
pytest
```

Tester un seul fichier :

```bash
pytest tests/test_utils.py
```

Tester une seule fonction :

```bash
pytest tests/test_utils.py::TestLoadConfig::test_load_config_with_valid_file
```

## Règle simple pour écrire un bon test

1. Préparer les données
2. Appeler la fonction
3. Vérifier un résultat clair avec `assert`

Exemple minimal :

```python
def test_exemple_simple():
    valeur = 2 * 3
    assert valeur == 6
```

## Si un test échoue

- Lire d'abord le nom du test qui échoue
- Corriger le code (ou le test si l'attendu est faux)
- Relancer uniquement ce test

Commande utile :

```bash
pytest -x
```

(`-x` arrête à la première erreur, pratique au début.)
