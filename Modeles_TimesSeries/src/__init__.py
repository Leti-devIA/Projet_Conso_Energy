"""Package source pour le pipeline Prophet de prévision énergétique."""

__version__ = "2.0.0"
__author__ = "Energy Forecast Team"

from .preprocessing import preprocess_pipeline
from .feature_engineering import feature_engineering_pipeline
from .predict import predict_future
from .utils import load_config, detect_prms, calculate_mape, evaluate_model

__all__ = [
    "preprocess_pipeline",
    "feature_engineering_pipeline",
    "predict_future",
    "load_config",
    "detect_prms",
    "calculate_mape",
    "evaluate_model",
]
