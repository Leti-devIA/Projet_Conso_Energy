"""Package source pour le pipeline Prophet de prévision énergétique."""

__version__ = "2.0.0"
__author__ = "Energy Forecast Team"

__all__ = [
    "preprocess_pipeline",
    "feature_engineering_pipeline",
    "predict_future",
    "load_config",
    "detect_prms",
    "calculate_mape",
    "evaluate_model",
]


def __getattr__(name):
    """Importe les sous-modules seulement quand ils sont nécessaires."""
    if name == "preprocess_pipeline":
        from .preprocessing import preprocess_pipeline

        return preprocess_pipeline
    if name == "feature_engineering_pipeline":
        from .feature_engineering import feature_engineering_pipeline

        return feature_engineering_pipeline
    if name == "predict_future":
        from .predict import predict_future

        return predict_future
    if name in {"load_config", "detect_prms", "calculate_mape", "evaluate_model"}:
        from .utils import load_config, detect_prms, calculate_mape, evaluate_model

        return {
            "load_config": load_config,
            "detect_prms": detect_prms,
            "calculate_mape": calculate_mape,
            "evaluate_model": evaluate_model,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
