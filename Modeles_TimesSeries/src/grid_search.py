"""
Random Search hiérarchique Prophet
Phase 1 : TREND
Phase 2 : SAISONNALITÉS
Optimisé pour prévision long terme (budget énergie)
"""

import argparse
import itertools
import random
import re
import json
import warnings
from pathlib import Path
from datetime import timedelta
import pandas as pd
import yaml
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics

from .preprocessing import preprocess_pipeline
from .feature_engineering import feature_engineering_pipeline

import logging


logging.getLogger("cmdstanpy").setLevel(logging.WARNING)  # supprime les logs trop verbeux de cmdstan
warnings.filterwarnings("ignore")  # ignore warnings pour cleaner la sortie


# ---------------- CONFIG ----------------
def load_config(config_path="config/config.yaml"):
    """Charge la configuration YAML."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def save_config(config, config_path="config/config.yaml"):
    """Sauvegarde la configuration YAML."""
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)


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
def evaluate_with_cv(model, gs_cfg, metric):
    """Évalue un modèle via cross-validation Prophet."""
    df_cv = cross_validation(
        model,
        initial=gs_cfg.get("initial", "365 days"),
        period=gs_cfg.get("period", "90 days"),
        horizon=gs_cfg.get("horizon", "30 days"),
        parallel="threads"
    )

    # calcule métriques classiques
    metrics_df = performance_metrics(df_cv)
    score_map = {
        "mae":  metrics_df["mae"].mean(),
        "rmse": metrics_df["rmse"].mean(),
        "mape": metrics_df["mape"].mean(),
    }
    return float(score_map.get(metric, metrics_df["rmse"].mean()))




# ---------------- PHASE 1 : TREND ----------------
def tune_trend(df_train, regressors, gs_cfg, metric):
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
    combos = random.sample(combos, min(len(combos), gs_cfg.get("n_samples_trend", 12)))

    best_score = float("inf")
    best_params = {}

    for i, combo in enumerate(combos, 1):
        params = dict(zip(trend_grid.keys(), combo))
        print(f"\n[Trend {i}/{len(combos)}] {params}")
        model = train_with_params(df_train, params, regressors)
        score = evaluate_with_cv(model, gs_cfg, metric)
        print(f"→ {metric} = {score:.4f}")

        if score < best_score:
            best_score = score
            best_params = params.copy()

    print("\n🏆 BEST TREND:", best_params, best_score)
    return best_params





# ---------------- PHASE 2 : SAISONNALITÉS ----------------
def tune_seasonality(df_train, regressors, gs_cfg, metric, base_params):
    """Recherche aléatoire des meilleurs paramètres de saisonnalité."""
    print("\n================ PHASE 2 : SAISONNALITÉS =================")
    season_grid = {
        "seasonality_mode": ["multiplicative"],
        "seasonality_prior_scale": [1, 5, 10, 20, 30],
        "holidays_prior_scale": [5, 10, 20],
        "daily_fourier_order": [5, 10, 15, 20],
        "weekly_fourier_order": [5, 10, 15, 20],
        "yearly_fourier_order": [5, 10, 15, 20],
    }

    combos = list(itertools.product(*season_grid.values()))
    combos = random.sample(combos, min(len(combos), gs_cfg.get("n_samples_season", 30)))

    best_score = float("inf")
    best_params = base_params.copy()

    for i, combo in enumerate(combos, 1):
        params = dict(zip(season_grid.keys(), combo))
        params.update(base_params)  # fusionne avec trend optimisé

        print(f"\n[Season {i}/{len(combos)}] {params}")
        model = train_with_params(df_train, params, regressors)
        score = evaluate_with_cv(model, gs_cfg, metric)
        print(f"→ {metric} = {score:.4f}")

        if score < best_score:
            best_score = score
            best_params = params.copy()

    print("\n🏆 BEST GLOBAL PARAMS:", best_params, best_score)
    return best_params





# ---------------- PIPELINE COMPLET ----------------
def grid_search_random(prm, config, config_path):
    """Pipeline complet : prépa données + recherche trend + recherche saisonnalité."""
    gs_cfg     = config.get("grid_search", {})
    metric     = gs_cfg.get("metric", "mape")
    regressors = config["prophet"]["regressors"]

    print(f"\n🔍 OPTIMISATION PRM {prm} | metric = {metric}")

    df = prepare_data(prm, config, config_path)
    split_date = df["ds"].max() - pd.Timedelta(days=30)
    df_train   = df[df["ds"] < split_date]

    best_trend = tune_trend(df_train, regressors, gs_cfg, metric)
    best_all   = tune_seasonality(df_train, regressors, gs_cfg, metric, best_trend)

    return best_all



# ---------------- SAUVEGARDE ----------------
def save_best_params(best_params, prm, config, config_path):
    """Sauvegarde les meilleurs paramètres en JSON."""
    save_dir = Path(config["models"]["save_dir"])
    save_dir.mkdir(parents=True, exist_ok=True)
    json_path = save_dir / f"prophet_best_params_{prm}.json"
    with open(json_path, "w") as f:
        json.dump(best_params, f, indent=2)
    print("✅ Params saved:", json_path)



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
    for p in processed_dir.glob("data_preprocessed_*.csv"):
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

    for prm in prm_files.keys():
        best_params = grid_search_random(prm, config, args.config)
        save_best_params(best_params, prm, config, args.config)