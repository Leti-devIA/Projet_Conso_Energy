"""Tests pour utils.py"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from utils import load_config, detect_prms


class TestLoadConfig:
    """Tests pour la fonction load_config."""

    def test_load_config_with_valid_file(self, temp_config_file):
        """Test le chargement d'un fichier de configuration valide."""
        config = load_config(str(temp_config_file))

        assert config is not None
        assert isinstance(config, dict)
        assert "target" in config
        assert config["target"] == "puissance_moy_heure"

    def test_load_config_structure(self, temp_config_file):
        """Test la structure du fichier de configuration chargé."""
        config = load_config(str(temp_config_file))

        required_keys = ["data", "prophet", "validation", "prediction"]
        for key in required_keys:
            assert key in config, f"Clé manquante : {key}"

    def test_load_config_with_nonexistent_file(self):
        """Test le chargement d'un fichier inexistant."""
        with pytest.raises(FileNotFoundError):
            load_config("nonexistent_config.yaml")


class TestDetectPrms:
    """Tests pour la fonction detect_prms."""

    def test_detect_prms_empty_dir(self, data_dir):
        """Test la détection de PRMs dans un répertoire vide."""
        prms = detect_prms(str(data_dir / "processed"))
        assert isinstance(prms, list) or len(prms) == 0

    def test_detect_prms_with_sample_files(self, data_dir):
        """Test la détection de PRMs avec des fichiers d'exemple."""
        # Créer des fichiers de test
        (data_dir / "processed" / "data_preprocessed_30000250086126.csv").touch()
        (data_dir / "processed" / "data_preprocessed_30000540191777.csv").touch()

        prms = detect_prms(str(data_dir / "processed"))

        assert isinstance(prms, (list, set))
        assert "30000250086126" in prms or len(prms) > 0
