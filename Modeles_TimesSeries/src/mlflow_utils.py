"""
Utilitaires MLflow pour le tracking des modèles Prophet.
"""
import mlflow
from pathlib import Path
import yaml


def setup_mlflow(config_path="config/config.yaml"):
    """
    Configure MLflow avec le tracking URI et l'experiment.
    """
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    mlflow_config = config.get('mlflow', {})

    tracking_uri = mlflow_config.get('tracking_uri', 'mlruns')
    mlflow.set_tracking_uri(tracking_uri)

    experiment_name = mlflow_config.get('experiment_name', 'Prophet_Energy_Forecast')
    mlflow.set_experiment(experiment_name)

    print(f"✅ MLflow configuré : {tracking_uri}")
    print(f"✅ Experiment : {experiment_name}")


def _extract_model_params(model, resolved_params=None):
    """
    Extrait les hyperparamètres réellement utilisés depuis l'objet Prophet entraîné.
    Source de vérité absolue : l'objet model lui-même.

    Les Fourier orders ne sont pas des attributs directs de Prophet —
    ils sont récupérés depuis resolved_params si fourni.

    Args:
        model: Modèle Prophet entraîné
        resolved_params: Dict des params résolus retourné par build_prophet_model (optionnel)

    Returns:
        Dict des paramètres prêt pour mlflow.log_params()
    """
    # Params directement lisibles depuis le modèle — 100% fiables
    params = {
        "growth":                   model.growth,
        "changepoint_prior_scale":  model.changepoint_prior_scale,
        "seasonality_prior_scale":  model.seasonality_prior_scale,
        "seasonality_mode":         model.seasonality_mode,
        "n_changepoints":           model.n_changepoints,
        "changepoint_range":        model.changepoint_range,
        "holidays_prior_scale":     model.holidays_prior_scale,
        "interval_width":           model.interval_width,
        "regressors":               list(model.extra_regressors.keys()),
    }

    # Fourier orders : non exposés comme attributs directs de Prophet
    # → récupérés depuis resolved_params si disponible
    if resolved_params is not None:
        params["fourier_order_daily"]  = resolved_params.get("fourier_order_daily")
        params["fourier_order_weekly"] = resolved_params.get("fourier_order_weekly")
        params["fourier_order_yearly"] = resolved_params.get("fourier_order_yearly")
    else:
        # Fallback : lire depuis les seasonalities enregistrées dans le modèle
        for name, s in model.seasonalities.items():
            params[f"fourier_order_{name}"] = s["fourier_order"]

    # MLflow n'accepte pas les listes → convertir en string
    params["regressors"] = ", ".join(params["regressors"]) if params["regressors"] else "none"

    return params


def log_prophet_training(model, df_train, df_val, metrics, config,
                         model_suffix="", resolved_params=None):
    """
    Log l'entraînement Prophet dans MLflow.

    Args:
        model: Modèle Prophet entraîné
        df_train: Données d'entraînement
        df_val: Données de validation
        metrics: Dict des métriques (MAE, RMSE, MAPE, R2)
        config: Configuration complète
        model_suffix: Suffixe du modèle (ex: PRM)
        resolved_params: Dict des hyperparamètres résolus (après site_overrides)
                         retourné par build_prophet_model. Recommandé pour
                         garantir la cohérence avec les Fourier orders.
    """
    with mlflow.start_run(run_name=f"prophet_{model_suffix}" if model_suffix else "prophet"):

        # 1. Log des paramètres Prophet — lus depuis le modèle réel
        prophet_params = _extract_model_params(model, resolved_params)
        mlflow.log_params(prophet_params)

        # 2. Log des infos de données
        mlflow.log_params({
            'train_size':  len(df_train),
            'val_size':    len(df_val),
            'train_start': str(df_train['ds'].min().date()),
            'train_end':   str(df_train['ds'].max().date()),
            'site_prm':    model_suffix if model_suffix else 'all',
        })

        # 3. Log des métriques de validation
        mlflow.log_metrics({
            'val_mae':  metrics['MAE'],
            'val_rmse': metrics['RMSE'],
            'val_mape': metrics['MAPE'],
            'val_r2':   metrics['R2'],
        })

        # 4. Log du modèle Prophet
        mlflow.prophet.log_model(model, "model")

        # 5. Log des tags
        mlflow.set_tags({
            'model_type': 'Prophet',
            'framework':  'Prophet',
            'task':       'timeseries_forecasting',
            'target':     config.get('target', 'puissance_kw'),
            'site_prm':   model_suffix if model_suffix else 'all',
        })

        # 6. Graphiques Prophet
        try:
            from prophet.plot import plot_plotly, plot_components_plotly

            forecast_val = model.predict(df_val)

            fig = plot_plotly(model, forecast_val)
            mlflow.log_figure(fig, "prophet_forecast.html")

            fig_comp = plot_components_plotly(model, forecast_val)
            mlflow.log_figure(fig_comp, "prophet_components.html")

            print("✅ Graphiques Prophet loggés dans MLflow")
        except ImportError:
            print("⚠️  Plotly non disponible, graphiques non générés")
        except Exception as e:
            print(f"⚠️  Erreur lors de la génération des graphiques : {e}")

        # 7. Fichier résumé
        summary_path = Path("mlruns_temp") / "model_summary.txt"
        summary_path.parent.mkdir(exist_ok=True)

        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("RÉSUMÉ DE L'ENTRAÎNEMENT PROPHET\n")
            f.write("=" * 80 + "\n\n")
            f.write(f"Site PRM      : {model_suffix if model_suffix else 'all'}\n")
            f.write(f"Train         : {df_train['ds'].min().date()} → {df_train['ds'].max().date()} ({len(df_train):,} pts)\n")
            f.write(f"Validation    : {df_val['ds'].min().date()} → {df_val['ds'].max().date()} ({len(df_val):,} pts)\n\n")
            f.write("Métriques de validation :\n")
            f.write(f"  MAE  : {metrics['MAE']:.4f} W\n")
            f.write(f"  RMSE : {metrics['RMSE']:.4f} W\n")
            f.write(f"  MAPE : {metrics['MAPE']:.2f}%\n")
            f.write(f"  R²   : {metrics['R2']:.4f}\n\n")
            f.write("Paramètres Prophet (réels, lus depuis le modèle) :\n")
            for key, value in prophet_params.items():
                f.write(f"  {key}: {value}\n")

        mlflow.log_artifact(str(summary_path))
        summary_path.unlink()

        run_id = mlflow.active_run().info.run_id
        print(f"✅ Run MLflow enregistré : {run_id}")

        return run_id


