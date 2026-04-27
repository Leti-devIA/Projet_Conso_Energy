"""
Étape 1 du pipeline ML : preprocessing.

Objectif pédagogique :
- transformer les données brutes en données propres et cohérentes,
- garantir un pas horaire régulier,
- préparer les colonnes nécessaires au feature engineering.
"""
import pandas as pd
import holidays
from .utils import load_config
from .data_loader import get_data_loader

# ===================================================
# CONFIGURATION
# ===================================================
config = load_config("config/config.yaml")



# ===================================================
# FONCTIONS DE PREPROCESSING
# ===================================================
def aggregate_by_hour(df):
    """
    Agrège les données de puissance par heure.
    Appelée uniquement sur des données brutes (colonne 'puissance' en Watts).
    """
    df = df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['date']  = pd.to_datetime(df['datetime'].dt.date)
    df['heure'] = df['datetime'].dt.hour

    group_cols = ['date', 'heure']
    if 'prm' in df.columns:
        group_cols = ['prm'] + group_cols

    meteo_cols = ['temperature', 'humidite', 'precipitation', 'vitesse_vent', 'direction_vent', 'couverture_nuages']
    available_meteo = [c for c in meteo_cols if c in df.columns]

    agg_dict = {'puissance': ['mean', 'sum']}
    for col in available_meteo:
        agg_dict[col] = 'mean'

    df_agg = df.groupby(group_cols).agg(agg_dict).reset_index()
    df_agg.columns = [
        '_'.join(col).strip('_') if col[1] else col[0]
        for col in df_agg.columns.values
    ]

    df_agg = df_agg.rename(columns={
        'puissance_mean': 'puissance_moy_heure',
        'puissance_sum':  'puissance_sum_heure'
    })
    meteo_rename = {f'{c}_mean': c for c in available_meteo}
    df_agg = df_agg.rename(columns=meteo_rename)

    df_agg['datetime'] = pd.to_datetime(df_agg['date']) + pd.to_timedelta(df_agg['heure'], unit='h')
    df_agg = df_agg.sort_values('datetime').reset_index(drop=True)
    df_agg = df_agg.drop(columns=['date', 'heure'])
    df_agg = df_agg.drop_duplicates(subset=['datetime'])

    print(f"✅ Agrégation horaire : {len(df_agg)} lignes")
    print(f"   Plage   : {df_agg['puissance_moy_heure'].min():.2f} - {df_agg['puissance_moy_heure'].max():.2f} W")
    print(f"   Moyenne : {df_agg['puissance_moy_heure'].mean():.2f} W")
    if available_meteo:
        print(f"   Météo préservée : {', '.join(available_meteo)}")

    return df_agg


def add_jour_ferie(df):
    df = df.copy()

    if 'jour_ferie' not in df.columns:
        jours_feries_fr = holidays.France()
        df['jour_ferie'] = df['datetime'].dt.normalize().map(
            lambda d: int(d.date() in jours_feries_fr)
        )
        print(f"✅ Colonne 'jour_ferie' ajoutée ({df['jour_ferie'].sum()} jours fériés)")

    return df


def clean_data(df):
    """Nettoie les données (tri, doublons, jours fériés, contrôle des NaN)."""
    df = df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df = df.sort_values('datetime').reset_index(drop=True)

    duplicates = df.duplicated(subset=['datetime']).sum()
    if duplicates > 0:
        print(f"⚠️  {duplicates} doublons supprimés")
        df = df.drop_duplicates(subset=['datetime'])

    df = add_jour_ferie(df)

    missing = df.isnull().sum()
    if missing.sum() > 0:
        print("⚠️  Valeurs manquantes :")
        print(missing[missing > 0])

    print(f"✅ Données nettoyées : {len(df)} lignes")
    return df


# ===================================================
# PIPELINE DE PREPROCESSING
# ===================================================
def preprocess_pipeline(prm: str, source="csv", config_path="config/config.yaml"):
    print("=" * 60)
    print(f"PREPROCESSING DES DONNÉES (PRM: {prm})")
    print("=" * 60)

    loader = get_data_loader(source, config_path)

    # 1️⃣ Charger données consommation
    df = loader.load_dataclean(prm=prm)
    print(f"\n📊 Colonnes initiales : {list(df.columns)}")

    # 2️⃣ Agrégation si nécessaire
    if "puissance" in df.columns and "puissance_moy_heure" not in df.columns:
        print("\n🔄 Agrégation par heure...")
        df = aggregate_by_hour(df)

    # 4️⃣ Nettoyage
    df = clean_data(df)

    # 5️⃣ Sauvegarde propre via loader
    loader.save_processed_site_data(df, prm)

    print("=" * 60)
    print("PREPROCESSING TERMINÉ")
    print("=" * 60)

    return df


# ===================================================
# UTILITAIRES DE VISUALISATION
# ===================================================
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Preprocessing des données")
    parser.add_argument("--prm", type=str, required=True)
    parser.add_argument("--source", type=str, default="csv")
    args = parser.parse_args()

    df_processed = preprocess_pipeline(
        prm=args.prm,
        source=args.source
    )

    print(f"\n📊 Shape : {df_processed.shape}")
    print(f"📊 Colonnes : {list(df_processed.columns)}")