"""
Script de prédiction itérative avec sauvegarde des résultats.
"""
import pandas as pd
import numpy as np
import pickle
import json
import yaml
from pathlib import Path
from tensorflow.keras.models import load_model

from feature_engineering import (
    create_temporal_features,
    create_lag_features,
    create_rolling_features,
    create_statistical_features,
    create_interaction_features
)


def load_config(config_path="config/config.yaml"):
    """Charge la configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_model_artifacts(model_dir="models/saved", use_latest=True, model_suffix=None):
    """
    Charge le modèle, les scalers et la configuration.

    Args:
        model_dir: Répertoire des modèles sauvegardés
        use_latest: Si True, charge la version 'latest', sinon demande le timestamp
        model_suffix: Suffixe du modèle (ex: 'lstm_energy_forecast_30000540191777') pour charger un modèle spécifique

    Returns:
        Tuple (model, scaler_X, scaler_y, config)
    """
    model_dir = Path(model_dir)

    if use_latest:
        if model_suffix:
            # Charger le modèle spécifique au site
            model_path = model_dir / f"lstm_energy_forecast_latest_{model_suffix}.h5"
            scalers_path = model_dir / f"scalers_latest_{model_suffix}.pkl"
            config_path = model_dir / f"config_latest_{model_suffix}.json"
        else:
            # Charger le modèle générique
            model_path = model_dir / "lstm_energy_forecast_latest.h5"
            scalers_path = model_dir / "scalers_latest.pkl"
            config_path = model_dir / "config_latest.json"
    else:
        # Lister les modèles disponibles
        models = list(model_dir.glob("lstm_energy_forecast_*.h5"))
        print("Modèles disponibles :")
        for i, m in enumerate(models):
            print(f"  {i}: {m.name}")

        choice = int(input("Choisir le modèle (numéro) : "))
        model_path = models[choice]

        # Extraire le timestamp
        timestamp = model_path.stem.split('_')[-1]
        scalers_path = model_dir / f"scalers_{timestamp}.pkl"
        config_path = model_dir / f"config_{timestamp}.json"

    print(f"📦 Chargement du modèle : {model_path}")
    model = load_model(model_path)

    print(f"📦 Chargement des scalers : {scalers_path}")
    with open(scalers_path, 'rb') as f:
        scalers = pickle.load(f)
    scaler_X = scalers['scaler_X']
    scaler_y = scalers['scaler_y']

    print(f"📦 Chargement de la config : {config_path}")
    with open(config_path, 'r', encoding='utf-8') as f:
        model_config = json.load(f)

    return model, scaler_X, scaler_y, model_config


def create_all_features(df, target_col):
    """
    Crée toutes les features nécessaires pour la prédiction.

    Args:
        df: DataFrame avec colonnes datetime, puissance_kw, temperature, humidite, jour_ferie
        target_col: Nom de la colonne cible

    Returns:
        DataFrame avec toutes les features
    """
    df = df.copy()

    # Features temporelles
    df = create_temporal_features(df)

    # Features historiques
    df = create_lag_features(df, target_col, lags=[1, 2, 3, 24, 48])
    df = create_rolling_features(df, target_col, windows=[3, 6, 12, 24])
    df = create_statistical_features(df, target_col)

    # Interactions
    df = create_interaction_features(df)

    return df


def predict_future(historique_df, meteo_future_df, model_dir="models/saved",
                   config_path="config/config.yaml", horizon=None, model_suffix=None):
    """
    Prédit les consommations futures de manière itérative.

    Args:
        historique_df: DataFrame avec au moins 48h d'historique
                      Colonnes : datetime, puissance_kw, temperature, humidite, jour_ferie
        meteo_future_df: DataFrame avec données météo futures
                        Colonnes : datetime, temperature, humidite, jour_ferie
        model_dir: Répertoire des modèles
        config_path: Chemin vers la configuration
        horizon: Nombre d'heures à prédire (si None, utilise len(meteo_future_df))
        model_suffix: Suffixe du modèle à charger (ex: 'lstm_energy_forecast_30000540191777')

    Returns:
        DataFrame avec les prédictions
    """
    print("=" * 60)
    print("PRÉDICTION ITÉRATIVE")
    print("=" * 60)

    # Charger la configuration
    config = load_config(config_path)

    # Charger le modèle et les artifacts
    model, scaler_X, scaler_y, model_config = load_model_artifacts(model_dir, model_suffix=model_suffix)

    window = model_config['model_architecture']['window']
    features = model_config['features']
    target_col = model_config['target']

    # Déterminer l'horizon
    if horizon is None:
        horizon = len(meteo_future_df)
    horizon = min(horizon, len(meteo_future_df))

    print(f"✅ Modèle chargé")
    print(f"✅ Window size : {window}")
    print(f"✅ Nombre de features : {len(features)}")
    print(f"✅ Horizon de prédiction : {horizon} heures")

    # Vérifier qu'on a assez d'historique
    if len(historique_df) < window:
        raise ValueError(f"Besoin d'au moins {window}h d'historique, {len(historique_df)}h fourni")

    # Préparer les données
    historique_df = historique_df.copy()
    meteo_future_df = meteo_future_df.copy()

    historique_df['datetime'] = pd.to_datetime(historique_df['datetime'])
    meteo_future_df['datetime'] = pd.to_datetime(meteo_future_df['datetime'])

    historique_df = historique_df.sort_values('datetime').reset_index(drop=True)
    meteo_future_df = meteo_future_df.sort_values('datetime').reset_index(drop=True)

    # Renommer la colonne cible si nécessaire
    if 'puissance_kw' in historique_df.columns and target_col not in historique_df.columns:
        historique_df[target_col] = historique_df['puissance_kw']

    # Prendre les dernières 48h d'historique
    df_work = historique_df.tail(window).copy()

    # Créer les features pour l'historique
    df_work = create_all_features(df_work, target_col)

    # Boucle de prédiction itérative
    predictions = []

    print(f"\n🔮 Début des prédictions...")

    for i in range(horizon):
        # Obtenir la dernière fenêtre
        window_data = df_work.tail(window).copy()

        # Vérifier que toutes les features sont présentes
        missing = [f for f in features if f not in window_data.columns]
        if missing:
            print(f"⚠️ Features manquantes : {missing}")
            break

        # Sélectionner les features
        X_window = window_data[features].values

        # Remplacer les NaN par 0
        X_window = np.nan_to_num(X_window, nan=0.0)

        # Normaliser
        X_window_scaled = scaler_X.transform(X_window)

        # Reshape pour le modèle
        X_window_seq = X_window_scaled.reshape(1, window, len(features))

        # Prédire
        y_pred_scaled = model.predict(X_window_seq, verbose=0)
        y_pred = scaler_y.inverse_transform(y_pred_scaled)[0, 0]

        # Clipper les valeurs négatives
        y_pred = max(0, y_pred)

        # Obtenir la date/heure future
        next_datetime = meteo_future_df.iloc[i]['datetime']

        # Ajouter la prédiction
        predictions.append({
            'datetime': next_datetime,
            'puissance_kw_pred': y_pred
        })

        # Créer une nouvelle ligne avec la prédiction
        new_row = pd.DataFrame([{
            'datetime': next_datetime,
            target_col: y_pred,
            'temperature': meteo_future_df.iloc[i]['temperature'],
            'humidite': meteo_future_df.iloc[i]['humidite'],
            'jour_ferie': meteo_future_df.iloc[i]['jour_ferie']
        }])

        # Ajouter au DataFrame de travail
        df_work = pd.concat([df_work, new_row], ignore_index=True)

        # Recréer toutes les features
        df_work = create_all_features(df_work, target_col)

        # Afficher la progression
        if (i + 1) % 24 == 0:
            print(f"  ✓ {i + 1}/{horizon} heures prédites")

    # Créer le DataFrame de résultats
    df_predictions = pd.DataFrame(predictions)

    print(f"\n✅ {len(df_predictions)} prédictions générées")
    print(f"📅 Période : {df_predictions['datetime'].min()} → {df_predictions['datetime'].max()}")
    print(f"📊 Consommation prédite :")
    print(f"   Min     : {df_predictions['puissance_kw_pred'].min():.2f} kW")
    print(f"   Max     : {df_predictions['puissance_kw_pred'].max():.2f} kW")
    print(f"   Moyenne : {df_predictions['puissance_kw_pred'].mean():.2f} kW")
    print("=" * 60)

    return df_predictions


def save_predictions(df_predictions, output_path=None, config_path="config/config.yaml"):
    """
    Sauvegarde les prédictions.

    Args:
        df_predictions: DataFrame avec les prédictions
        output_path: Chemin de sortie (si None, utilise data/predictions/)
        config_path: Chemin vers la configuration
    """
    from datetime import datetime
    
    if output_path is None:
        config = load_config(config_path)
        predictions_dir = Path(config['data']['predictions'])
        predictions_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = predictions_dir / f"predictions_{timestamp}.csv"

    df_predictions.to_csv(output_path, index=False)
    print(f"\n✅ Prédictions sauvegardées : {output_path}")

    return output_path

    # Prédire
    # predictions = predict_future(historique, meteo_future, horizon=360)

    # Sauvegarder
    # save_predictions(predictions)

    print("⚠️ Décommenter le code ci-dessus et fournir les données pour exécuter")
