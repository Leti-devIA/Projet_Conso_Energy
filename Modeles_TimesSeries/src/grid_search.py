"""
Optimisation hyperparamètres Prophet (version pédagogique).

Approche en 2 phases :
1) Trend : paramètres de tendance/changepoints
2) Seasonality : paramètres de saisonnalité

Le script exporte :
- les meilleurs paramètres par site,
- un résumé CSV,
- le détail CSV de tous les essais.
"""

import argparse
import itertools
import random
import re
import json
import math
import warnings
import importlib
import time
from datetime import datetime
from pathlib import Path
import pandas as pd
import yaml
from prophet import Prophet

try:
    Tuner = importlib.import_module("mango").Tuner
    MANGO_AVAILABLE = True
except Exception:
    Tuner = None
    MANGO_AVAILABLE = False

from .preprocessing import preprocess_pipeline
from .feature_engineering import feature_engineering_pipeline

import logging

try:
    import mlflow
    from .mlflow_utils import setup_mlflow
    MLFLOW_AVAILABLE = True
except Exception:
    mlflow = None
    MLFLOW_AVAILABLE = False


logging.getLogger("cmdstanpy").setLevel(logging.WARNING)  # supprime les logs trop verbeux de cmdstan
logging.getLogger("cmdstanpy.model").setLevel(logging.WARNING)
logging.getLogger("cmdstanpy.stanfit").setLevel(logging.WARNING)
warnings.filterwarnings("ignore")  # ignore warnings pour cleaner la sortie


SUPPORTED_METRICS = {"mae", "rmse", "mape", "wape"}


