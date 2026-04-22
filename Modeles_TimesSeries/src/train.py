"""
Étape 3 du pipeline ML : entraînement Prophet multi-sites.

Chaque site produit :
  - models/saved/prophet_model_{PRM}_{timestamp}.pkl
  - models/saved/prophet_model_{PRM}_latest.pkl
  - models/saved/prophet_metrics_{PRM}.json

Utilisation :
  # Tous les sites détectés automatiquement
  python src/train.py

  # Un site spécifique
  python src/train.py --prm 30000250086126

  # Plusieurs sites
  python src/train.py --prm 30000250086126 30000540191777

Point pédagogique : ce script montre une chaîne complète
préprocessing -> features -> entraînement -> évaluation -> sauvegarde.
"""

import argparse
import os
import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
from datetime import datetime
from .data_loader import get_data_loader
from .utils import load_config, detect_prms
from .preprocessing import preprocess_pipeline
from .feature_engineering import (
    feature_engineering_pipeline,
    save_features,
)
from prophet import Prophet
from prophet.make_holidays import make_holidays_df
from prophet.diagnostics import cross_validation, performance_metrics


try:
    from .mlflow_utils import setup_mlflow, log_prophet_training
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False

# ===================================================
# CONFIGURATION
# ===================================================
config = load_config("config/config.yaml")

holidays = make_holidays_df([2023, 2024, 2025, 2026], country="FR")

# ===================================================
# FONCTION DE PRÉPARATION DES DONNÉES
# ===================================================

def prepare_data_for_prophet(df, target_col, config):
    """Convertit un DataFrame enrichi en format attendu par Prophet (ds, y + regressors)."""
    df = df.copy()
    df["ds"] = pd.to_datetime(df["datetime"])
    df["y"]  = df[target_col]
    df = df.dropna(subset=["y"])

    # Correction unités : preprocessing divise par 1000 à tort
    y_max = df["y"].max()
    if y_max < 10:
        print(f"   ⚠️  Target normalisée (max={y_max:.3f}) → ×1000")
        df["y"] = df["y"] * 1000

    # Filtre bruit de mesure
    filter_cfg = config["prophet"].get("filter_low_values", {})
    if filter_cfg.get("enabled", False):
        threshold = filter_cfg.get("threshold_kw", 0.0)
        n_before = len(df)
        df = df[df["y"] >= threshold]
        print(f"   Filtrage < {threshold} W : {n_before - len(df)} lignes supprimées")

    # Garder uniquement les colonnes nécessaires
    regressors = config["prophet"]["regressors"]
    allowed_cols = ["ds", "y"] + regressors
    available_cols = [c for c in allowed_cols if c in df.columns]

    missing = [c for c in regressors if c not in df.columns]
    if missing:
        print(f"   ⚠️  Regressors absents : {missing}")

    extra_feature_cols = [
        c for c in df.columns
        if c.startswith('puissance_lag_') or c.startswith('puissance_roll_')
        or c.startswith('puissance_std_') or c.startswith('puissance_min_')
        or c.startswith('puissance_max_')
    ]
    retained_extra = [c for c in regressors if c.startswith('puissance_')]
    excluded_extra = [c for c in extra_feature_cols if c not in retained_extra]

    if retained_extra:
        print(f"   Regressors extra retenus : {retained_extra}")

    if regressors:
        nan_counts = df[regressors].isna().sum()
        nan_regressors = nan_counts[nan_counts > 0]
        if not nan_regressors.empty:
            print(f"   ⚠️  NaN dans les regressors : {nan_regressors.to_dict()}")

    return df[available_cols].copy()



# ============================================================
# FONCTION DE MÉTRIQUES
# ============================================================
def evaluate_model(model, df_val):
    """Calcule MAE, RMSE, MAPE et R² sur une fenêtre de validation temporelle."""
    df_pred = df_val.copy()

    if model.growth == "logistic":
        df_pred["cap"]   = df_val["cap"]
        df_pred["floor"] = df_val["floor"]

    forecast = model.predict(df_pred)

    y_true = df_val["y"].values
    y_pred = forecast["yhat"].values
    mask   = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[mask], y_pred[mask]

    mae  = float(np.mean(np.abs(y_true - y_pred)))
    rmse = float(np.sqrt(np.mean((y_true - y_pred) ** 2)))
    mape = float(np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100)
    abs_y = float(np.abs(y_true).sum())
    wape = float("nan") if abs_y == 0 else float(np.abs(y_true - y_pred).sum() / abs_y * 100)

    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    return {"mae": mae, "rmse": rmse, "mape": mape, "wape": wape, "r2": r2}



