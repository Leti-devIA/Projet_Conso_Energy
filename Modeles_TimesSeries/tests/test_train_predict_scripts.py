"""Tests pour les scripts `train.py` et `predict.py`.

Les tests restent unitaires et utilisent des objets factices pour éviter
de lancer un vrai entraînement Prophet.
"""

from types import SimpleNamespace
from pathlib import Path
import json
import pickle

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("prophet")

from src import predict as predict_mod
from src import train as train_mod


class FakeProphetModel:
    """Modèle Prophet factice pour les tests."""

    def __init__(self, **kwargs):
        self.init_kwargs = kwargs
        self.extra_regressors = {}
        self.seasonalities = {}
        self.growth = kwargs.get("growth", "linear")
        self.seasonality_mode = kwargs.get("seasonality_mode", "additive")
        self.changepoint_prior_scale = kwargs.get("changepoint_prior_scale", 0.05)
        self.seasonality_prior_scale = kwargs.get("seasonality_prior_scale", 10.0)
        self.holidays_prior_scale = kwargs.get("holidays_prior_scale", 10.0)
        self.n_changepoints = kwargs.get("n_changepoints", 25)
        self.changepoint_range = kwargs.get("changepoint_range", 0.8)

    def add_seasonality(self, name, period, fourier_order):
        self.seasonalities[name] = {
            "period": period,
            "fourier_order": fourier_order,
        }

    def add_regressor(self, name, standardize=False):
        self.extra_regressors[name] = {"standardize": standardize}

    def fit(self, df, algorithm=None, **kwargs):
        self.fitted_df = df.copy()
        self.fit_kwargs = {"algorithm": algorithm, **kwargs}
        return self

    def predict(self, df):
        n_rows = len(df)
        return pd.DataFrame(
            {
                "ds": df["ds"].values,
                "yhat": np.linspace(-10, 10, n_rows),
                "yhat_lower": np.linspace(-20, 0, n_rows),
                "yhat_upper": np.linspace(0, 20, n_rows),
            }
        )


def _make_history_df(hours=240):
    """Crée un historique horaire simple pour les tests."""
    dates = pd.date_range("2024-01-01", periods=hours, freq="h")
    df = pd.DataFrame(
        {
            "datetime": dates,
            "puissance_moy_heure": 100 + np.arange(hours, dtype=float),
            "temperature": np.linspace(5, 15, hours),
            "humidite": np.linspace(40, 60, hours),
            "cap": 1000.0,
            "floor": 0.0,
        }
    )
    df["heure_sin"] = np.sin(2 * np.pi * df["datetime"].dt.hour / 24)
    df["heure_cos"] = np.cos(2 * np.pi * df["datetime"].dt.hour / 24)
    return df


def _make_future_meteo_df(start_dt, hours=3):
    """Crée une météo future minimale pour les tests."""
    dates = pd.date_range(start_dt, periods=hours, freq="h")
    return pd.DataFrame(
        {
            "datetime": dates,
            "temperature": [7.0, 8.0, 9.0][:hours],
            "humidite": [50.0, 51.0, 52.0][:hours],
        }
    )


def test_prepare_data_for_prophet_scales_and_filters():
    """Le format Prophet doit être nettoyé et filtré correctement."""
    df = pd.DataFrame(
        {
            "datetime": pd.date_range("2024-01-01", periods=4, freq="h"),
            "puissance_moy_heure": [0.5, 1.2, np.nan, 3.4],
            "temperature": [10.0, 11.0, 12.0, 13.0],
            "humidite": [50.0, 51.0, 52.0, 53.0],
            "is_weekend": [0, 0, 0, 0],
        }
    )
    config = {
        "prophet": {
            "regressors": ["temperature", "humidite", "is_weekend", "missing_regressor"],
            "filter_low_values": {"enabled": True, "threshold_kw": 1000},
        }
    }

    result = train_mod.prepare_data_for_prophet(
        df,
        target_col="puissance_moy_heure",
        config=config,
    )

    assert list(result.columns) == ["ds", "y", "temperature", "humidite", "is_weekend"]
    assert result["y"].tolist() == [1200.0, 3400.0]
    assert result["ds"].dtype.kind == "M"


