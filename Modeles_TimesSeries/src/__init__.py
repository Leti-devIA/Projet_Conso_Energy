# __init__.py pour le package src
"""
Package source pour le projet de prédiction de consommation énergétique.
"""

__version__ = "1.0.0"
__author__ = "Energy Forecast Team"

# Imports pour faciliter l'utilisation
from .preprocessing import preprocess_pipeline
from .feature_engineering import feature_engineering_pipeline, get_feature_list
from .model import build_lstm_model
from .train import train_model
from .predict import predict_future, save_predictions
from .utils import (
    create_sequences,
    calculate_mape,
    evaluate_model,
    plot_predictions,
    plot_training_history,
    plot_feature_importance
)

__all__ = [
    'preprocess_pipeline',
    'feature_engineering_pipeline',
    'get_feature_list',
    'build_lstm_model',
    'train_model',
    'predict_future',
    'save_predictions',
    'create_sequences',
    'calculate_mape',
    'evaluate_model',
    'plot_predictions',
    'plot_training_history',
    'plot_feature_importance'
]
