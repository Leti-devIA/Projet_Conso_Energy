"""Tests pour data_loader.py"""
import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from data_loader import get_data_loader


class TestGetDataLoader:
    """Tests pour get_data_loader."""

    def test_get_data_loader_csv(self, temp_config_file):
        """Test la création d'un DataLoader CSV."""
        loader = get_data_loader("csv", str(temp_config_file))

        assert loader is not None
        assert hasattr(loader, "load_dataclean")
        assert hasattr(loader, "load_processed_site_data")

    def test_get_data_loader_invalid_source(self, temp_config_file):
        """Test la création d'un DataLoader avec source invalide."""
        with pytest.raises((ValueError, KeyError, Exception)):
            get_data_loader("invalid_source", str(temp_config_file))


class TestDataLoaderInterface:
    """Tests pour l'interface DataLoader."""

    def test_loader_has_required_methods(self, temp_config_file):
        """Test que le loader a les méthodes requises."""
        loader = get_data_loader("csv", str(temp_config_file))

        required_methods = [
            "load_dataclean",
            "load_processed_site_data",
            "save_processed_site_data",
        ]

        for method_name in required_methods:
            assert hasattr(loader, method_name), f"Méthode manquante : {method_name}"