def log_longterm_predictions(df_predictions, prm=None, nb_annees=3):
    """
    Log les prédictions long terme dans MLflow.
    """
    with mlflow.start_run(run_name=f"prediction_longterm_{prm}" if prm else "prediction_longterm"):

        mlflow.log_params({
            'horizon_years':    nb_annees,
            'horizon_hours':    len(df_predictions),
            'site_prm':         prm if prm else 'all',
            'prediction_start': str(df_predictions['datetime'].min()),
            'prediction_end':   str(df_predictions['datetime'].max()),
        })

        mlflow.log_metrics({
            'pred_mean_kw': float(df_predictions['puissance_kw_pred'].mean()),
            'pred_min_kw':  float(df_predictions['puissance_kw_pred'].min()),
            'pred_max_kw':  float(df_predictions['puissance_kw_pred'].max()),
            'pred_std_kw':  float(df_predictions['puissance_kw_pred'].std()),
        })

        if 'annee' in df_predictions.columns:
            for annee, groupe in df_predictions.groupby('annee'):
                mlflow.log_metric(f'pred_mean_kw_{annee}', float(groupe['puissance_kw_pred'].mean()))

        if 'puissance_kw_lower' in df_predictions.columns:
            mlflow.log_metrics({
                'pred_lower_mean':          float(df_predictions['puissance_kw_lower'].mean()),
                'pred_upper_mean':          float(df_predictions['puissance_kw_upper'].mean()),
                'confidence_interval_width': float((df_predictions['puissance_kw_upper'] - df_predictions['puissance_kw_lower']).mean()),
            })

        mlflow.set_tags({
            'task':       'longterm_forecast',
            'model_type': 'Prophet',
        })

        run_id = mlflow.active_run().info.run_id
        print(f"✅ Prédictions loggées dans MLflow : {run_id}")

        return run_id


def load_model_from_mlflow(run_id):
    """
    Charge un modèle Prophet depuis MLflow.
    """
    model_uri = f"runs:/{run_id}/model"
    model = mlflow.prophet.load_model(model_uri)
    print(f"✅ Modèle chargé depuis MLflow : {run_id}")
    return model


def compare_models(experiment_name="Prophet_Energy_Forecast", metric="val_rmse"):
    """
    Compare les modèles d'un experiment par métrique.
    """
    experiment = mlflow.get_experiment_by_name(experiment_name)
    if experiment is None:
        print(f"❌ Experiment '{experiment_name}' introuvable")
        return None

    runs = mlflow.search_runs(
        experiment_ids=[experiment.experiment_id],
        order_by=[f"metrics.{metric} ASC"]
    )

    if len(runs) == 0:
        print(f"❌ Aucun run trouvé dans l'experiment '{experiment_name}'")
        return None

    print(f"📊 {len(runs)} runs trouvés")
    print(f"\n🏆 Meilleur modèle (par {metric}) :")
    best_run = runs.iloc[0]
    print(f"   Run ID  : {best_run['run_id']}")
    print(f"   {metric} : {best_run[f'metrics.{metric}']:.4f}")

    return runs