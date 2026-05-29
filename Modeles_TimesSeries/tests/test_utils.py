"""Tests pour utils.py

Ce module teste les utilitaires génériques du projet :
- load_config : charge le fichier YAML de configuration
- detect_prms : détecte les PRMs (Points de Mesure) dans un répertoire
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.utils import load_config, detect_prms


class TestLoadConfig:
    """Tests pour la fonction load_config (chargement de configuration YAML)."""

    def test_chargement_config_fichier_valide(self, temp_config_file):
        """Teste le chargement d'un fichier de configuration valide."""
        config = load_config(str(temp_config_file))

        # Le fichier doit être chargé en dictionnaire
        assert config is not None
        assert isinstance(config, dict)
        # Les clés spécifiées dans conftest.py doivent être présentes
        assert "target" in config
        assert config["target"] == "puissance_moy_heure"

    def test_structure_config(self, temp_config_file):
        """Teste que la structure du fichier de configuration est complète."""
        config = load_config(str(temp_config_file))

        # Les sections principales doivent exister
        required_keys = ["data", "prophet", "validation", "prediction"]
        for key in required_keys:
            assert key in config, f"Section manquante dans config : {key}"

    def test_chargement_config_fichier_inexistant(self):
        """Teste que charger un fichier inexistant lève FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_config("fichier_inexistant_12345.yaml")


class TestDetectPrms:
    """Tests pour la fonction detect_prms (détection des Points de Mesure)."""

    def test_detection_prms_repertoire_vide(self, data_dir):
        """Teste la détection de PRMs dans un répertoire vide."""
        # Aucun fichier PRM ne doit être détecté
        prms = detect_prms(str(data_dir / "processed"))

        # Le résultat doit être une liste vide ou un dictionnaire vide
        assert isinstance(prms, (list, dict))
        assert len(prms) == 0

    def test_detection_prms_fichiers_exemple(self, tmp_path):
        """Teste la détection de PRMs avec des fichiers d'exemple."""
        # Créer un fichier CSV factice avec un numéro PRM
        (tmp_path / "dataclean_prm_12345.csv").touch()

        prms = detect_prms(tmp_path)

        # Le résultat doit être un dictionnaire {prm: Path}
        assert isinstance(prms, dict)
        # La clé doit être le numéro PRM
        assert "12345" in prms
        # La valeur doit être le chemin du fichier
        assert prms["12345"].name == "dataclean_prm_12345.csv"
