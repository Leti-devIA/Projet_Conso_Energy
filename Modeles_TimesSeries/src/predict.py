"""
Étape 4 du pipeline ML : prédiction avec un modèle Prophet entraîné.

Ce module :
- charge le modèle sauvegardé,
- construit le DataFrame futur à partir de la météo,
- produit un CSV de prévision exploitable dans le dashboard.
"""

import pandas as pd
import numpy as np
import pickle
from pathlib import Path

from .feature_engineering import feature_engineering_pipeline
from .utils import load_config, build_jour_ferie_index

# ===================================================
# CONFIGURATION
# ===================================================
config = load_config("config/config.yaml")

# ============================================================
# CHARGEMENT MODÈLE
# ============================================================
def load_prophet_model(model_dir="models/saved", prm=None):
    model_dir = Path(model_dir)
    candidates = []

    if prm:
        p = model_dir / f"prophet_model_{prm}_latest.pkl"
        if p.exists():
            candidates.append(p)
        candidates += sorted(model_dir.glob(f"prophet_model_{prm}_2*.pkl"))

    p = model_dir / "prophet_model_latest.pkl"
    if p.exists():
        candidates.append(p)

    candidates += sorted(model_dir.glob("prophet_model_2*.pkl"))

    if not candidates:
        raise FileNotFoundError(f"Aucun modèle Prophet trouvé dans {model_dir}")

    model_path = candidates[0]
    print(f"📦 Modèle chargé : {model_path.name}")
    with open(model_path, "rb") as f:
        return pickle.load(f)


