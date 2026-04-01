"""
Patterns avancés de test avec pytest.

Ce fichier sert de référence pour les patterns courants en testing.
"""

import pytest
import pandas as pd
import numpy as np


# =====================================================================
# PATTERN 1 : Parameterized Tests
# =====================================================================
class TestParameterized:
    """Tests paramétrés - tester plusieurs cas avec une fonction."""

    @pytest.mark.parametrize("input_val,expected", [
        (5, 10),
        (3, 6),
        (0, 0),
        (-5, -10),
    ])
    def test_double_number(self, input_val, expected):
        """Teste la fonction double pour plusieurs valeurs."""
        result = input_val * 2
        assert result == expected

    # Tester plusieurs valeurs de fixture
    @pytest.mark.parametrize("prm", [
        "30000250086126",
        "30000540191777",
        "30000650805048",
    ])
    def test_load_different_sites(self, prm):
        """Teste le chargement pour plusieurs sites."""
        # Ton code de test ici
        assert len(prm) > 0


# =====================================================================
# PATTERN 2 : Test avec marker personnalisé
# =====================================================================
@pytest.mark.slow
def test_slow_operation():
    """Ce test est marqué comme 'slow'."""
    # Pour l'exécuter : pytest -m slow
    # Pour l'éviter   : pytest -m "not slow"
    import time
    time.sleep(0.1)
    assert True


@pytest.mark.requires_data
def test_with_actual_data():
    """Ce test nécessite les vrais fichiers de données."""
    # Pour l'exécuter : pytest -m requires_data
    pass


# =====================================================================
# PATTERN 3 : Test avec setup et teardown
# =====================================================================
class TestWithSetupTeardown:
    """Tests avec préparation et nettoyage."""

    @classmethod
    def setup_class(cls):
        """Exécuté une fois avant tous les tests de la classe."""
        print("\n📋 Setup: Préparation des ressources")
        cls.expensive_resource = "Resource coûteux à créer"

    @classmethod
    def teardown_class(cls):
        """Exécuté une fois après tous les tests de la classe."""
        print("\n🧹 Teardown: Nettoyage")
        cls.expensive_resource = None

    def setup_method(self):
        """Exécuté avant chaque test."""
        self.temp_data = [1, 2, 3]

    def teardown_method(self):
        """Exécuté après chaque test."""
        self.temp_data = None

    def test_with_resource(self):
        """Test utilisant la ressource setup."""
        assert self.expensive_resource is not None
        assert self.temp_data == [1, 2, 3]


# =====================================================================
# PATTERN 4 : Test d'exception avec pytest.raises
# =====================================================================
class TestExceptions:
    """Tester que les erreurs sont levées correctement."""

    def test_raises_specific_exception(self):
        """Test qu'une exception spécifique est levée."""
        with pytest.raises(ValueError):
            int("not_a_number")

    def test_exception_message(self):
        """Test le message d'exception."""
        with pytest.raises(ValueError, match="invalid literal"):
            int("not_a_number")

    def test_no_exception_raised(self):
        """Test qu'aucune exception n'est levée."""
        with pytest.raises(ValueError) as exc_info:
            raise ValueError("Expected error")

        # Accéder aux détails de l'exception
        assert "Expected error" in str(exc_info.value)


# =====================================================================
# PATTERN 5 : Fixture avec paramètres
# =====================================================================
@pytest.fixture(params=[10, 20, 30])
def parametrized_fixture(request):
    """Fixture qui crée plusieurs valeurs."""
    return request.param


def test_with_parametrized_fixture(parametrized_fixture):
    """Ce test sera exécuté 3 fois avec 10, 20, 30."""
    assert parametrized_fixture > 0


# =====================================================================
# PATTERN 6 : Fixtures avec scope
# =====================================================================
@pytest.fixture(scope="session")  # Partagé pour toute la session
def session_data():
    """Créé une fois pour toute la session de test."""
    return {"data": "expensive to create"}


@pytest.fixture(scope="module")   # Partagé pour un module
def module_data():
    """Créé une fois par module de test."""
    return {"module": "data"}


@pytest.fixture(scope="function")  # Créé pour chaque test (défaut)
def function_data():
    """Créé pour chaque fonction de test."""
    return {"function": "data"}


def test_scope_example(session_data, module_data, function_data):
    """Utilise des fixtures avec différents scopes."""
    assert session_data["data"] == "expensive to create"
    assert module_data["module"] == "data"
    assert function_data["function"] == "data"


# =====================================================================
# PATTERN 7 : Fixture avec autouse (utilisée automatiquement)
# =====================================================================
@pytest.fixture(autouse=True)
def auto_fixture():
    """Cette fixture est utilisée automatiquement par tous les tests."""
    print("\n🔄 Setup automatique")
    yield
    print("\n🔄 Teardown automatique")


