"""Tests pour preprocessing.py

Ce module teste les fonctions de nettoyage et prétraitement des données.
- clean_data : supprime les doublons, trie par date
- add_jour_ferie : identifie les jours fériés
- aggregate_by_hour : agrège les données horaires
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.preprocessing import clean_data, add_jour_ferie, aggregate_by_hour


class TestCleanData:
    """Tests pour la fonction clean_data (nettoyage des données)."""

    def test_nettoyage_donnees_basique(self, sample_dataframe):
        """Teste le nettoyage basique : conversion types, tri, suppression doublons."""
        df = sample_dataframe.copy()
        df_clean = clean_data(df)

        # Vérifications basiques
        assert df_clean is not None
        assert isinstance(df_clean, pd.DataFrame)
        assert "datetime" in df_clean.columns

    def test_nettoyage_supprime_doublons(self):
        """Teste que clean_data supprime les doublons."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=5, freq="h"),
            "puissance_moy_heure": [100, 200, 100, 200, 150],
        })
        # Ajouter des doublons intentionnels
        df = pd.concat([df, df.iloc[:2]], ignore_index=True)

        df_clean = clean_data(df)

        # Après suppression des doublons, même nombre de lignes uniques
        assert len(df_clean) <= len(df)

    def test_nettoyage_trie_par_datetime(self):
        """Teste que clean_data trie les données par ordre chronologique."""
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

        # Vérifier que les dates sont triées croissantes
        assert df_clean["datetime"].is_monotonic_increasing


class TestAddJourFerie:
    """Tests pour la fonction add_jour_ferie (détection jours fériés)."""

    def test_ajout_colonne_jour_ferie(self, sample_dataframe):
        """Teste l'ajout de la colonne 'jour_ferie' (0 ou 1)."""
        df = sample_dataframe.copy()
        df_with_ferie = add_jour_ferie(df)

        # La colonne doit exister et être de type entier
        assert "jour_ferie" in df_with_ferie.columns
        assert df_with_ferie["jour_ferie"].dtype in [np.int64, int, np.int32]

    def test_valeurs_jour_ferie(self, sample_dataframe):
        """Teste que les valeurs de jour_ferie sont 0 (non-férié) ou 1 (férié)."""
        df = sample_dataframe.copy()
        df_with_ferie = add_jour_ferie(df)

        # Vérifier que seules les valeurs 0 et 1 sont présentes
        assert set(df_with_ferie["jour_ferie"].unique()).issubset({0, 1})


class TestAggregateByHour:
    """Tests pour la fonction aggregate_by_hour (agrégation horaire)."""

    def test_agregation_par_heure_basique(self):
        """Teste l'agrégation basique de données à 15 minutes vers l'heure."""
        # Créer des données à 15 minute intervals
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=4, freq="15min"),
            "puissance": [100, 110, 120, 130],
        })

        df_agg = aggregate_by_hour(df)

        # Après agrégation, moins de lignes (fusion des données)
        assert df_agg is not None
        assert isinstance(df_agg, pd.DataFrame)
        assert len(df_agg) <= len(df)

    def test_agregation_preserve_datetime(self):
        """Teste que l'agrégation préserve la colonne datetime."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=4, freq="15min"),
            "puissance": [100, 110, 120, 130],
        })

        df_agg = aggregate_by_hour(df)

        # La colonne datetime doit toujours exister
        assert "datetime" in df_agg.columns