# ---------------- CONFIG ----------------
def load_config(config_path="config/config.yaml"):
    """Charge la configuration YAML."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config, config_path="config/config.yaml"):
    """Sauvegarde la configuration YAML."""
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)


def parse_metric_config(gs_cfg):
    """
    Parse la configuration de métriques.
    - metric: "mae" (str) -> optimisation mono-métrique
    - metric: ["mae", "rmse"] (list) -> mae principal, rmse tie-break
    """
    default_metrics = ["mae", "rmse"]
    metric_cfg = gs_cfg.get("metric", default_metrics)

    if isinstance(metric_cfg, str):
        metrics = [metric_cfg.lower()]
    elif isinstance(metric_cfg, list) and metric_cfg:
        metrics = [str(m).lower() for m in metric_cfg]
    else:
        metrics = default_metrics

    metrics = [m for m in metrics if m in SUPPORTED_METRICS]
    if not metrics:
        metrics = default_metrics

    return metrics


# ---------------- DATA PREPARATION ----------------
def prepare_data(prm, config, config_path):
    """Prépare les données pour Prophet : chargement + features."""
    target_col = config["target"]
    source = config.get("data_source", "csv")
    configured_regressors = config["prophet"]["regressors"]

    preprocess_pipeline(prm=prm, source=source, config_path=config_path)
    df_feat, _ = feature_engineering_pipeline(prm=prm, source=source, config_path=config_path)

    df = df_feat.copy()
    df["ds"] = pd.to_datetime(df["datetime"])  # Prophet attend 'ds' pour la date
    df["y"]  = df[target_col]                  # Prophet attend 'y' pour la cible
    df = df.dropna(subset=["y"])

    available_regressors = [c for c in configured_regressors if c in df.columns]
    missing_regressors = [c for c in configured_regressors if c not in df.columns]
    if missing_regressors:
        print(f"⚠️ Regressors absents ignorés ({len(missing_regressors)}): {missing_regressors}")

    allowed_cols = ["ds", "y"] + available_regressors
    return df[[c for c in allowed_cols if c in df.columns]], available_regressors

def add_logistic_cap_floor(df):
    """
    Ajoute cap et floor pour growth 'logistic'.
    Cap = maximum réaliste, Floor = minimum robuste
    """
    df = df.copy()
    floor = max(0, df["y"].quantile(0.01))
    cap = df["y"].quantile(0.99) * 1.3
    df["floor"] = floor
    df["cap"]   = cap
    return df


# ---------------- MODEL TRAINING ----------------
def train_with_params(df_train, params, regressors):
    """Entraîne un modèle Prophet avec des hyperparamètres donnés."""
    df_train = df_train.copy()
    growth = params.get("growth", "linear")

    if growth == "logistic":
        df_train = add_logistic_cap_floor(df_train)

    model = Prophet(
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        growth=growth,
        seasonality_mode=params.get("seasonality_mode", "additive"),
        changepoint_prior_scale=params.get("changepoint_prior_scale", 0.1),
        seasonality_prior_scale=params.get("seasonality_prior_scale", 10.0),
        holidays_prior_scale=params.get("holidays_prior_scale", 10.0),
        interval_width=params.get("interval_width", 0.95),
        uncertainty_samples=params.get("uncertainty_samples", 1000),
        n_changepoints=params.get("n_changepoints", 25),
        changepoint_range=params.get("changepoint_range", 0.8),
    )

    model.add_seasonality("daily",  period=1,      fourier_order=params.get("daily_fourier_order", 10))
    model.add_seasonality("weekly", period=7,      fourier_order=params.get("weekly_fourier_order", 5))
    model.add_seasonality("yearly", period=365.25, fourier_order=params.get("yearly_fourier_order", 10))

    for col in regressors:
        model.add_regressor(col, standardize=False)

    fit_kwargs = {}
    if "fit_iter" in params:
        fit_kwargs["iter"] = int(params["fit_iter"])  # borne itérations optimiseur
    if "fit_seed" in params:
        fit_kwargs["seed"] = int(params["fit_seed"])

    model.fit(df_train, algorithm=params.get("fit_algorithm", "LBFGS"), **fit_kwargs)
    return model


def build_tuning_fixed_params(gs_cfg):
    """Construit des paramètres fixes pour accélérer/stabiliser le tuning."""
    fixed_params = {
        "uncertainty_samples": int(gs_cfg.get("uncertainty_samples", 0)),
        "interval_width": float(gs_cfg.get("interval_width", 0.95)),
        "fit_iter": int(gs_cfg.get("fit_iter", 300)),
        "fit_seed": int(gs_cfg.get("fit_seed", 42)),
    }

    fit_algorithm = gs_cfg.get("fit_algorithm")
    if fit_algorithm:
        fixed_params["fit_algorithm"] = str(fit_algorithm)

    return fixed_params


# ---------------- METRICS ----------------
def evaluate_holdout(model, df_val, metrics):
    """Évalue un modèle sur un holdout temporel (sans cross-validation)."""
    df_pred = df_val.copy()

    if model.growth == "logistic":
        if "cap" not in df_pred.columns or "floor" not in df_pred.columns:
            df_pred = add_logistic_cap_floor(df_pred)

    forecast = model.predict(df_pred)
    y_true = df_val["y"].values
    y_pred = forecast["yhat"].values

    mask = ~(pd.isna(y_true) | pd.isna(y_pred))
    y_true = y_true[mask]
    y_pred = y_pred[mask]

    mae = float((abs(y_true - y_pred)).mean())
    rmse = float((((y_true - y_pred) ** 2).mean()) ** 0.5)
    mape = float((abs((y_true - y_pred) / (y_true + 1e-8))).mean() * 100.0)

    score_map = {
        "mae": mae,
        "rmse": rmse,
        "mape": mape,
    }

    abs_err_sum = abs(y_true - y_pred).sum()
    abs_y_sum = abs(y_true).sum()
    wape = float("nan") if abs_y_sum == 0 else float((abs_err_sum / abs_y_sum) * 100.0)
    score_map["wape"] = wape

    ss_res = ((y_true - y_pred) ** 2).sum()
    ss_tot = ((y_true - y_true.mean()) ** 2).sum()
    r2 = float("nan") if ss_tot == 0 else float(1 - (ss_res / ss_tot))

    all_scores = {
        "mae": float(score_map["mae"]),
        "rmse": float(score_map["rmse"]),
        "mape": float(score_map["mape"]),
        "wape": float(score_map["wape"]),
        "r2": r2,
    }

    selected_scores = {
        metric: float(score_map[metric])
        for metric in metrics
        if metric in score_map
    }

    if not selected_scores:
        selected_scores = {"rmse": float(score_map["rmse"])}

    return selected_scores, all_scores


def _score_key(scores, metrics):
    return tuple(scores[m] for m in metrics if m in scores)


def _objective_loss(selected_scores, metrics):
    """Construit une loss scalaire pour Mango à partir des métriques à minimiser."""
    available = [m for m in metrics if m in selected_scores]
    if not available:
        return float("inf")

    if "mae" in available and "rmse" in available:
        return float(selected_scores["mae"] + selected_scores["rmse"])

    return float(sum(selected_scores[m] for m in available))


def _ensure_space_list(value, default_values):
    if value is None:
        return list(default_values)
    if isinstance(value, list):
        return value if value else list(default_values)
    return [value]


def _run_mango_tuning(
    phase_name,
    df_train,
    df_val,
    regressors,
    metrics,
    prm,
    search_space,
    n_iterations,
    base_params=None,
):
    """Exécute un tuning Mango et retourne best params/scores + détails des essais."""
    if not MANGO_AVAILABLE:
        raise ImportError(
            "Le package 'mango' n'est pas disponible. Installez-le (ex: pip install arm-mango)."
        )

    safe_penalty = 1e12
    trial_rows = []
    started_at = time.perf_counter()
    progress = {"done": 0}

    def objective_function(args_list):
        params_evaluated = []
        losses = []

        for i, params in enumerate(args_list, 1):
            merged_params = dict(base_params or {})
            merged_params.update(params)
            trial_started_at = time.perf_counter()

            try:
                model = train_with_params(df_train, merged_params, regressors)
                selected_scores, all_scores = evaluate_holdout(model, df_val, metrics)
                objective_loss = _objective_loss(selected_scores, metrics)
                if not math.isfinite(objective_loss):
                    objective_loss = safe_penalty
            except Exception as err:
                selected_scores = {metric: safe_penalty for metric in metrics}
                all_scores = {
                    "mae": safe_penalty,
                    "rmse": safe_penalty,
                    "mape": safe_penalty,
                    "wape": safe_penalty,
                    "r2": float("nan"),
                }
                objective_loss = safe_penalty
                print(f"⚠️ [{phase_name}] essai invalide: {err}")

            trial_row = {
                "prm": prm,
                "phase": phase_name,
                "trial_index": len(trial_rows) + 1,
                "optimized_metrics": ",".join(metrics),
                "objective_loss": objective_loss,
            }
            trial_row.update({f"param_{k}": v for k, v in merged_params.items()})
            trial_row.update({f"selected_{k}": v for k, v in selected_scores.items()})
            trial_row.update({f"metric_{k}": v for k, v in all_scores.items()})
            trial_rows.append(trial_row)

            score_txt = " | ".join([f"{m} = {selected_scores[m]:.4f}" for m in metrics if m in selected_scores])
            progress["done"] += 1
            total_done = progress["done"]
            elapsed_trial = time.perf_counter() - trial_started_at
            elapsed_total = time.perf_counter() - started_at
            avg_sec = elapsed_total / max(1, total_done)
            remaining = max(0, int(n_iterations) - total_done)
            eta_sec = avg_sec * remaining

            print(f"[{phase_name} batch item {i}/{len(args_list)} | essai {total_done}/{int(n_iterations)}] {merged_params}")
            print(f"→ {score_txt}")
            print(f"   Objective loss: {objective_loss:.4f}")
            print(
                f"   Temps essai: {elapsed_trial:.1f}s | "
                f"Temps total: {elapsed_total/60:.1f}min | "
                f"ETA: {eta_sec/60:.1f}min"
            )

            params_evaluated.append(params)
            losses.append(objective_loss)

        return params_evaluated, losses

    conf_dict = {
        "num_iteration": max(1, int(n_iterations)),
        "initial_random": max(1, min(10, int(n_iterations))),
    }

    tuner = Tuner(search_space, objective_function, conf_dict)
    tuner.maximize()

    if not trial_rows:
        raise RuntimeError(f"Aucun essai Mango exécuté pour la phase {phase_name}")

    best_trial = min(
        trial_rows,
        key=lambda row: _score_key(
            {m: row.get(f"selected_{m}", safe_penalty) for m in metrics},
            metrics,
        ),
    )

    best_params = {
        col.replace("param_", ""): val
        for col, val in best_trial.items()
        if col.startswith("param_")
    }
    best_selected_scores = {
        metric: float(best_trial[f"selected_{metric}"])
        for metric in metrics
        if f"selected_{metric}" in best_trial
    }
    best_all_scores = {
        metric: float(best_trial[f"metric_{metric}"])
        for metric in ["mae", "rmse", "mape", "wape", "r2"]
        if f"metric_{metric}" in best_trial
    }

    return best_params, best_selected_scores, best_all_scores, trial_rows




# ---------------- PHASE 1 : TREND ----------------
def tune_trend(df_train, df_val, regressors, gs_cfg, metrics, prm, rng):
    """Recherche des meilleurs paramètres de trend avec Mango."""
    print("\n================ PHASE 1 : TREND =================")
    trend_space = {
        "growth": _ensure_space_list(gs_cfg.get("growth"), ["flat"]),
        "changepoint_prior_scale": _ensure_space_list(
            gs_cfg.get("changepoint_prior_scale"),
            [0.001, 0.01, 0.05, 0.1, 0.3],
        ),
        "n_changepoints": _ensure_space_list(gs_cfg.get("n_changepoints"), [10, 25, 50]),
        "changepoint_range": _ensure_space_list(gs_cfg.get("changepoint_range"), [0.8, 0.9, 0.95]),
    }
    n_iterations = int(gs_cfg.get("n_samples_trend", gs_cfg.get("n_iter_trend", 20)))
    fixed_params = build_tuning_fixed_params(gs_cfg)

    best_params, best_scores, best_all_scores, trial_rows = _run_mango_tuning(
        phase_name="trend",
        df_train=df_train,
        df_val=df_val,
        regressors=regressors,
        metrics=metrics,
        prm=prm,
        search_space=trend_space,
        n_iterations=n_iterations,
        base_params=fixed_params,
    )

    print("\n🏆 BEST TREND:", best_params, best_scores)
    return best_params, best_scores, best_all_scores, trial_rows





# ---------------- PHASE 2 : SAISONNALITÉS ----------------
def tune_seasonality(df_train, df_val, regressors, gs_cfg, metrics, base_params, prm, rng):
    """Recherche des meilleurs paramètres de saisonnalité avec Mango."""
    print("\n================ PHASE 2 : SAISONNALITÉS =================")
    season_space = {
        "seasonality_mode": _ensure_space_list(gs_cfg.get("seasonality_mode"), ["multiplicative"]),
        "seasonality_prior_scale": _ensure_space_list(gs_cfg.get("seasonality_prior_scale"), [1, 10, 30]),
        "holidays_prior_scale": _ensure_space_list(gs_cfg.get("holidays_prior_scale"), [5, 10, 20]),
        "daily_fourier_order": _ensure_space_list(gs_cfg.get("daily_fourier_order"), [5, 15, 20]),
        "weekly_fourier_order": _ensure_space_list(gs_cfg.get("weekly_fourier_order"), [5, 15, 20]),
        "yearly_fourier_order": _ensure_space_list(gs_cfg.get("yearly_fourier_order"), [5, 15, 20]),
    }
    n_iterations = int(gs_cfg.get("n_samples_season", gs_cfg.get("n_iter_season", 25)))
    fixed_params = build_tuning_fixed_params(gs_cfg)
    full_base_params = dict(fixed_params)
    full_base_params.update(base_params)

    best_params, best_scores, best_all_scores, trial_rows = _run_mango_tuning(
        phase_name="seasonality",
        df_train=df_train,
        df_val=df_val,
        regressors=regressors,
        metrics=metrics,
        prm=prm,
        search_space=season_space,
        n_iterations=n_iterations,
        base_params=full_base_params,
    )

    print("\n🏆 BEST GLOBAL PARAMS:", best_params, best_scores)
    return best_params, best_scores, best_all_scores, trial_rows





# ---------------- PIPELINE COMPLET ----------------
def grid_search_random(prm, config, config_path):
    """Pipeline complet : prépa données + recherche trend + recherche saisonnalité."""
    gs_cfg     = config.get("grid_search", {})
    metrics    = parse_metric_config(gs_cfg)
    seed = int(gs_cfg.get("random_seed", 42))
    rng = random.Random(seed)

    if not MANGO_AVAILABLE:
        raise ImportError(
            "Le package 'mango' est requis pour ce script. Installez-le via `pip install arm-mango`."
        )

    print(f"\n🔍 OPTIMISATION PRM {prm} | metrics = {', '.join(metrics)} | seed = {seed}")

    df, regressors = prepare_data(prm, config, config_path)
    if df.empty:
        raise ValueError(f"Aucune donnée disponible après preprocessing/features pour PRM {prm}")
    if not regressors:
        raise ValueError(f"Aucun regressor disponible pour PRM {prm}")

    # Utilise la même fenêtre de validation que train.py pour la cohérence des métriques
    validation_days = config.get("validation", {}).get("days", 30)
    split_date = df["ds"].max() - pd.Timedelta(days=validation_days)
    print(f"   Split : {validation_days} jours réservés pour validation (idem train.py)")
    df_train   = df[df["ds"] < split_date]
    df_val     = df[df["ds"] >= split_date]
    if df_train.empty or df_val.empty:
        raise ValueError(
            f"Split invalide pour PRM {prm} (train={len(df_train)}, val={len(df_val)}). "
            "Réduire validation.days ou vérifier l'historique disponible."
        )

    if bool(gs_cfg.get("fast_mode", True)):
        train_window_days = int(gs_cfg.get("train_window_days", 365))
        if train_window_days > 0:
            min_train_date = df_train["ds"].max() - pd.Timedelta(days=train_window_days)
            df_train_fast = df_train[df_train["ds"] >= min_train_date]
            if not df_train_fast.empty and len(df_train_fast) < len(df_train):
                print(
                    f"   ⚡ fast_mode actif: train réduit de {len(df_train)} à {len(df_train_fast)} lignes "
                    f"(fenêtre {train_window_days} jours)"
                )
                df_train = df_train_fast

        max_train_rows = int(gs_cfg.get("max_train_rows", 0))
        if max_train_rows > 0 and len(df_train) > max_train_rows:
            print(f"   ⚡ fast_mode actif: train tronqué à {max_train_rows} dernières lignes")
            df_train = df_train.tail(max_train_rows).copy()

    best_trend, _, _, trend_trials = tune_trend(df_train, df_val, regressors, gs_cfg, metrics, prm, rng)
    best_all, best_selected_scores, best_all_scores, season_trials = tune_seasonality(
        df_train,
        df_val,
        regressors,
        gs_cfg,
        metrics,
        best_trend,
        prm,
        rng,
    )

    return {
        "prm": prm,
        "optimized_metrics": ",".join(metrics),
        "train_size": int(len(df_train)),
        "val_size": int(len(df_val)),
        "regressors_used": regressors,
        "best_params": best_all,
        "best_selected_scores": best_selected_scores or {},
        "best_all_scores": best_all_scores or {},
        "trials": trend_trials + season_trials,
    }


def _is_finite_number(value):
    return value is not None and not pd.isna(value) and math.isfinite(float(value))


def log_grid_search_to_mlflow(result, config, config_path):
    if not (MLFLOW_AVAILABLE and config.get("mlflow", {}).get("enabled", False)):
        return None

    setup_mlflow(config_path)
    prm = result.get("prm")
    optimized_metrics = [m for m in str(result.get("optimized_metrics", "")).split(",") if m]

    with mlflow.start_run(run_name=f"grid_search_{prm}"):
        mlflow.set_tags({
            "task": "hyperparameter_tuning",
            "model_type": "Prophet",
            "site_prm": str(prm),
            "optimized_metrics": ",".join(optimized_metrics),
        })

        mlflow.log_params({
            "site_prm": str(prm),
            "optimized_metrics": ",".join(optimized_metrics),
            "primary_metric": optimized_metrics[0] if optimized_metrics else "mae",
            "secondary_metric": optimized_metrics[1] if len(optimized_metrics) > 1 else "none",
            "train_size": int(result.get("train_size", 0)),
            "val_size": int(result.get("val_size", 0)),
            "n_regressors": int(len(result.get("regressors_used", []))),
            "regressors_used": ", ".join(result.get("regressors_used", [])) or "none",
            "n_trials": int(len(result.get("trials", []))),
        })

        best_params = result.get("best_params", {}) or {}
        if best_params:
            mlflow.log_params({f"best_{k}": v for k, v in best_params.items()})

        best_scores = result.get("best_all_scores", {}) or {}
        for metric_name in ["mae", "rmse", "mape", "r2", "wape"]:
            value = best_scores.get(metric_name)
            if _is_finite_number(value):
                mlflow.log_metric(f"best_{metric_name}", float(value))

        df_trials = pd.DataFrame(result.get("trials", []))
        if not df_trials.empty:
            temp_dir = Path("mlruns_temp")
            temp_dir.mkdir(parents=True, exist_ok=True)

            trials_csv = temp_dir / f"grid_search_trials_{prm}.csv"
            df_trials.to_csv(trials_csv, index=False)
            mlflow.log_artifact(str(trials_csv), artifact_path="grid_search")
            if trials_csv.exists():
                trials_csv.unlink()

            for step, row in enumerate(df_trials.itertuples(index=False), 1):
                for metric_name in ["mae", "rmse", "mape", "r2"]:
                    col_name = f"metric_{metric_name}"
                    value = getattr(row, col_name, None)
                    if _is_finite_number(value):
                        mlflow.log_metric(f"trial_{metric_name}", float(value), step=step)

            fig_path = temp_dir / f"grid_search_mape_r2_{prm}.png"
            if fig_path.exists():
                fig_path.unlink()

        run_id = mlflow.active_run().info.run_id
        print(f"✅ Run MLflow grid search : {run_id}")
        return run_id



# ---------------- SAUVEGARDE ----------------
def save_best_params(best_params, prm, config, config_path):
    """
    Sauvegarde les meilleurs paramètres en JSON ET met à jour site_overrides dans config.yaml.

    Pourquoi c'est important : si on ne réinjecte pas les paramètres dans config.yaml,
    train.py utilisera les valeurs par défaut → métriques incohérentes avec le grid search.
    """
    save_dir = Path(config["models"]["save_dir"])
    save_dir.mkdir(parents=True, exist_ok=True)
    json_path = save_dir / f"prophet_best_params_{prm}.json"
    with open(json_path, "w") as f:
        json.dump(best_params, f, indent=2)
    print("✅ Params saved:", json_path)

    # Réinjection dans config.yaml → site_overrides[prm]
    update_config_site_overrides(prm, best_params, config_path)


# Clés grid search → clés Prophet (site_overrides)
_PARAM_KEYS = {
    "growth", "changepoint_prior_scale", "n_changepoints",
    "changepoint_range", "seasonality_mode", "seasonality_prior_scale",
    "holidays_prior_scale", "daily_fourier_order",
    "weekly_fourier_order", "yearly_fourier_order",
}


def update_config_site_overrides(prm, best_params, config_path):
    """
    Écrit les meilleurs hyperparamètres dans site_overrides[prm] du config.yaml.

    Point pédagogique : c'est le lien entre l'optimisation (grid search) et
    l'entraînement final (train.py). Sans ça, les deux scripts utilisent des
    paramètres différents → métriques incomparables.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if "site_overrides" not in cfg:
        cfg["site_overrides"] = {}

    prm_str = str(prm)
    existing = cfg["site_overrides"].get(prm_str, {}) or {}

    # Ne garder que les clés pertinentes pour Prophet
    filtered = {k: v for k, v in best_params.items() if k in _PARAM_KEYS}
    existing.update(filtered)
    cfg["site_overrides"][prm_str] = existing

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(cfg, f, allow_unicode=True, sort_keys=False)

    print(f"✅ site_overrides[{prm}] mis à jour dans {config_path}")
    print(f"   Paramètres écrits : {filtered}")