# ============================================================
# CONSTRUCTION DATAFRAME FUTUR
# ============================================================
def build_future_from_features(df_features, meteo_future_df, model):
    """
    Prépare le DataFrame futur pour Prophet à partir des features pré-calculées.

    Stratégie lags :
    - lag_24  : les 24 premières heures futures → valeurs historiques réelles (j-1)
                au-delà → recyclage saisonnier (même heure, j-7 dans l'historique)
    - lag_168 : les 168 premières heures futures → valeurs historiques réelles (j-7)
                au-delà → recyclage saisonnier (même heure, j-7 dans l'historique)
    - Rolling/std/min/max : exclus (non fiables en prévision future)
    """
    regressors = list(model.extra_regressors.keys())

    last_datetime = df_features["datetime"].max()
    horizon = len(meteo_future_df)
    future_datetimes = pd.date_range(
        start=last_datetime + pd.Timedelta(hours=1),
        periods=horizon,
        freq='h'
    )

    df_future = pd.DataFrame({"ds": future_datetimes})

    # ── Regressors cycliques
    cyclic = ['heure_sin', 'heure_cos', 'jour_sin', 'jour_cos', 'is_weekend']
    for feat in cyclic:
        if feat in regressors:
            if feat == 'heure_sin':
                df_future[feat] = np.sin(2 * np.pi * df_future['ds'].dt.hour / 24)
            elif feat == 'heure_cos':
                df_future[feat] = np.cos(2 * np.pi * df_future['ds'].dt.hour / 24)
            elif feat == 'jour_sin':
                df_future[feat] = np.sin(2 * np.pi * df_future['ds'].dt.dayofweek / 7)
            elif feat == 'jour_cos':
                df_future[feat] = np.cos(2 * np.pi * df_future['ds'].dt.dayofweek / 7)
            elif feat == 'is_weekend':
                df_future[feat] = (df_future['ds'].dt.dayofweek >= 5).astype(int)

    # ── Météo future
    meteo_future_df = meteo_future_df.copy()
    meteo_future_df['ds'] = pd.to_datetime(meteo_future_df['datetime']).dt.round('h')
    meteo_future_df = meteo_future_df.drop_duplicates(subset=['ds']).set_index('ds')

    for col in ['temperature', 'humidite', 'vitesse_vent', 'couverture_nuages']:
        if col in regressors:
            if col in meteo_future_df.columns:
                df_future[col] = df_future['ds'].map(meteo_future_df[col])
                n_missing = df_future[col].isna().sum()
                if n_missing > 0:
                    print(f"⚠️ {n_missing} NaN pour '{col}' → interpolation")
                    df_future[col] = df_future[col].interpolate(method='linear')
                    df_future[col] = df_future[col].ffill().bfill()
            elif col in df_features.columns:
                hist_mean = float(df_features[col].dropna().mean())
                print(f"⚠️ Colonne météo '{col}' absente du futur → moyenne historique ({hist_mean:.2f})")
                df_future[col] = hist_mean
            else:
                print(f"⚠️ Colonne météo '{col}' absente partout → 0")
                df_future[col] = 0.0

    # ── Interaction météo (temp_x_heure_sin, temp_x_heure_cos)
    if 'temp_x_heure_sin' in regressors and 'temperature' in df_future.columns:
        df_future['temp_x_heure_sin'] = df_future['temperature'] * df_future['heure_sin']
    if 'temp_x_heure_cos' in regressors and 'temperature' in df_future.columns:
        df_future['temp_x_heure_cos'] = df_future['temperature'] * df_future['heure_cos']

    # ── Précipitation (pas dans météo future générée, on met 0)
    if 'precipitation' in regressors:
        if 'precipitation' in meteo_future_df.columns:
            df_future['precipitation'] = df_future['ds'].map(meteo_future_df['precipitation']).fillna(0.0)
        elif 'precipitation' not in df_future.columns:
            df_future['precipitation'] = 0.0

    # ── Jours fériés
    years = df_future['ds'].dt.year.unique()
    ferie_set = build_jour_ferie_index(years)
    if 'is_holiday' in regressors:
        df_future['is_holiday'] = df_future['ds'].dt.date.isin(ferie_set).astype(int)
    if 'jour_ferie' in regressors:
        df_future['jour_ferie'] = df_future['ds'].dt.date.isin(ferie_set).astype(int)

    # ── Lags : stratégie par profil horaire moyen (robuste sur long horizon)
    lag_cols = [c for c in regressors if c.startswith('puissance_lag_')]
    if lag_cols:
        hist = df_features[['datetime', 'puissance_moy_heure']].copy()
        hist['datetime'] = pd.to_datetime(hist['datetime'])
        hist = hist.set_index('datetime')['puissance_moy_heure']

        # Profil de référence : moyenne par (heure, jour_semaine) sur l'historique
        # On exclut les 30 derniers jours pour éviter les pics atypiques récents
        hist_stable = hist.iloc[:-24*30] if len(hist) > 24*30 else hist
        profile = (
            hist_stable
            .groupby([hist_stable.index.hour, hist_stable.index.dayofweek])
            .mean()
        )
        # profile.index = (hour, dayofweek)

        for col in lag_cols:
            lag = int(col.split('_')[-1])

            values = []
            for future_dt in df_future['ds']:
                target_dt = future_dt - pd.Timedelta(hours=lag)

                if target_dt in hist.index:
                    # Dans l'historique réel → valeur exacte
                    values.append(hist[target_dt])
                else:
                    # Hors historique → profil moyen (heure, dow) de référence
                    key = (future_dt.hour, future_dt.dayofweek)
                    if key in profile.index:
                        values.append(profile[key])
                    else:
                        values.append(float(hist_stable.mean()))

            df_future[col] = values
            n_nan = df_future[col].isna().sum()
            print(f"   ✅ {col} | NaN={n_nan} | "
                f"moy={df_future[col].mean():.0f} | "
                f"ex={df_future[col].head(3).values.round(0)}")

    # ── Colonnes rolling/std/min/max : si présentes dans regressors, on met la moyenne historique
    # (ne pas mettre 0 car ça biaiserait fortement le modèle)
    stat_cols = [c for c in regressors if any(k in c for k in ['roll', 'std_', 'min_', 'max_'])]
    if stat_cols:
        hist_target = df_features['puissance_moy_heure']
        for col in stat_cols:
            hist_mean = float(hist_target.mean())
            df_future[col] = hist_mean
            print(f"   ℹ️  {col} → moyenne historique ({hist_mean:.0f} W)")

    # ── Cap/Floor logistic
    if hasattr(model, 'growth') and model.growth == 'logistic':
        df_future['cap']   = df_features['cap'].iloc[-1]
        df_future['floor'] = df_features['floor'].iloc[-1]

    # ── Colonnes manquantes → 0 en dernier recours
    for r in regressors:
        if r not in df_future.columns:
            print(f"   ⚠️  {r} manquant → 0 (vérifier)")
            df_future[r] = 0

    ordered_cols = ['ds']
    if hasattr(model, 'growth') and model.growth == 'logistic':
        ordered_cols += [c for c in ['cap', 'floor'] if c in df_future.columns]
    ordered_cols += regressors

    return df_future[ordered_cols].copy()


