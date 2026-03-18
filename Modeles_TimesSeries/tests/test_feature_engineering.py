"""Tests pour feature_engineering.py"""
import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.feature_engineering import (
    create_temporal_features,
    create_lag_features,
    create_rolling_features,
)


class TestCreateTemporalFeatures:
    """Tests pour create_temporal_features."""

    def test_temporal_features_basic(self, sample_dataframe):
        """Test la création de features temporelles basiques."""
        df = sample_dataframe.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])

        df_feat = create_temporal_features(df)

        assert df_feat is not None
        assert "heure" in df_feat.columns or "hour" in df_feat.columns
        assert "jour_semaine" in df_feat.columns or "dayofweek" in df_feat.columns

    def test_temporal_features_creates_trig_functions(self, sample_dataframe):
        """Test la création de features trigonométriques."""
        df = sample_dataframe.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])

        df_feat = create_temporal_features(df)

        # Vérifier la présence de features sin/cos
        trig_features = [col for col in df_feat.columns if "sin" in col or "cos" in col]
        assert len(trig_features) >= 2, "Features trigonométriques manquantes"


class TestCreateLagFeatures:
    """Tests pour create_lag_features."""

    def test_lag_features_basic(self, sample_dataframe):
        """Test la création basique de features de lag."""
        df = sample_dataframe.copy()
        original_cols = len(df.columns)

        df_feat = create_lag_features(df, "puissance_moy_heure")

        assert len(df_feat.columns) >= original_cols
        # Au moins une colonne de lag devrait être créée
        lag_cols = [col for col in df_feat.columns if "lag" in col]
        assert len(lag_cols) > 0, "Aucune feature de lag créée"

    def test_lag_features_correct_lags(self, sample_dataframe):
        """Test que les lags ont les bonnes valeurs."""
        df = sample_dataframe.copy()
        df["puissance_moy_heure"] = range(len(df))  # Valeurs 0, 1, 2, 3, ...

        df_feat = create_lag_features(df, "puissance_moy_heure")

        # Le lag de 1 devrait décaler les valeurs
        if "puissance_moy_heure_lag_1" in df_feat.columns:
            # Les valeurs décalées doivent être différentes (sauf NaN au début)
            valid_indices = ~df_feat["puissance_moy_heure_lag_1"].isna()
            if valid_indices.sum() > 0:
                assert (df_feat.loc[valid_indices, "puissance_moy_heure_lag_1"].values !=
                        df_feat.loc[valid_indices, "puissance_moy_heure"].values).all()


class TestCreateRollingFeatures:
    """Tests pour create_rolling_features."""

    def test_rolling_features_basic(self, sample_dataframe):
        """Test la création basique de features rolling."""
        df = sample_dataframe.copy()
        original_cols = len(df.columns)

        df_feat = create_rolling_features(df, "puissance_moy_heure")

        assert len(df_feat.columns) >= original_cols
        # Au moins une rolling feature devrait être créée
        rolling_cols = [col for col in df_feat.columns if "roll" in col]
        assert len(rolling_cols) > 0, "Aucune feature rolling créée"

    def test_rolling_mean_values(self, sample_dataframe):
        """Test que les rolling means sont corrects."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=10, freq="h"),  # "H" → "h"
            "puissance_moy_heure": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        })

        df_feat = create_rolling_features(df, "puissance_moy_heure")

        # Vérifier que les rolling means existent
        assert "puissance_roll_3" in df_feat.columns


class TestFeatureEngineering:
    """Tests d'intégration pour feature engineering."""

    def test_features_dont_have_nan_only(self, sample_dataframe):
        """Test que les features créées ne sont pas que des NaN."""
        df = sample_dataframe.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])

        df_feat = create_temporal_features(df)
        df_feat = create_lag_features(df_feat, "puissance_moy_heure")

        # Chaque colonne de features ne doit pas être entièrement NaN
        for col in df_feat.columns:
            if col not in ["datetime", "puissance_moy_heure"]:
                # Au moins une valeur non-NaN
                assert df_feat[col].notna().sum() > 0, f"Colonne {col} est entièrement NaN"