# ============================================================
# CROSS-VALIDATION PROPHET
# ============================================================
def run_cross_validation(model, df_train, config, prm):
    """
    Cross-validation temporelle Prophet.

    Principe :
    - initial  : taille de la première fenêtre d'entraînement
    - period   : intervalle entre chaque fenêtre
    - horizon  : durée de prédiction évaluée à chaque fenêtre

    Plus robuste qu'un simple split train/val car évalue
    le modèle sur plusieurs périodes temporelles différentes.
    """
    cv_cfg = config.get("cross_validation", {})

    if not cv_cfg.get("enabled", False):
        return None

    try:
        initial = cv_cfg.get("initial", "365 days")
        period  = cv_cfg.get("period",  "90 days")
        horizon = cv_cfg.get("horizon", "30 days")

        print(f"--- Cross-Validation ---")
        print(f"   initial={initial}  period={period}  horizon={horizon}")

        df_cv = cross_validation(
            model,
            initial=initial,
            period=period,
            horizon=horizon,
            parallel="threads"
        )

        metrics_cv = performance_metrics(df_cv)

        mae_cv  = float(metrics_cv["mae"].mean())
        rmse_cv = float(metrics_cv["rmse"].mean())
        mape_cv = float(metrics_cv["mape"].mean() * 100)

        print(f"   CV MAE  : {mae_cv:.2f} W")
        print(f"   CV RMSE : {rmse_cv:.2f} W")
        print(f"   CV MAPE : {mape_cv:.1f}%")

        return {"cv_mae": mae_cv, "cv_rmse": rmse_cv, "cv_mape": mape_cv}

    except Exception as e:
        print(f"   ⚠️  Cross-validation échouée : {e}")
        return None


# ============================================================
# BASELINE NAÏVE (même heure -7 jours)
# ============================================================
def naive_baseline(df_full, df_val):
    lag = 7 * 24
    val_start_idx = len(df_full) - len(df_val)

    if val_start_idx < lag:
        print("   ⚠️  Baseline impossible (historique < 7 jours)")
        return

    y_true = df_val["y"].values
    y_pred = df_full["y"].iloc[val_start_idx - lag : val_start_idx - lag + len(df_val)].values
    mask   = ~(np.isnan(y_true) | np.isnan(y_pred))

    mae  = np.mean(np.abs(y_true[mask] - y_pred[mask]))
    rmse = np.sqrt(np.mean((y_true[mask] - y_pred[mask]) ** 2))

    print(f"   Baseline (j-7) → MAE={mae:.2f} W  RMSE={rmse:.2f} W")