# ============================================================
# PREDICTION FUTURE
# ============================================================
def predict_future(prm, meteo_future_df, model_dir="models/saved", config_path="config/config.yaml"):
    """
    Lance la prédiction pour un PRM à partir d'un DataFrame météo futur.
    """
    print(f"\n🔮 PRÉDICTION PROPHET LONG TERME — PRM {prm}")

    # ── Charger le modèle
    model = load_prophet_model(model_dir, prm=prm)
    regressors = list(model.extra_regressors.keys())
    print(f"📋 Regressors attendus : {regressors}")

    # ── Charger les features calculées pour ce PRM
    df_features, _ = feature_engineering_pipeline(prm=prm, source='csv', config_path=config_path)

    # ── Construire le DataFrame futur
    df_future = build_future_from_features(df_features, meteo_future_df, model)

    # ── Prédiction
    forecast = model.predict(df_future)

    # ── Clipping négatif
    clip_negative = load_config(config_path).get('prediction', {}).get('clip_negative', True)
    if clip_negative:
        forecast['yhat'] = forecast['yhat'].clip(lower=0)
        forecast['yhat_lower'] = forecast['yhat_lower'].clip(lower=0)

    # ── Résultat final
    df_pred = pd.DataFrame({
        'datetime': forecast['ds'],
        'yhat': forecast['yhat'],
        'yhat_lower': forecast['yhat_lower'],
        'yhat_upper': forecast['yhat_upper'],
    })

    print(f"✅ {len(df_pred)} heures prédites")
    return df_pred


# ============================================================
# FORMAT POUR DASHBOARD
# ============================================================
def format_predictions_for_dashboard(df_pred, historique_start):
    df = df_pred.copy()
    df['puissance_moy_heure_pred'] = df['yhat']
    df['puissance_moy_heure_pred_lower'] = df['yhat_lower']
    df['puissance_moy_heure_pred_upper'] = df['yhat_upper']
    df['jours_depuis_debut'] = (df['datetime'] - pd.to_datetime(historique_start)).dt.total_seconds()/86400
    df['annee'] = df['datetime'].dt.year
    return df[['datetime','puissance_moy_heure_pred','puissance_moy_heure_pred_lower','puissance_moy_heure_pred_upper','jours_depuis_debut','annee']]



# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prédiction Prophet long terme")
    parser.add_argument("--prm", type=str, help="Numéro PRM (résout les chemins automatiquement)")
    parser.add_argument("--historique", type=str, default=None, help="Fichier historique CSV")
    parser.add_argument("--meteo", type=str, default=None, help="Fichier météo CSV (horaire)")
    parser.add_argument("--horizon", type=int, default=None, help="Heures à prédire (défaut : config.yaml)")
    parser.add_argument("--model-dir", type=str, default="models/saved")
    parser.add_argument("--config", type=str, default="config/config.yaml")
    parser.add_argument("--output", type=str, default=None, help="Fichier de sortie CSV")

    args = parser.parse_args()

    # Mode PRM : résolution automatique des chemins
    if args.prm:
        args.historique = args.historique or f"data/processed/data_processed_{args.prm}.csv"
        args.meteo      = args.meteo      or f"data/raw/meteo/meteo_horaire_{args.prm}.csv"
        args.output     = args.output     or f"data/predictions/prophet_predictions_{args.prm}.csv"

    if not args.historique or not args.meteo:
        print("❌ Erreur : utilisez --prm ou (--historique + --meteo)")
        print("  python src/predict.py --prm 30000250086126")
        print("  python src/predict.py --historique data.csv --meteo meteo.csv --output out.csv")
        exit(1)

    print(f"📂 Historique : {args.historique}")
    print(f"📂 Météo      : {args.meteo}")

    historique = pd.read_csv(args.historique)
    meteo      = pd.read_csv(args.meteo)

    print(f"   {len(historique):,} lignes historiques")
    print(f"   {len(meteo):,} lignes météo")

    # Prédiction
    meteo_df = pd.read_csv(args.meteo)
    df_pred = predict_future(prm=args.prm, meteo_future_df=meteo_df,
                             model_dir=args.model_dir, config_path=args.config)

    # Formater pour le dashboard
    df_csv = format_predictions_for_dashboard(
        df_pred,
        historique_start=historique["datetime"].min()
    )

    # Sauvegarde
    output_path = args.output or f"data/predictions/prophet_predictions_{args.prm}.csv"
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df_csv.to_csv(output_path, index=False)
    print(f"\n💾 Prédictions sauvegardées : {output_path}")