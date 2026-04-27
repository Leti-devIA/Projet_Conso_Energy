"""
Script de test manuel (legacy / exploration).

Note pédagogique : les tests officiels du projet sont dans `tests/`.
Ce fichier peut servir pour du debug rapide en local.
"""
from preprocessing import preprocess_pipeline
from feature_engineering import feature_engineering_pipeline

df_pre = preprocess_pipeline(
    "data/processed/data_preprocessed_30000250086126.csv",
    from_dataframe=False
)
df_feat = feature_engineering_pipeline(df_pre, config_path="config/config.yaml")

print("=== TARGET AVANT PROPHET ===")
print(df_feat["puissance_moy_heure"].describe())
print(f"\nMax absolu : {df_feat['puissance_moy_heure'].max()}")
print(f"Min absolu : {df_feat['puissance_moy_heure'].min()}")