def save_grid_search_summary(summary_rows, config):
    """Sauvegarde un CSV récapitulatif final (1 ligne par PRM)."""
    if not summary_rows:
        return

    flattened_rows = []
    for row in summary_rows:
        flat = {
            "prm": row.get("prm"),
            "optimized_metrics": row.get("optimized_metrics", ""),
        }

        for k, v in (row.get("best_params") or {}).items():
            flat[f"param_{k}"] = v

        for k, v in (row.get("best_selected_scores") or {}).items():
            flat[f"selected_{k}"] = v

        for k, v in (row.get("best_all_scores") or {}).items():
            flat[f"metric_{k}"] = v

        flattened_rows.append(flat)

    df_summary = pd.DataFrame(flattened_rows).sort_values(by="prm")
    save_dir = Path(config["models"]["save_dir"])
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = save_dir / f"grid_search_summary_{timestamp}.csv"
    df_summary.to_csv(csv_path, index=False)
    print("✅ Grid search summary saved:", csv_path)


def save_grid_search_trials(all_trial_rows, config):
    """Sauvegarde un CSV détaillé avec tous les essais du grid search."""
    if not all_trial_rows:
        return

    df_trials = pd.DataFrame(all_trial_rows)
    sort_cols = [c for c in ["prm", "phase", "trial_index"] if c in df_trials.columns]
    if sort_cols:
        df_trials = df_trials.sort_values(by=sort_cols)

    save_dir = Path(config["models"]["save_dir"])
    save_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = save_dir / f"grid_search_trials_{timestamp}.csv"
    df_trials.to_csv(csv_path, index=False)
    print("✅ Grid search trials saved:", csv_path)