# ============================================================
# CONSTRUCTION DU MODÈLE
# ============================================================
def build_prophet_model(config, prm=None):
    cfg = config["prophet"]

    # Overrides par site (optionnel dans config.yaml)
    # Exemple :
    #   site_overrides:
    #     "30000650805048":
    #       changepoint_prior_scale: 0.01
    #       growth: "flat"
    overrides = {}
    if prm and "site_overrides" in config:
        overrides = config["site_overrides"].get(str(prm), {})
        if overrides:
            print(f"   ⚙️  Overrides appliqués pour {prm} : {overrides}")

    def _cfg_value(*keys, default=None):
        for key in keys:
            if key in overrides:
                return overrides[key]
        for key in keys:
            if key in cfg:
                return cfg[key]
        return default

    growth = _cfg_value("growth", default="linear")
    changepoint_prior_scale = _cfg_value("changepoint_prior_scale", default=cfg["changepoint_prior_scale"])
    seasonality_prior_scale = _cfg_value("seasonality_prior_scale", default=cfg["seasonality_prior_scale"])
    seasonality_mode = _cfg_value("seasonality_mode", default=cfg["seasonality_mode"])
    fourier_order_daily = _cfg_value("daily_fourier_order", "fourier_order_daily", default=10)
    fourier_order_weekly = _cfg_value("weekly_fourier_order", "fourier_order_weekly", default=5)
    fourier_order_yearly = _cfg_value("yearly_fourier_order", "fourier_order_yearly", default=10)
    holidays_prior_scale = _cfg_value("holidays_prior_scale", default=cfg.get("holidays_prior_scale", 10))
    n_changepoints = _cfg_value("n_changepoints", default=cfg.get("n_changepoints", 25))
    changepoint_range = _cfg_value("changepoint_range", default=cfg.get("changepoint_range", 0.8))

    model = Prophet(
        holidays=holidays,
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
        growth=growth,
        seasonality_mode=seasonality_mode,
        changepoint_prior_scale=changepoint_prior_scale,
        seasonality_prior_scale=seasonality_prior_scale,
        holidays_prior_scale=holidays_prior_scale,
        n_changepoints=n_changepoints,
        changepoint_range=changepoint_range,
        interval_width=0.95
    )

    model.add_seasonality(name="daily",  period=1,      fourier_order=fourier_order_daily)
    model.add_seasonality(name="weekly", period=7,      fourier_order=fourier_order_weekly)
    model.add_seasonality(name="yearly", period=365.25, fourier_order=fourier_order_yearly)

    return model


def build_fit_options(config, prm=None):
    """Construit des options pour model.fit; mode avancé activé uniquement si demandé."""
    prophet_cfg = config.get("prophet", {})
    fit_cfg = prophet_cfg.get("fit", {}) or {}
    fit_enabled = bool(fit_cfg.get("enabled", False))

    overrides = {}
    if prm and "site_overrides" in config:
        overrides = config["site_overrides"].get(str(prm), {}) or {}

    fit_algorithm = overrides.get("fit_algorithm", fit_cfg.get("algorithm", "LBFGS"))
    fit_iter = int(overrides.get("fit_iter", fit_cfg.get("iter", 200)))
    fit_seed = int(overrides.get("fit_seed", fit_cfg.get("seed", 42)))
    fit_timeout = fit_cfg.get("timeout", None)

    output_dir = None
    if fit_enabled and fit_cfg.get("output_dir"):
        output_root = Path(fit_cfg.get("output_dir"))
        output_root.mkdir(parents=True, exist_ok=True)
        output_dir_path = output_root / f"prm_{prm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        output_dir_path.mkdir(parents=True, exist_ok=True)
        output_dir = str(output_dir_path)

    return {
        "enabled": fit_enabled,
        "algorithm": str(fit_algorithm),
        "iter": fit_iter,
        "seed": fit_seed,
        "timeout": fit_timeout,
        "output_dir": output_dir,
    }


# ============================================================
# SAUVEGARDE
# ============================================================
def save_model(model, config, metrics, prm):
    save_dir = Path(config["models"]["save_dir"])
    save_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Modèle versionné
    model_path = save_dir / f"prophet_model_{prm}_{timestamp}.pkl"
    with open(model_path, "wb") as f:
        pickle.dump(model, f)

    # Alias latest par PRM
    latest_path = save_dir / f"prophet_model_{prm}_latest.pkl"
    with open(latest_path, "wb") as f:
        pickle.dump(model, f)

    # Métriques JSON
    metrics_data = {
        "prm":              prm,
        "timestamp":        timestamp,
        "metrics":          metrics,
        "regressors":       list(model.extra_regressors.keys()),
        "seasonality_mode": model.seasonality_mode,
        "growth":           getattr(model, "growth", None),
        "hyperparameters": {
            "changepoint_prior_scale": model.changepoint_prior_scale,
            "seasonality_prior_scale": model.seasonality_prior_scale,
            "holidays_prior_scale": model.holidays_prior_scale,
            "n_changepoints": model.n_changepoints,
            "changepoint_range": model.changepoint_range,
            "daily_fourier_order": model.seasonalities.get("daily", {}).get("fourier_order"),
            "weekly_fourier_order": model.seasonalities.get("weekly", {}).get("fourier_order"),
            "yearly_fourier_order": model.seasonalities.get("yearly", {}).get("fourier_order"),
        },
    }
    metrics_path = save_dir / f"prophet_metrics_{prm}.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics_data, f, indent=2, ensure_ascii=False)

    print(f"   ✅ {model_path.name}")
    print(f"   ✅ {latest_path.name}")
    print(f"   ✅ {metrics_path.name}")


