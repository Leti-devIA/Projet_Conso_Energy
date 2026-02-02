"""
Feature Engineering pour les séries temporelles de consommation énergétique.
"""
import pandas as pd
import numpy as np
import yaml


def load_config(config_path="config/config.yaml"):
    """Charge la configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def create_temporal_features(df):
    """
    Crée les features temporelles cycliques.
    
    Args:
        df: DataFrame avec une colonne 'datetime'
        
    Returns:
        DataFrame avec features temporelles ajoutées
    """
    df = df.copy()
    
    # Extraire composantes temporelles
    df['heure'] = df['datetime'].dt.hour
    df['jour_semaine'] = df['datetime'].dt.dayofweek
    
    # Features cycliques pour l'heure (cycle 24h)
    df['heure_sin'] = np.sin(2 * np.pi * df['heure'] / 24)
    df['heure_cos'] = np.cos(2 * np.pi * df['heure'] / 24)
    
    # Features cycliques pour le jour de la semaine (cycle 7j)
    df['jour_sin'] = np.sin(2 * np.pi * df['jour_semaine'] / 7)
    df['jour_cos'] = np.cos(2 * np.pi * df['jour_semaine'] / 7)
    
    return df


def create_lag_features(df, target_col, lags=[1, 2, 3, 24, 48]):
    """
    Crée les features de lag (valeurs historiques).
    
    Args:
        df: DataFrame
        target_col: Colonne cible pour les lags
        lags: Liste des décalages temporels
        
    Returns:
        DataFrame avec features de lag
    """
    df = df.copy()
    
    # 🔧 FIX : Utiliser 'puissance' comme préfixe au lieu du nom complet
    prefix = 'puissance'
    
    for lag in lags:
        df[f'{prefix}_lag_{lag}'] = df[target_col].shift(lag)
    
    return df


def create_rolling_features(df, target_col, windows=[3, 6, 12, 24]):
    """
    Crée les moyennes mobiles (rolling means).
    
    Args:
        df: DataFrame
        target_col: Colonne cible
        windows: Fenêtres pour les moyennes mobiles
        
    Returns:
        DataFrame avec moyennes mobiles
    """
    df = df.copy()
    
    # 🔧 FIX : Utiliser 'puissance' comme préfixe
    prefix = 'puissance'
    
    for window in windows:
        df[f'{prefix}_roll_{window}'] = df[target_col].shift(1).rolling(window=window).mean()
    
    return df


def create_statistical_features(df, target_col):
    """
    Crée les features statistiques (std, min, max).
    
    Args:
        df: DataFrame
        target_col: Colonne cible
        
    Returns:
        DataFrame avec features statistiques
    """
    df = df.copy()
    
    # 🔧 FIX : Utiliser 'puissance' comme préfixe
    prefix = 'puissance'
    
    # Écart-types roulants
    df[f'{prefix}_std_12'] = df[target_col].shift(1).rolling(window=12).std()
    df[f'{prefix}_std_24'] = df[target_col].shift(1).rolling(window=24).std()
    
    # Min/Max roulants
    df[f'{prefix}_min_24'] = df[target_col].shift(1).rolling(window=24).min()
    df[f'{prefix}_max_24'] = df[target_col].shift(1).rolling(window=24).max()
    
    return df


def create_interaction_features(df):
    """
    Crée les features d'interaction (température x heure).
    
    Args:
        df: DataFrame
        
    Returns:
        DataFrame avec interactions
    """
    df = df.copy()
    
    if 'temperature' in df.columns and 'heure_sin' in df.columns:
        df['temp_x_heure_sin'] = df['temperature'] * df['heure_sin']
        df['temp_x_heure_cos'] = df['temperature'] * df['heure_cos']
    
    return df


def feature_engineering_pipeline(df, config_path="config/config.yaml"):
    """
    Pipeline complet de feature engineering.
    
    Args:
        df: DataFrame avec données prétraitées
        config_path: Chemin vers la configuration
        
    Returns:
        DataFrame avec toutes les features
    """
    print("=" * 60)
    print("FEATURE ENGINEERING")
    print("=" * 60)
    
    # Charger la configuration
    config = load_config(config_path)
    target_col = config.get('target', 'puissance_moy_heure')
    
    # Créer les features
    df = create_temporal_features(df)
    df = create_lag_features(df, target_col)
    df = create_rolling_features(df, target_col)
    df = create_statistical_features(df, target_col)
    df = create_interaction_features(df)
    
    # Supprimer les NaN créés par les lags et rolling
    initial_len = len(df)
    df = df.dropna()
    removed = initial_len - len(df)
    print(f"⚠️ {removed} lignes avec NaN supprimées")
    
    print(f"✅ Nombre total de features : {len(df.columns) - 1}")  # -1 pour datetime
    
    # 🔧 FIX : Afficher les noms des features créées
    feature_cols = [col for col in df.columns if col not in ['datetime', target_col]]
    print(f"\n📋 Features créées :")
    for i, feat in enumerate(feature_cols, 1):
        print(f"   {i:2d}. {feat}")
    
    print("=" * 60)
    print("FEATURE ENGINEERING TERMINÉ")
    print("=" * 60)
    
    return df


def get_feature_list(config_path="config/config.yaml", optimized=False):
    """
    Récupère la liste des features depuis la configuration.
    
    Args:
        config_path: Chemin vers la configuration
        optimized: Si True, retourne les features optimisées (14), sinon toutes
        
    Returns:
        Liste des noms de features
    """
    config = load_config(config_path)
    
    if optimized:
        return config.get('features_optimized', [])
    
    # Rassembler toutes les features
    features = []
    feature_groups = config.get('features', {})
    for group in ['meteo', 'temporelles', 'lags', 'rolling', 'statistiques', 'interactions']:
        features.extend(feature_groups.get(group, []))
    
    return features


if __name__ == "__main__":
    # Exemple d'utilisation
    from preprocessing import load_raw_data, convert_to_kw, clean_data
    
    # Charger et préparer les données
    df = load_raw_data("dataFE_prm_30000250086126.csv")
    df = convert_to_kw(df)
    df = clean_data(df)
    
    # Feature engineering
    df_fe = feature_engineering_pipeline(df)
    
    # Afficher résultat
    print(f"\n📊 Shape finale : {df_fe.shape}")
    print(f"📊 Features disponibles : {list(df_fe.columns)}")
    
    # Sauvegarder
    output_path = "data/processed/data_with_features.csv"
    df_fe.to_csv(output_path, index=False)
    print(f"\n✅ Données sauvegardées : {output_path}")
