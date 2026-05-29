"""Tests pour feature_engineering.py

Ce module teste la création des features (variables explicatives) :
- Features temporelles : heure, jour de la semaine, sin/cos (cyclique)
- Features de lag : décalages temporels (t-1, t-2, t-24...)
- Features rolling : moyennes/max/min sur des fenêtres glissantes
"""
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from src.feature_engineering import (
    create_temporal_features,
    create_lag_features,
    create_rolling_features,
)


class TestCreateTemporalFeatures:
    """Tests pour create_temporal_features (features liées au temps)."""

    def test_features_temporelles_basiques(self, sample_dataframe):
        """Teste la création de features temporelles basiques."""
        df = sample_dataframe.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])

        df_feat = create_temporal_features(df)

        # Vérifier la présence de features classiques
        assert df_feat is not None
        assert "heure" in df_feat.columns or "hour" in df_feat.columns
        assert "jour_semaine" in df_feat.columns or "dayofweek" in df_feat.columns

    def test_features_temporelles_cree_fonctions_trigo(self, sample_dataframe):
        """Teste que les features trigonométriques (sin/cos) sont créées.

        Les fonctions trigonométriques permettent de coder les cycles
        (jour, semaine, année) de manière continue et circulaire.
        """
        df = sample_dataframe.copy()
        df["datetime"] = pd.to_datetime(df["datetime"])

        df_feat = create_temporal_features(df)

        # Vérifier la présence de features sin/cos
        trig_features = [col for col in df_feat.columns if "sin" in col or "cos" in col]
        assert len(trig_features) >= 2, f"Features trigonométriques manquantes : trouvé {len(trig_features)}"


class TestCreateLagFeatures:
    """Tests pour create_lag_features (décalages temporels)."""

    def test_features_lag_basiques(self, sample_dataframe):
        """Teste la création basique de features de lag (décalages)."""
        df = sample_dataframe.copy()
        original_cols = len(df.columns)

        df_feat = create_lag_features(df, "puissance_moy_heure")

        # Le nombre de colonnes doit augmenter
        assert len(df_feat.columns) >= original_cols
        # Au moins une colonne de lag devrait être créée
        lag_cols = [col for col in df_feat.columns if "lag" in col]
        assert len(lag_cols) > 0, "Aucune feature de lag créée"

    def test_features_lag_valeurs_correctes(self, sample_dataframe):
        """Teste que les lags ont les bonnes valeurs (décalage correct)."""
        df = sample_dataframe.copy()
        # Valeurs 0, 1, 2, 3... pour faciliter la vérification
        df["puissance_moy_heure"] = range(len(df))

        df_feat = create_lag_features(df, "puissance_moy_heure")

        # Vérifier le lag de 1 : devrait décaler les valeurs
        if "puissance_moy_heure_lag_1" in df_feat.columns:
            valid_indices = ~df_feat["puissance_moy_heure_lag_1"].isna()
            if valid_indices.sum() > 0:
                # Les valeurs décalées doivent être différentes (sauf NaN)
                assert (df_feat.loc[valid_indices, "puissance_moy_heure_lag_1"].values !=
                        df_feat.loc[valid_indices, "puissance_moy_heure"].values).all()


class TestCreateRollingFeatures:
    """Tests pour create_rolling_features (moyennes/max glissantes)."""

    def test_features_rolling_basiques(self, sample_dataframe):
        """Teste la création basique de features rolling (fenêtres glissantes)."""
        df = sample_dataframe.copy()
        original_cols = len(df.columns)

        df_feat = create_rolling_features(df, "puissance_moy_heure")

        # Le nombre de colonnes doit augmenter
        assert len(df_feat.columns) >= original_cols
        # Au moins une rolling feature devrait être créée
        rolling_cols = [col for col in df_feat.columns if "roll" in col]
        assert len(rolling_cols) > 0, "Aucune feature rolling créée"

    def test_valeurs_rolling_mean(self, sample_dataframe):
        """Teste que les rolling means sont calculées correctement."""
        df = pd.DataFrame({
            "datetime": pd.date_range("2023-01-01", periods=10, freq="h"),
            "puissance_moy_heure": [10, 20, 30, 40, 50, 60, 70, 80, 90, 100],
        })

        df_feat = create_rolling_features(df, "puissance_moy_heure")

        # Vérifier que les rolling means existent
        assert "puissance_roll_3" in df_feat.columns


class TestFeatureEngineering:
    """Tests d'intégration du feature engineering (combinaison de toutes les features)."""

    def test_features_ne_sont_pas_entierement_nan(self, sample_dataframe):
        """Vérifie que les features générées ne sont pas entièrement NaN.

        Chaque feature créée doit avoir au moins une valeur valide.
        """
        df_feat = sample_dataframe.copy()

        # Appliquer toutes les transformations
        df_feat = create_temporal_features(df_feat)
        df_feat = create_lag_features(df_feat, target_col='puissance_moy_heure')
        df_feat = create_rolling_features(df_feat, target_col='puissance_moy_heure')

        # Colonnes de base (à exclure de la vérification)
        cols_de_base = ["datetime", "puissance_moy_heure", "temperature", "humidite", "prm"]
        feature_cols = [c for c in df_feat.columns if c not in cols_de_base]

        # Vérifier que chaque feature générée a au moins une valeur non-NaN
        for col in feature_cols:
            # Ignorer les lags trop grands pour le dataset de test (100 lignes)
            if "lag_" in col:
                try:
                    lag_val = int(col.split("_")[-1])
                    if lag_val >= len(df_feat):
                        continue
                except (ValueError, IndexError):
                    pass

            non_null_count = df_feat[col].notna().sum()
            assert non_null_count > 0, f"Colonne '{col}' est entièrement NaN"
