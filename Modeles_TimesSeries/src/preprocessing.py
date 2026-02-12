"""
Preprocessing des données brutes de consommation énergétique.
"""
import pandas as pd
import numpy as np
import yaml
from pathlib import Path


def load_config(config_path="config/config.yaml"):
    """Charge la configuration depuis le fichier YAML."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def load_raw_data(filepath_or_df):
    """
    Charge les données brutes depuis un fichier CSV ou utilise un DataFrame existant.

    Args:
        filepath_or_df: Chemin vers le fichier CSV ou DataFrame pandas

    Returns:
        DataFrame pandas avec les données brutes
    """
    if isinstance(filepath_or_df, pd.DataFrame):
        df = filepath_or_df.copy()
        print(f"✅ Données chargées depuis DataFrame : {len(df)} lignes")
    else:
        df = pd.read_csv(filepath_or_df, sep=",", decimal=".")
        print(f"✅ Données chargées depuis {filepath_or_df} : {len(df)} lignes")
    return df


def convert_to_kw(df, column="puissance_moy_heure"):
    """
    Convertit la puissance de Wh en kW.

    Args:
        df: DataFrame
        column: Nom de la colonne à convertir

    Returns:
        DataFrame avec la conversion effectuée
    """
    df = df.copy()
    df[column] = df[column] / 1000
    print(f"✅ Conversion en kW effectuée")
    print(f"   Plage : {df[column].min():.2f} - {df[column].max():.2f} kW")
    print(f"   Moyenne : {df[column].mean():.2f} kW")
    return df


def clean_data(df):
    """
    Nettoie les données (valeurs manquantes, doublons, etc.).

    Args:
        df: DataFrame à nettoyer

    Returns:
        DataFrame nettoyé
    """
    df = df.copy()

    # Convertir datetime
    df['datetime'] = pd.to_datetime(df['datetime'])

    # Trier par date
    df = df.sort_values('datetime').reset_index(drop=True)

    # Supprimer les doublons
    duplicates = df.duplicated(subset=['datetime']).sum()
    if duplicates > 0:
        print(f"⚠️ {duplicates} doublons supprimés")
        df = df.drop_duplicates(subset=['datetime'])

    # Afficher les valeurs manquantes
    missing = df.isnull().sum()
    if missing.sum() > 0:
        print(f"⚠️ Valeurs manquantes détectées :")
        print(missing[missing > 0])

    print(f"✅ Données nettoyées : {len(df)} lignes")
    return df


def save_processed_data(df, output_path):
    """
    Sauvegarde les données prétraitées.

    Args:
        df: DataFrame à sauvegarder
        output_path: Chemin de sortie
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    print(f"✅ Données sauvegardées : {output_path}")


def preprocess_pipeline(input_filepath_or_df, output_filepath=None,
                       config_path="config/config.yaml", from_dataframe=False):
    """
    Pipeline complet de preprocessing.

    Args:
        input_filepath_or_df: Chemin vers les données brutes ou DataFrame
        output_filepath: Chemin de sortie (optionnel)
        config_path: Chemin vers le fichier de configuration
        from_dataframe: Si True, input_filepath_or_df est un DataFrame

    Returns:
        DataFrame prétraité
    """
    print("=" * 60)
    print("PREPROCESSING DES DONNÉES")
    print("=" * 60)

    # Charger la configuration
    config = load_config(config_path)

    # Charger les données
    df = load_raw_data(input_filepath_or_df)

    # Convertir en kW
    target_col = config.get('target', 'puissance_moy_heure')
    df = convert_to_kw(df, column=target_col)

    # Nettoyer
    df = clean_data(df)

    # Sauvegarder si chemin fourni
    if output_filepath:
        save_processed_data(df, output_filepath)

    print("=" * 60)
    print("PREPROCESSING TERMINÉ")
    print("=" * 60)

    return df


if __name__ == "__main__":
    # Exemple d'utilisation
    input_file = "dataFE_prm_30000250086126.csv"
    output_file = "data/processed/data_preprocessed.csv"

    df_processed = preprocess_pipeline(input_file, output_file)
    print(f"\n📊 Shape finale : {df_processed.shape}")
    print(f"📊 Colonnes : {list(df_processed.columns)}")