def test_build_prophet_model_applies_site_overrides(monkeypatch):
    """Les paramètres du site doivent surcharger la config globale."""
    monkeypatch.setattr(train_mod, "Prophet", FakeProphetModel)

    config = {
        "prophet": {
            "growth": "linear",
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.01,
            "seasonality_prior_scale": 10.0,
            "holidays_prior_scale": 10.0,
            "n_changepoints": 25,
            "changepoint_range": 0.8,
        },
        "site_overrides": {
            "30000250086126": {
                "growth": "logistic",
                "seasonality_mode": "multiplicative",
                "changepoint_prior_scale": 0.2,
                "daily_fourier_order": 12,
                "weekly_fourier_order": 6,
                "yearly_fourier_order": 8,
            }
        },
    }

    model = train_mod.build_prophet_model(config, prm="30000250086126")

    assert model.growth == "logistic"
    assert model.seasonality_mode == "multiplicative"
    assert model.changepoint_prior_scale == 0.2
    assert model.seasonalities["daily"]["fourier_order"] == 12
    assert model.seasonalities["weekly"]["fourier_order"] == 6
    assert model.seasonalities["yearly"]["fourier_order"] == 8


def test_save_model_creates_expected_files(tmp_path):
    """La sauvegarde doit produire le modèle et le JSON de métriques."""
    model = SimpleNamespace(
        extra_regressors={"temperature": {}, "humidite": {}},
        seasonality_mode="additive",
        growth="linear",
        changepoint_prior_scale=0.01,
        seasonality_prior_scale=10.0,
        holidays_prior_scale=10.0,
        n_changepoints=25,
        changepoint_range=0.8,
        seasonalities={
            "daily": {"fourier_order": 10},
            "weekly": {"fourier_order": 5},
            "yearly": {"fourier_order": 8},
        },
    )
    config = {"models": {"save_dir": str(tmp_path)}}
    metrics = {"mae": 1.0, "rmse": 2.0, "mape": 3.0, "wape": 4.0, "r2": 0.5}

    train_mod.save_model(model, config, metrics, prm="30000250086126")

    model_file = tmp_path / "prophet_model_30000250086126_latest.pkl"
    metrics_file = tmp_path / "prophet_metrics_30000250086126.json"

    assert model_file.exists()
    assert metrics_file.exists()

    payload = json.loads(metrics_file.read_text(encoding="utf-8"))
    assert payload["prm"] == "30000250086126"
    assert payload["metrics"]["mae"] == 1.0
    assert payload["regressors"] == ["temperature", "humidite"]


def test_train_one_site_orchestration(monkeypatch, tmp_path):
    """Le pipeline d'entraînement doit appeler les bonnes briques."""
    history_df = _make_history_df(hours=800)
    base_config = {
        "target": "puissance_moy_heure",
        "validation": {"days": 2},
        "prophet": {
            "regressors": ["temperature", "humidite"],
            "seasonality_mode": "additive",
            "changepoint_prior_scale": 0.01,
            "seasonality_prior_scale": 10.0,
        },
        "models": {"save_dir": str(tmp_path)},
        "mlflow": {"enabled": False},
    }

    fake_model = FakeProphetModel(growth="linear")
    saved = {}

    monkeypatch.setattr(train_mod, "preprocess_pipeline", lambda prm: history_df)
    monkeypatch.setattr(
        train_mod,
        "feature_engineering_pipeline",
        lambda prm, source, config_path: (history_df.copy(), base_config.copy()),
    )
    monkeypatch.setattr(train_mod, "get_data_loader", lambda *args, **kwargs: object())
    monkeypatch.setattr(train_mod, "save_features", lambda df, prm, loader: None)
    monkeypatch.setattr(train_mod, "build_prophet_model", lambda config, prm=None: fake_model)
    monkeypatch.setattr(train_mod, "naive_baseline", lambda df_full, df_val: None)
    monkeypatch.setattr(
        train_mod,
        "evaluate_model",
        lambda model, df_val: {"mae": 1.0, "rmse": 2.0, "mape": 3.0, "wape": 4.0, "r2": 0.9},
    )
    monkeypatch.setattr(train_mod, "MLFLOW_AVAILABLE", False)

    def _capture_save_model(model, config, metrics, prm):
        saved["model"] = model
        saved["metrics"] = metrics
        saved["prm"] = prm

    monkeypatch.setattr(train_mod, "save_model", _capture_save_model)

    model, metrics = train_mod.train_one_site(
        data_path=Path("unused.csv"),
        config=base_config,
        prm="30000250086126",
        config_path=str(tmp_path / "config.yaml"),
    )

    assert model is fake_model
    assert metrics["mae"] == 1.0
    assert fake_model.extra_regressors["temperature"]["standardize"] is True
    assert saved["prm"] == "30000250086126"
    assert saved["metrics"]["r2"] == 0.9
    assert len(fake_model.fitted_df) > 0


