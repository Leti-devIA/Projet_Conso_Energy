"""Tests pour data_loader.py

Ce module teste les fonctions de chargement de données (CSV, base de données, API).
Certains tests peuvent être sautés en CI si les données ne sont pas disponibles.
"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.data_loader import get_data_loader


class TestGetDataLoader:
    """Tests pour la création et l'initialisation d'un DataLoader."""

    def test_creation_dataloader_csv(self, temp_config_file):
        """Teste la création d'un DataLoader au format CSV.

        Vérifie que le loader est instancié correctement et
        possède les méthodes attendues.
        """
        loader = get_data_loader("csv", str(temp_config_file))

        assert loader is not None
        assert hasattr(loader, "load_dataclean")
        assert hasattr(loader, "load_processed_site_data")

    def test_creation_dataloader_source_invalide(self, temp_config_file):
        """Teste que la création d'un DataLoader avec source invalide lève une exception.

        Les sources valides sont limitées : 'csv', 'api', 'db'.
        Une source inconnue doit être rejetée.
        """
        with pytest.raises((ValueError, KeyError, Exception)):
            get_data_loader("invalid_source", str(temp_config_file))


class TestDataLoaderInterface:
    """Tests pour l'interface et les méthodes du DataLoader.

    Un DataLoader valide doit implémenter un ensemble de méthodes
    pour charger, traiter et sauvegarder les données.
    """

    def test_loader_possede_methodes_requises(self, temp_config_file):
        """Teste que le loader possède toutes les méthodes requises.

        Les méthodes obligatoires : load_dataclean, load_processed_site_data,
        save_processed_site_data.
        """
        loader = get_data_loader("csv", str(temp_config_file))

        # Méthodes obligatoires que tout DataLoader doit implémenter
        required_methods = [
            "load_dataclean",           # Charger les données brutes nettoyées
            "load_processed_site_data", # Charger les données traitées pour un site
            "save_processed_site_data", # Sauvegarder les données traitées
        ]

        # Vérifier que chaque méthode existe
        for method_name in required_methods:
            assert hasattr(loader, method_name), f"Méthode manquante : {method_name}"