# ============================================================
# ENTRAÎNEMENT D'UN SITE
# ============================================================
def train_one_site(data_path, config, prm, config_path):
    """Entraîne et sauvegarde un modèle Prophet pour un PRM donné."""

    target_col      = config["target"]
    validation_days = config.get("validation", {}).get("days", 30)

    print(f"\n{'='*60}")
    print(f"  SITE : {prm}")
    print(f"{'='*60}")

    try:
        print("\n--- Preprocessing ---")
        df_pre = preprocess_pipeline(prm=prm)

        print("\n--- Feature Engineering ---")
        df_feat, config = feature_engineering_pipeline(prm=prm, source="csv", config_path=config_path)

        # Initialiser le DataLoader et sauvegarder les features
        loader = get_data_loader("csv", config_path)
        save_features(df_feat, prm, loader)

        print("\n--- Préparation Prophet ---")
        df_prophet = prepare_data_for_prophet(df_feat, target_col, config)
        regressors = [c for c in df_prophet.columns if c not in ["ds", "y", "cap", "floor"]]

        if not regressors:
            raise ValueError("Aucun regressor disponible après préparation des données Prophet.")

        # Split temporel
        split_date = df_prophet["ds"].max() - pd.Timedelta(days=validation_days)
        df_train   = df_prophet[df_prophet["ds"] < split_date].copy()
        df_val     = df_prophet[df_prophet["ds"] >= split_date].copy()

        print(f"\n   Train : {df_train['ds'].min().date()} → {df_train['ds'].max().date()} ({len(df_train):,} pts)")
        print(f"   Val   : {df_val['ds'].min().date()}   → {df_val['ds'].max().date()}   ({len(df_val):,} pts)")

        # Vérification données suffisantes
    # NOTE : train.py évalue sur un unique holdout fixe (derniers N jours).
    # Le grid search évalue via cross-validation temporelle (plusieurs fenêtres glissantes).
    # → Les métriques sont légitimement différentes : CV mesure la robustesse
    #   moyenne dans le temps, le holdout mesure la perf sur la dernière période.
    # Les hyperparamètres proviennent de site_overrides dans config.yaml,
    # mis à jour automatiquement après chaque grid search.
        if len(df_train) < 24 * 30:
            print(f"   ⚠️  Données insuffisantes ({len(df_train)} pts < 30 jours) — site ignoré")
            return None, None

        # Vérification regressors
        missing = [r for r in regressors if r not in df_train.columns]
        if missing:
            raise ValueError(f"Regressors manquants dans df_train : {missing}")

        # Modèle
        model = build_prophet_model(config, prm=prm)
        for col in regressors:
            model.add_regressor(col, standardize=False)

        print("\n--- Entraînement ---")
        fit_options = build_fit_options(config, prm=prm)

        if not fit_options["enabled"]:
            print("   Mode fit notebook-compatible (model.fit(df_train))")
            model.fit(df_train)
        else:
            fit_kwargs = {
                "iter": fit_options["iter"],
                "seed": fit_options["seed"],
            }

            if fit_options["output_dir"]:
                # Sécurise les répertoires temporaires pour CmdStan (Windows)
                cmdstan_tmp = Path(fit_options["output_dir"]).parent
                os.environ["TMP"] = str(cmdstan_tmp.resolve())
                os.environ["TEMP"] = str(cmdstan_tmp.resolve())
                fit_kwargs["output_dir"] = fit_options["output_dir"]

            if fit_options["timeout"] is not None:
                fit_kwargs["timeout"] = fit_options["timeout"]

            print(
                f"   Fit options: algorithm={fit_options['algorithm']} "
                f"iter={fit_options['iter']} seed={fit_options['seed']}"
            )
            if fit_options["output_dir"]:
                print(f"   CmdStan output_dir: {fit_options['output_dir']}")

            model.fit(df_train, algorithm=fit_options["algorithm"], **fit_kwargs)

        # Évaluation
        print("\n--- Évaluation ---")
        naive_baseline(df_prophet, df_val)
        metrics = evaluate_model(model, df_val)
        print(f"   Prophet → MAE={metrics['mae']:.2f} W  RMSE={metrics['rmse']:.2f} W  "
              f"MAPE={metrics['mape']:.1f}%  WAPE={metrics['wape']:.1f}%  R²={metrics['r2']:.4f}")

        # Sauvegarde
        print("\n--- Sauvegarde ---")
        save_model(model, config, metrics, prm)

        # MLflow tracking (activé via config.yaml : mlflow.enabled: true)
        if MLFLOW_AVAILABLE and config.get("mlflow", {}).get("enabled", False):
            try:
                print("\n--- MLflow ---")
                setup_mlflow(config_path)

                # Adapter les clés de métriques au format attendu par mlflow_utils
                metrics_mlflow = {
                    "MAE":  metrics["mae"],
                    "RMSE": metrics["rmse"],
                    "MAPE": metrics["mape"],
                    "WAPE": metrics["wape"],
                    "R2":   metrics["r2"],
                }
                run_id = log_prophet_training(
                    model=model,
                    df_train=df_train,
                    df_val=df_val,
                    metrics=metrics_mlflow,
                    config=config,
                    model_suffix=prm
                )
                metrics["mlflow_run_id"] = run_id
                print(f"   ✅ Run MLflow : {run_id}")
            except Exception as e:
                print(f"   ⚠️  MLflow échoué (non bloquant) : {e}")
        elif not MLFLOW_AVAILABLE:
            pass  # mlflow_utils.py absent — silencieux
        else:
            print("\n   ℹ️  MLflow désactivé (mlflow.enabled: false dans config.yaml)")

        return model, metrics

    except Exception as e:
        print(f"\n   ❌ Erreur site {prm} : {e}")
        import traceback
        traceback.print_exc()
        return None, None


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Entraînement Prophet multi-sites")
    parser.add_argument(
        "--prm", type=str, nargs="+", default=None,
        help="PRM(s) à entraîner. Si absent, tous les sites sont traités."
    )
    parser.add_argument(
        "--config", type=str, default="config/config.yaml",
        help="Chemin vers config.yaml"
    )
    args = parser.parse_args()

    config = load_config(args.config)
    if config is None:
        raise ValueError(f"Impossible de charger la config depuis {args.config}")
    raw_data_dir = Path(config["data"]["raw"]) / "sites"

    # Détecter tous les sites disponibles
    all_prm_files = detect_prms(raw_data_dir)

    if not all_prm_files:
        raise FileNotFoundError(f"Aucun fichier dataclean_prm_*.csv dans {raw_data_dir}")

    # Filtrer selon --prm si fourni
    if args.prm:
        prm_files = {}
        for prm in args.prm:
            if prm in all_prm_files:
                prm_files[prm] = all_prm_files[prm]
            else:
                print(f"⚠️  PRM {prm} introuvable dans {raw_data_dir}")
    else:
        prm_files = all_prm_files

    if not prm_files:
        raise ValueError("Aucun site valide à entraîner.")

    print(f"\n🏭 {len(prm_files)} site(s) à entraîner : {list(prm_files.keys())}")

    # Entraîner chaque site
    results = {}
    for prm, data_path in prm_files.items():
        _, metrics = train_one_site(data_path, config, prm, args.config)
        results[prm] = metrics

    # Résumé
    print(f"\n{'='*60}")
    print("  RÉSUMÉ")
    print(f"{'='*60}")
    print(f"  {'PRM':<20} {'MAE':>8} {'RMSE':>8} {'MAPE':>7} {'WAPE':>7} {'R²':>8}")
    print(f"  {'-'*64}")
    for prm, m in results.items():
        if m:
            print(f"  {prm:<20} {m['mae']:>7.1f}  {m['rmse']:>7.1f}  {m['mape']:>6.1f}%  {m['wape']:>6.1f}%  {m['r2']:>7.4f}")
        else:
            print(f"  {prm:<20}  {'ÉCHEC':>40}")
