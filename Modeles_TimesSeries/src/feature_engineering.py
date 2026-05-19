"""
Étape 2 du pipeline ML : feature engineering.

Ce module construit des variables explicatives utiles à Prophet :
- variables temporelles cycliques,
- retards (lags),
- statistiques glissantes,
- interactions météo,
- indicateurs calendaires (jours fériés).
"""
import numpy as np
import yaml
from pathlib import Path
import holidays as pyholidays
from .data_loader import get_data_loader
import argparse
from .utils import load_config

DEFAULT_LAGS = [1, 2, 3, 24, 48, 168]
DEFAULT_ROLLING_WINDOWS = [3, 6, 12, 24]
FUTURE_SAFE_LAGS = [24, 168]
FUTURE_UNSAFE_PREFIXES = (
    'puissance_roll_',
    'puissance_std_',
    'puissance_min_',
    'puissance_max_',
)

# ===================================================
# CONFIGURATION
# ===================================================
config = load_config("config/config.yaml")



# ===================================================
# FONCTIONS DE FEATURE ENGINEERING
# ===================================================
def create_temporal_features(df):
    df = df.copy()
    df['heure'] = df['datetime'].dt.hour
    df['jour_semaine'] = df['datetime'].dt.dayofweek
    df['is_weekend'] = df['jour_semaine'].isin([5,6]).astype(int)

    df['heure_sin'] = np.sin(2*np.pi*df['heure']/24)
    df['heure_cos'] = np.cos(2*np.pi*df['heure']/24)
    df['jour_sin'] = np.sin(2*np.pi*df['jour_semaine']/7)
    df['jour_cos'] = np.cos(2*np.pi*df['jour_semaine']/7)
    return df


def create_lag_features(df, target_col, lags=DEFAULT_LAGS):
    df = df.copy()
    prefix = 'puissance'
    for lag in lags:
        df[f'{prefix}_lag_{lag}'] = df[target_col].shift(lag)
    return df


def create_rolling_features(df, target_col, windows=DEFAULT_ROLLING_WINDOWS):
    df = df.copy()
    prefix = 'puissance'
    for window in windows:
        df[f'{prefix}_roll_{window}'] = df[target_col].shift(1).rolling(window=window).mean()
    return df

# ...existing code...

def create_thermal_features(df):
    """
    Variables thermiques orientées pics hivernaux.
    """
    df = df.copy()

    if 'datetime' not in df.columns or 'temperature' not in df.columns:
        return df

    dt = df['datetime']
    temp = df['temperature']

    df['dju_chauffage'] = (18 - temp).clip(lower=0)
    df['grand_froid'] = (temp <= 0).astype(int)

    df['mois_hivernal'] = dt.dt.month.isin([11, 12, 1, 2, 3]).astype(int)
    df['jour_ouvre'] = (~dt.dt.dayofweek.isin([5, 6])).astype(int)
    df['heure_pointe'] = dt.dt.hour.isin([7, 8, 9, 18, 19]).astype(int)

    df['is_peak_winter_hour'] = (
        (df['mois_hivernal'] == 1) &
        (df['jour_ouvre'] == 1) &
        (df['heure_pointe'] == 1)
    ).astype(int)

    df['dju_peak_winter'] = df['dju_chauffage'] * df['is_peak_winter_hour']

    df['temp_min_24h'] = temp.rolling(24, min_periods=1).min()
    df['temp_min_48h'] = temp.rolling(48, min_periods=1).min()

    df['dju_rolling_24h'] = df['dju_chauffage'].rolling(24, min_periods=1).mean()
    df['dju_rolling_48h'] = df['dju_chauffage'].rolling(48, min_periods=1).mean()

    return df


def create_statistical_features(df, target_col):
    df = df.copy()
    prefix = 'puissance'
    df[f'{prefix}_std_12'] = df[target_col].shift(1).rolling(12).std()
    df[f'{prefix}_std_24'] = df[target_col].shift(1).rolling(24).std()
    df[f'{prefix}_min_24'] = df[target_col].shift(1).rolling(24).min()
    df[f'{prefix}_max_24'] = df[target_col].shift(1).rolling(24).max()
    return df


def create_interaction_features(df):
    df = df.copy()
    if 'temperature' in df.columns and 'heure_sin' in df.columns:
        df['temp_x_heure_sin'] = df['temperature'] * df['heure_sin']
        df['temp_x_heure_cos'] = df['temperature'] * df['heure_cos']
    return df


def create_holiday_features(df):
    df = df.copy()
    years = range(df['datetime'].dt.year.min(), df['datetime'].dt.year.max() + 1)
    fr_holidays = pyholidays.France(years=years)
    df['is_holiday'] = df['datetime'].dt.date.map(lambda d: int(d in fr_holidays))
    print(f"   Jours fériés détectés : {df['is_holiday'].sum()} heures sur {len(df)}")
    return df