# ---------------- MAIN ----------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prm", nargs="+", default=None)
    parser.add_argument("--config", default="config/config.yaml")
    args = parser.parse_args()

    config = load_config(args.config)
    processed_dir = Path(config["data"]["processed"])

    # Construire un dictionnaire PRM → chemin fichier
    all_prm_files = {}
    for p in processed_dir.glob("data_processed_*.csv"):
        match = re.search(r'(\d+)', p.name)
        if match:
            prm = match.group(1)
            all_prm_files[prm] = p

    # Filtrer par PRMs demandés (ou tous si aucun spécifié)
    prm_files = {}
    if args.prm:
        for prm in args.prm:
            if prm in all_prm_files:
                prm_files[prm] = all_prm_files[prm]
            else:
                print(f"❌ Fichier processed introuvable pour PRM {prm}")
    else:
        prm_files = all_prm_files

    if not prm_files:
        print("❌ Aucun fichier trouvé pour optimisation")
        exit(1)

    print(f"✅ {len(prm_files)} site(s) à optimiser : {', '.join(prm_files.keys())}\n")

    summary_rows = []
    all_trial_rows = []
    for prm in prm_files.keys():
        result = grid_search_random(prm, config, args.config)

        if MLFLOW_AVAILABLE and config.get("mlflow", {}).get("enabled", False):
            try:
                run_id = log_grid_search_to_mlflow(result, config, args.config)
                if run_id:
                    result["mlflow_run_id"] = run_id
            except Exception as e:
                print(f"⚠️ MLflow grid search échoué (non bloquant) pour {prm}: {e}")

        save_best_params(result["best_params"], prm, config, args.config)
        summary_rows.append(result)
        all_trial_rows.extend(result.get("trials", []))

    save_grid_search_summary(summary_rows, config)
    save_grid_search_trials(all_trial_rows, config)