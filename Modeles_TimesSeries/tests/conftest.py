"""Fixtures pytest réutilisables pour tous les tests."""
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from datetime import datetime, timedelta
import yaml
import sys

# Ajouter src au path pour les imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Exclure les patterns avancés du run par défaut (fichier pédagogique)
collect_ignore = ["test_patterns_advanced.py"]


@pytest.fixture
def sample_dates():
    """Crée une série de dates de test."""
    start = datetime(2023, 1, 1)
    dates = pd.date_range(start=start, periods=365, freq="D")
    return dates


@pytest.fixture
def sample_dataframe(sample_dates):
    """Crée un DataFrame de test avec données de consommation."""
    np.random.seed(42)
    df = pd.DataFrame({
        "datetime": pd.date_range(start=datetime(2023, 1, 1), periods=100, freq="h"),  # "H" → "h"
        "puissance_moy_heure": np.random.uniform(100, 500, 100),
        "temperature": np.random.uniform(-5, 30, 100),
        "humidite": np.random.uniform(30, 90, 100),
        "prm": "30000250086126",
    })
    return df


@pytest.fixture
def sample_config():
    """Crée une configuration de test."""
    config = {
        "target": "puissance_moy_heure",
        "data": {
            "raw": "data/raw",
            "processed": "data/processed",
            "predictions": "data/predictions",
        },
        "prophet": {
            "seasonality_mode": "additive",
            "yearly_seasonality": False,
            "weekly_seasonality": False,
            "daily_seasonality": False,
            "fourier_order_daily": 10,
            "fourier_order_weekly": 5,
            "fourier_order_yearly": 10,
            "changepoint_prior_scale": 0.005,
            "seasonality_prior_scale": 10.0,
            "regressors": [
                "temperature",
                "humidite",
                "precipitation",
                "couverture_nuages",
                "vitesse_vent",
                "is_holiday",
                "heure_sin",
                "heure_cos",
                "jour_sin",
                "jour_cos",
                "is_weekend",
            ],
        },
        "validation": {"days": 120},
        "prediction": {"horizon": 8784, "clip_negative": True},
        "mlflow": {"enabled": False},
    }
    return config


@pytest.fixture
def temp_config_file(sample_config, tmp_path):
    """Crée un fichier de configuration temporaire."""
    config_path = tmp_path / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(sample_config, f)
    return config_path


@pytest.fixture
def sample_prophet_data():
    """Crée un DataFrame au format attendu par Prophet."""
    dates = pd.date_range(start=datetime(2023, 1, 1), periods=365, freq="D")
    np.random.seed(42)
    df = pd.DataFrame({
        "ds": dates,
        "y": 100 + 50 * np.sin(np.arange(365) * 2 * np.pi / 365) + np.random.normal(0, 5, 365),
    })
    return df


@pytest.fixture
def data_dir(tmp_path):
    """Crée une structure de répertoires temporaire pour les données."""
    (tmp_path / "processed").mkdir()
    (tmp_path / "raw").mkdir()
    (tmp_path / "predictions").mkdir()
    return tmp_path