def add_logistic_cap_floor(df, config, prm=None, config_path=None):
    df = df.copy()
    logistic_cfg = config.setdefault("logistic_growth", {})
    cap_by_site  = logistic_cfg.setdefault("cap_by_site", {})
    floor_by_site = logistic_cfg.setdefault("floor_by_site", {})

    floor = logistic_cfg.get("floor", max(0,float(df["puissance_moy_heure"].quantile(0.01))))
    logistic_cfg["floor"] = float(floor)

    if prm and prm in cap_by_site:
        cap = cap_by_site[prm]
    else:
        cap = float(df["puissance_moy_heure"].quantile(0.99) * 1.5)
        if prm:
            cap_by_site[prm] = cap

    if prm and prm in floor_by_site:
        floor = floor_by_site[prm]
    else:
        floor = float(df["puissance_moy_heure"].quantile(0.01))
        if prm:
            floor_by_site[prm] = floor

    df["floor"] = floor
    df["cap"]   = cap

    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, "w", encoding="utf-8") as f:
                yaml.safe_dump(config, f, allow_unicode=True, sort_keys=False)
            print(f"💾 Config mise à jour avec floor et cap pour {prm}")
    return df, config


# ===================================================
# PIPELINE
# ===================================================
def feature_engineering_pipeline(prm: str, source="csv", config_path="config/config.yaml"):
    """
    Pipeline complet d'enrichissement pour un site PRM.

    Note pédagogique : cette fonction est centrale car elle transforme
    un dataset "propre" en dataset "modélisable".
    """
    print("="*60)
    print(f"FEATURE ENGINEERING (PRM: {prm})")
    print("="*60)

    loader = get_data_loader(source, config_path)
    df = loader.load_processed_site_data(prm=prm)

    config = load_config(config_path)
    target_col = config.get('target', 'puissance_moy_heure')

    if target_col not in df.columns:
        raise ValueError(f"Colonne cible '{target_col}' manquante.")

    # Création des features
    df = create_temporal_features(df)
    df = create_lag_features(df, target_col)
    df = create_rolling_features(df, target_col)
    df = create_statistical_features(df, target_col)
    df = create_interaction_features(df)
    df = create_thermal_features(df)
    df = create_holiday_features(df)
    df, config = add_logistic_cap_floor(df, config, prm=prm, config_path=config_path)

    # Supprimer les NaN générés
    initial_len = len(df)
    df = df.dropna()
    removed = initial_len - len(df)
    if removed > 0:
        print(f"⚠️ {removed} lignes avec NaN supprimées")

    feature_cols = [c for c in df.columns if c not in ['datetime', target_col]]
    print(f"\n📋 Features créées : {feature_cols}")
    print("="*60)
    print("FEATURE ENGINEERING TERMINÉ")
    print("="*60)

    return df, config


def save_features(df, prm, loader):
    """
    Sauvegarde le DataFrame enrichi avec les features.
     - Utilise le DataLoader pour garantir la cohérence des chemins
     - Permet de centraliser la logique de sauvegarde et de logging
    """
    # Sauvegarde
    output_path = loader.processed_path / f"data_features_{prm}.csv"
    df.to_csv(output_path, index=False)
    print(f"✅ Features sauvegardées : {output_path}")

# ===================================================
# UTILITAIRES DE VISUALISATION
# ===================================================
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Feature engineering des données de consommation")
    parser.add_argument("--prm", type=str, required=True, help="Numéro PRM du site")
    parser.add_argument("--source", type=str, default="csv", help="Source des données : csv ou database")
    parser.add_argument("--config", type=str, default="config/config.yaml", help="Chemin vers le fichier de config")
    args = parser.parse_args()

    prm = args.prm
    source = args.source
    config_path = args.config

    # 🔹 Initialiser le DataLoader
    loader = get_data_loader(source, config_path)

    # 🔹 Charger les données processed pour ce PRM
    try:
        df = loader.load_processed_site_data(prm=prm)
        print(f"✅ Données processed chargées pour {prm} : {len(df)} lignes")
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Les données processed pour PRM {prm} n'existent pas. "
            "Exécutez d'abord le preprocessing."
        )

    # 🔹 Feature engineering
    df_fe, cfg = feature_engineering_pipeline(df=df, prm=prm, config_path=config_path)

    print(f"\n📊 Shape finale après feature engineering : {df_fe.shape}")
    print(f"📊 Colonnes disponibles : {list(df_fe.columns)}")

    # 🔹 Sauvegarder le DataFrame enrichi avec features
    output_path = loader.processed_path / f"data_features_{prm}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_fe.to_csv(output_path, index=False)
    print(f"\n✅ Données avec features sauvegardées : {output_path}")