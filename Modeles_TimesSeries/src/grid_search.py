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
import warnings
from datetime import datetime
from pathlib import Path
from datetime import timedelta
import pandas as pd
import yaml
from prophet import Prophet

from .preprocessing import preprocess_pipeline
from .feature_engineering import feature_engineering_pipeline

import logging


logging.getLogger("cmdstanpy").setLevel(logging.WARNING)  # supprime les logs trop verbeux de cmdstan
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
    - metric: "rmse" (str) -> optimisation mono-métrique
    - metric: ["rmse", "wape"] (list) -> rmse principal, wape tie-break
    """
    metric_cfg = gs_cfg.get("metric", "wape")

    if isinstance(metric_cfg, str):
        metrics = [metric_cfg.lower()]
    elif isinstance(metric_cfg, list) and metric_cfg:
        metrics = [str(m).lower() for m in metric_cfg]
    else:
        metrics = ["wape"]

    metrics = [m for m in metrics if m in SUPPORTED_METRICS]
    if not metrics:
        metrics = ["wape"]

    return metrics


# ---------------- DATA PREPARATION ----------------
def prepare_data(prm, config, config_path):
    """Prépare les données pour Prophet : chargement + features."""
    target_col = config["target"]
    regressors = config["prophet"]["regressors"]

    # Charger et ajouter les features via feature_engineering_pipeline
    # qui retourne un tuple (df, config)
    df_feat, _ = feature_engineering_pipeline(prm, config_path=config_path)

    df = df_feat.copy()
    df["ds"] = pd.to_datetime(df["datetime"])  # Prophet attend 'ds' pour la date
    df["y"]  = df[target_col]                  # Prophet attend 'y' pour la cible
    df = df.dropna(subset=["y"])

    allowed_cols = ["ds", "y"] + regressors
    return df[[c for c in allowed_cols if c in df.columns]]

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

    # si logistic growth, ajoute cap/floor
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

    # ajout des saisonnalités custom
    model.add_seasonality("daily",  period=1,      fourier_order=params.get("daily_fourier_order", 10))
    model.add_seasonality("weekly", period=7,      fourier_order=params.get("weekly_fourier_order", 5))
    model.add_seasonality("yearly", period=365.25, fourier_order=params.get("yearly_fourier_order", 10))

    # ajout des regressors exogènes
    for col in regressors:
        model.add_regressor(col, standardize=False)

    model.fit(df_train)
    return model


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




# ---------------- PHASE 1 : TREND ----------------
def tune_trend(df_train, df_val, regressors, gs_cfg, metrics, prm, rng):
    """Recherche aléatoire des meilleurs paramètres de trend."""
    print("\n================ PHASE 1 : TREND =================")
    trend_grid = {
        "growth": ["flat"],
        "changepoint_prior_scale": [0.001, 0.01, 0.05, 0.1, 0.5],
        "n_changepoints": [10, 25, 50],
        "changepoint_range": [0.8, 0.9, 0.95],
    }

    # combinaisons et sous-échantillonnage aléatoire
    combos = list(itertools.product(*trend_grid.values()))
    combos = rng.sample(combos, min(len(combos), gs_cfg.get("n_samples_trend", 12)))

    best_scores = None
    best_all_scores = None
    best_params = {}
    trial_rows = []

    for i, combo in enumerate(combos, 1):
        params = dict(zip(trend_grid.keys(), combo))
        print(f"\n[Trend {i}/{len(combos)}] {params}")
        model = train_with_params(df_train, params, regressors)
        scores, all_scores = evaluate_holdout(model, df_val, metrics)
        score_txt = " | ".join([f"{m} = {scores[m]:.4f}" for m in metrics if m in scores])
        print(f"→ {score_txt}")
        print(
            "   All metrics: "
            f"mae = {all_scores['mae']:.4f} | "
            f"rmse = {all_scores['rmse']:.4f} | "
            f"mape = {all_scores['mape']:.4f} | "
            f"wape = {all_scores['wape']:.4f} | "
            f"r2 = {all_scores['r2']:.4f}"
        )

        trial_row = {
            "prm": prm,
            "phase": "trend",
            "trial_index": i,
            "optimized_metrics": ",".join(metrics),
        }
        trial_row.update({f"param_{k}": v for k, v in params.items()})
        trial_row.update({f"selected_{k}": v for k, v in scores.items()})
        trial_row.update({f"metric_{k}": v for k, v in all_scores.items()})
        trial_rows.append(trial_row)

        candidate_key = tuple(scores[m] for m in metrics if m in scores)
        best_key = tuple(best_scores[m] for m in metrics if m in best_scores) if best_scores else None

        if best_key is None or candidate_key < best_key:
            best_scores = scores.copy()
            best_all_scores = all_scores.copy()
            best_params = params.copy()

    print("\n🏆 BEST TREND:", best_params, best_scores)
    return best_params, best_scores, best_all_scores, trial_rows





# ---------------- PHASE 2 : SAISONNALITÉS ----------------
def tune_seasonality(df_train, df_val, regressors, gs_cfg, metrics, base_params, prm, rng):
    """Recherche aléatoire des meilleurs paramètres de saisonnalité."""
    print("\n================ PHASE 2 : SAISONNALITÉS =================")
    season_grid = {
        "seasonality_mode": ["multiplicative"],
        "seasonality_prior_scale": [1, 10, 30],
        "holidays_prior_scale": [5, 10, 20],
        "daily_fourier_order": [5, 15, 20],
        "weekly_fourier_order": [5, 15, 20],
        "yearly_fourier_order": [5, 15, 20],
    }

    combos = list(itertools.product(*season_grid.values()))
    combos = rng.sample(combos, min(len(combos), gs_cfg.get("n_samples_season", 15)))

    best_scores = None
    best_all_scores = None
    best_params = base_params.copy()
    trial_rows = []

    for i, combo in enumerate(combos, 1):
        params = dict(zip(season_grid.keys(), combo))
        params.update(base_params)  # fusionne avec trend optimisé

        print(f"\n[Season {i}/{len(combos)}] {params}")
        model = train_with_params(df_train, params, regressors)
        scores, all_scores = evaluate_holdout(model, df_val, metrics)
        score_txt = " | ".join([f"{m} = {scores[m]:.4f}" for m in metrics if m in scores])
        print(f"→ {score_txt}")
        print(
            "   All metrics: "
            f"mae = {all_scores['mae']:.4f} | "
            f"rmse = {all_scores['rmse']:.4f} | "
            f"mape = {all_scores['mape']:.4f} | "
            f"wape = {all_scores['wape']:.4f} | "
            f"r2 = {all_scores['r2']:.4f}"
        )

        trial_row = {
            "prm": prm,
            "phase": "seasonality",
            "trial_index": i,
            "optimized_metrics": ",".join(metrics),
        }
        trial_row.update({f"param_{k}": v for k, v in params.items()})
        trial_row.update({f"selected_{k}": v for k, v in scores.items()})
        trial_row.update({f"metric_{k}": v for k, v in all_scores.items()})
        trial_rows.append(trial_row)

        candidate_key = tuple(scores[m] for m in metrics if m in scores)
        best_key = tuple(best_scores[m] for m in metrics if m in best_scores) if best_scores else None

        if best_key is None or candidate_key < best_key:
            best_scores = scores.copy()
            best_all_scores = all_scores.copy()
            best_params = params.copy()

    print("\n🏆 BEST GLOBAL PARAMS:", best_params, best_scores)
    return best_params, best_scores, best_all_scores, trial_rows





# ---------------- PIPELINE COMPLET ----------------
def grid_search_random(prm, config, config_path):
    """Pipeline complet : prépa données + recherche trend + recherche saisonnalité."""
    gs_cfg     = config.get("grid_search", {})
    metrics    = parse_metric_config(gs_cfg)
    regressors = config["prophet"]["regressors"]
    seed = int(gs_cfg.get("random_seed", 42))
    rng = random.Random(seed)

    print(f"\n🔍 OPTIMISATION PRM {prm} | metrics = {', '.join(metrics)} | seed = {seed}")

    df = prepare_data(prm, config, config_path)
    # Utilise la même fenêtre de validation que train.py pour la cohérence des métriques
    validation_days = config.get("validation", {}).get("days", 30)
    split_date = df["ds"].max() - pd.Timedelta(days=validation_days)
    print(f"   Split : {validation_days} jours réservés pour validation (idem train.py)")
    df_train   = df[df["ds"] < split_date]
    df_val     = df[df["ds"] >= split_date]

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
        "best_params": best_all,
        "best_selected_scores": best_selected_scores or {},
        "best_all_scores": best_all_scores or {},
        "trials": trend_trials + season_trials,
    }



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
        save_best_params(result["best_params"], prm, config, args.config)
        summary_rows.append(result)
        all_trial_rows.extend(result.get("trials", []))

    save_grid_search_summary(summary_rows, config)
    save_grid_search_trials(all_trial_rows, config)