# =====================================================================
# PATTERN 8 : Test avec mock (nécessite pytest-mock)
# =====================================================================
def test_mock_example(mocker):
    """Test avec mocking (nécessite pytest-mock : pip install pytest-mock)."""
    # Mock une fonction
    mock_func = mocker.patch("builtins.open", mocker.mock_open(read_data="test data"))

    # Utilise la fonction mockée
    with open("fake_file.txt") as f:
        content = f.read()

    # Vérifie que le mock a été appelé
    assert content == "test data"
    mock_func.assert_called_once_with("fake_file.txt")


# =====================================================================
# PATTERN 9 : Test avec approx pour float
# =====================================================================
def test_float_comparison():
    """Tester les floats avec approximation."""
    result = 0.1 + 0.2

    # ❌ Mauvais : peut échouer avec erreurs de précision
    # assert result == 0.3

    # ✅ Bon : utilise pytest.approx
    assert result == pytest.approx(0.3)
    assert result == pytest.approx(0.3, abs=1e-10)  # Précision absolue
    assert result == pytest.approx(0.3, rel=1e-3)   # Précision relative


# =====================================================================
# PATTERN 10 : Test d'assertion multiple
# =====================================================================
class TestMultipleAssertions:
    """Plusieurs assertions dans un même test."""

    def test_multiple_conditions(self):
        """Tester plusieurs conditions."""
        result = {"name": "John", "age": 30, "email": "john@example.com"}

        # Plusieurs assertions
        assert result["name"] == "John"
        assert result["age"] == 30
        assert "email" in result
        assert len(result) == 3

    def test_with_context_manager(self):
        """Utiliser pytest.warns pour tester les warnings."""
        # Cette syntaxe montre comment tester les warnings
        import warnings

        with pytest.warns(UserWarning):
            warnings.warn("Test warning", UserWarning)


# =====================================================================
# PATTERN 11 : Conditional skip
# =====================================================================
import sys

@pytest.mark.skipif(sys.version_info < (3, 10), reason="Python 3.10+ required")
def test_python310_feature():
    """Ce test est skippé si Python < 3.10."""
    pass


@pytest.mark.skipif(
    not any(["tensorflow" in str(p) for p in __import__("sys").path]),
    reason="TensorFlow not available"
)
def test_requires_tensorflow():
    """Ce test est skippé si TensorFlow n'est pas installé."""
    pass


# =====================================================================
# PATTERN 12 : xfail (expected to fail)
# =====================================================================
@pytest.mark.xfail(reason="Bug connu - voir issue #123")
def test_known_bug():
    """Ce test devrait échouer. Si ça passe, pytest le signalera."""
    assert 1 == 2  # Volontairement faux


@pytest.mark.xfail(strict=True)
def test_should_fail_strictly():
    """Ce test doit échouer. S'il passe, c'est une erreur."""
    assert False


# =====================================================================
# PATTERN 13 : Utiliser contexte pour cleanup
# =====================================================================
@pytest.fixture
def fixture_with_context():
    """Fixture avec gestion de contexte pour cleanup garantie."""
    import tempfile
    from contextlib import contextmanager

    @contextmanager
    def temp_dir():
        tmpdir = tempfile.mkdtemp()
        yield tmpdir
        # Cleanup automatique
        import shutil
        shutil.rmtree(tmpdir)

    with temp_dir() as tmpdir:
        yield tmpdir


# =====================================================================
# PATTERN 14 : Test avec DataFrame pandas
# =====================================================================
class TestDataFrameOperations:
    """Tests spécifiques pour pandas DataFrames."""

    def test_dataframe_equality(self):
        """Tester l'égalité de DataFrames."""
        df1 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
        df2 = pd.DataFrame({"A": [1, 2], "B": [3, 4]})

        # Utiliser assert_frame_equal pour une comparaison robuste
        pd.testing.assert_frame_equal(df1, df2)

    def test_dataframe_nan_values(self):
        """Tester les DataFrames avec NaN."""
        df = pd.DataFrame({"A": [1, np.nan, 3]})

        # Vérifier les NaN
        assert df["A"].isna().sum() == 1
        pd.testing.assert_frame_equal(
            df,
            pd.DataFrame({"A": [1.0, np.nan, 3.0]})
        )

    def test_series_values(self):
        """Tester les Series pandas."""
        s = pd.Series([1, 2, 3, 4, 5])

        assert len(s) == 5
        assert s.sum() == 15
        pd.testing.assert_series_equal(s, pd.Series([1, 2, 3, 4, 5]))


# =====================================================================
# PATTERN 15 : Test performance
# =====================================================================
@pytest.mark.slow
def test_performance_with_timeout():
    """Test que le code termine en moins d'une seconde."""
    import time

    # Importe pytest-timeout : pip install pytest-timeout
    # ajoute à pytest.ini : timeout = 1
    result = sum(range(1000))
    assert result > 0
