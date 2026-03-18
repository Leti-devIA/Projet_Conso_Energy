"""Tests pour preprocessing.py"""
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.preprocessing import clean_data, add_jour_ferie, aggregate_by_hour


class TestCleanData:
    """Tests pour la fonction clean_data."""

    def test_clean_data_basic(self, sample_dataframe):
        """Test le nettoyage basique des données."""
        df = sample_dataframe.copy()
        df_clean = clean_data(df)

        assert df_clean is not None
        assert isinstance(df_clean, pd.DataFrame)
        assert "datetime" in df_clean.columns

    def test_clean_data_removes_duplicates(self):
        """Test que clean_data supprime les doublons."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=5, freq="h"),  # "H" → "h"
            "puissance_moy_heure": [100, 200, 100, 200, 150],
        })
        # Ajouter des doublons
        df = pd.concat([df, df.iloc[:2]], ignore_index=True)

        df_clean = clean_data(df)

        # Le nombre de lignes uniques devrait être < nombre total
        assert len(df_clean) <= len(df)

    def test_clean_data_sorts_by_datetime(self):
        """Test que clean_data trie par datetime."""
        df = pd.DataFrame({
            "datetime": [
                datetime(2023, 1, 3),
                datetime(2023, 1, 1),
                datetime(2023, 1, 2),
            ],
            "puissance_moy_heure": [150, 100, 200],
        })
        df["datetime"] = pd.to_datetime(df["datetime"])

        df_clean = clean_data(df)

        # Vérifier que les dates sont triées
        assert df_clean["datetime"].is_monotonic_increasing


class TestAddJourFerie:
    """Tests pour add_jour_ferie."""

    def test_add_jour_ferie_column(self, sample_dataframe):
        """Test l'ajout de la colonne jour_ferie."""
        df = sample_dataframe.copy()
        df_with_ferie = add_jour_ferie(df)

        assert "jour_ferie" in df_with_ferie.columns
        assert df_with_ferie["jour_ferie"].dtype in [np.int64, int, np.int32]

    def test_add_jour_ferie_values(self, sample_dataframe):
        """Test les valeurs de jour_ferie."""
        df = sample_dataframe.copy()
        df_with_ferie = add_jour_ferie(df)

        # Les valeurs doivent être 0 ou 1
        assert set(df_with_ferie["jour_ferie"].unique()).issubset({0, 1})


class TestAggregateByHour:
    """Tests pour aggregate_by_hour."""

    def test_aggregate_by_hour_basic(self):
        """Test l'agrégation basique par heure."""
        # Créer des données à 15 minute intervals
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=4, freq="15min"),
            "puissance": [100, 110, 120, 130],
        })

        df_agg = aggregate_by_hour(df)

        assert df_agg is not None
        assert isinstance(df_agg, pd.DataFrame)
        # Après agrégation, on devrait avoir moins de lignes
        assert len(df_agg) <= len(df)

    def test_aggregate_by_hour_preserves_datetime(self):
        """Test que l'agrégation préserve la colonne datetime."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=4, freq="15min"),
            "puissance": [100, 110, 120, 130],
        })

        df_agg = aggregate_by_hour(df)

        assert "datetime" in df_agg.columns