def test_load_prophet_model_prefers_latest(tmp_path):
    """Le chargement doit privilégier l'alias *_latest.pkl."""
    old_model = tmp_path / "prophet_model_30000250086126_20240101.pkl"
    latest_model = tmp_path / "prophet_model_30000250086126_latest.pkl"
    newer_model = tmp_path / "prophet_model_30000250086126_20240102.pkl"

    for path, value in ((old_model, "old"), (latest_model, "latest"), (newer_model, "new")):
        with open(path, "wb") as f:
            pickle.dump({"version": value}, f)

    loaded = predict_mod.load_prophet_model(model_dir=str(tmp_path), prm="30000250086126")

    assert loaded["version"] == "latest"


def test_build_future_from_features_creates_expected_columns():
    """Le futur doit reconstruire les variables attendues par Prophet."""
    df_features = _make_history_df(hours=240)
    model = SimpleNamespace(
        growth="logistic",
        extra_regressors={
            "temperature": {},
            "heure_sin": {},
            "heure_cos": {},
            "is_holiday": {},
            "puissance_lag_24": {},
            "puissance_roll_24": {},
        },
    )
    meteo_future_df = _make_future_meteo_df(df_features["datetime"].max() + pd.Timedelta(hours=1), hours=3)

    future = predict_mod.build_future_from_features(df_features, meteo_future_df, model)

    assert list(future.columns[:3]) == ["ds", "cap", "floor"]
    assert future["cap"].nunique() == 1
    assert future["floor"].nunique() == 1
    assert future["temperature"].tolist() == [7.0, 8.0, 9.0]
    assert future["puissance_roll_24"].nunique() == 1
    assert future["puissance_lag_24"].iloc[0] == df_features["puissance_moy_heure"].iloc[-24]


def test_predict_future_clips_negative_values(monkeypatch):
    """La prédiction finale doit être bornée à zéro si demandé."""
    df_features = _make_history_df(hours=240)
    meteo_future_df = _make_future_meteo_df(df_features["datetime"].max() + pd.Timedelta(hours=1), hours=3)

    fake_model = SimpleNamespace(
        growth="linear",
        extra_regressors={"temperature": {}, "heure_sin": {}, "heure_cos": {}},
        predict=lambda df: pd.DataFrame(
            {
                "ds": df["ds"].values,
                "yhat": [-5.0, -1.0, 2.0],
                "yhat_lower": [-7.0, -3.0, 0.5],
                "yhat_upper": [1.0, 2.0, 3.0],
            }
        ),
    )

    monkeypatch.setattr(predict_mod, "load_prophet_model", lambda model_dir, prm=None: fake_model)
    monkeypatch.setattr(
        predict_mod,
        "build_features_from_history_df",
        lambda history_df, prm, config_path: (df_features.copy(), {}),
    )
    monkeypatch.setattr(predict_mod, "load_config", lambda config_path: {"prediction": {"clip_negative": True}})

    result = predict_mod.predict_future(
        prm="30000250086126",
        meteo_future_df=meteo_future_df,
        model_dir="unused",
        config_path="unused",
        history_df=pd.DataFrame({"datetime": []}),
    )

    assert len(result) == 3
    assert result["yhat"].tolist() == [0.0, 0.0, 2.0]
    assert result["yhat_lower"].tolist() == [0.0, 0.0, 0.5]
