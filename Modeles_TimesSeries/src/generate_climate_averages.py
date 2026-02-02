"""
Génère des données météo moyennes basées sur l'historique pour prédictions long terme.
"""
import pandas as pd
import numpy as np
import yaml
from pathlib import Path


def load_config(config_path="config/config.yaml"):
    """Charge la configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def calculate_climate_averages(historique_df):
    """
    Calcule les moyennes climatiques par mois et heure depuis l'historique.
    
    Args:
        historique_df: DataFrame avec colonnes datetime, temperature, humidite, 
                      vitesse_vent, couverture_nuages
    
    Returns:
        DataFrame avec moyennes par (mois, heure)
    """
    df = historique_df.copy()
    
    # Convertir datetime
    df['datetime'] = pd.to_datetime(df['datetime'])
    
    # Extraire mois et heure
    df['mois'] = df['datetime'].dt.month
    df['heure'] = df['datetime'].dt.hour
    
    # Calculer les moyennes
    colonnes_meteo = ['temperature', 'humidite', 'vitesse_vent', 'couverture_nuages']
    colonnes_disponibles = [col for col in colonnes_meteo if col in df.columns]
    
    meteo_moyenne = df.groupby(['mois', 'heure'])[colonnes_disponibles].agg(['mean', 'std']).reset_index()
    
    # Aplatir les colonnes multi-niveaux
    meteo_moyenne.columns = ['_'.join(col).strip('_') for col in meteo_moyenne.columns.values]
    
    print(f"✅ Moyennes climatiques calculées pour {len(colonnes_disponibles)} variables météo")
    print(f"📊 Période d'historique : {df['datetime'].min()} → {df['datetime'].max()}")
    print(f"📊 Nombre de données : {len(df):,} heures")
    
    return meteo_moyenne


def generate_future_meteo(start_date, nb_heures, meteo_moyenne, add_variability=True):
    """
    Génère des données météo futures basées sur les moyennes climatiques.
    
    Args:
        start_date: Date de début des prédictions
        nb_heures: Nombre d'heures à générer
        meteo_moyenne: DataFrame des moyennes climatiques
        add_variability: Si True, ajoute une variabilité aléatoire
        
    Returns:
        DataFrame avec données météo futures
    """
    # Créer les dates futures
    dates = pd.date_range(start=start_date, periods=nb_heures, freq='H')
    
    # Créer le DataFrame
    meteo_future = pd.DataFrame({
        'datetime': dates,
        'mois': dates.month,
        'heure': dates.hour
    })
    
    # Fusionner avec les moyennes
    meteo_future = meteo_future.merge(
        meteo_moyenne,
        on=['mois', 'heure'],
        how='left'
    )
    
    # Colonnes de base
    colonnes_base = ['temperature', 'humidite', 'vitesse_vent', 'couverture_nuages']
    
    # Remplir les valeurs avec moyennes + variabilité optionnelle
    for col in colonnes_base:
        col_mean = f"{col}_mean"
        col_std = f"{col}_std"
        
        if col_mean in meteo_future.columns:
            if add_variability and col_std in meteo_future.columns:
                # Ajouter du bruit gaussien basé sur l'écart-type historique
                noise = np.random.normal(0, meteo_future[col_std] * 0.3, len(meteo_future))
                meteo_future[col] = meteo_future[col_mean] + noise
            else:
                # Utiliser simplement la moyenne
                meteo_future[col] = meteo_future[col_mean]
            
            # S'assurer que les valeurs restent dans des plages réalistes
            if col == 'temperature':
                meteo_future[col] = np.clip(meteo_future[col], -30, 50)
            elif col == 'humidite':
                meteo_future[col] = np.clip(meteo_future[col], 0, 100)
            elif col == 'vitesse_vent':
                meteo_future[col] = np.clip(meteo_future[col], 0, 100)
            elif col == 'couverture_nuages':
                meteo_future[col] = np.clip(meteo_future[col], 0, 100)
    
    # Garder uniquement les colonnes nécessaires
    colonnes_finales = ['datetime'] + [col for col in colonnes_base if col in meteo_future.columns]
    meteo_future = meteo_future[colonnes_finales]
    
    print(f"✅ {nb_heures:,} heures de données météo générées")
    print(f"📅 Période : {meteo_future['datetime'].min()} → {meteo_future['datetime'].max()}")
    
    return meteo_future


def add_jours_feries(meteo_future_df, jours_feries_list=None):
    """
    Ajoute la colonne jour_ferie au DataFrame.
    
    Args:
        meteo_future_df: DataFrame avec colonne datetime
        jours_feries_list: Liste de dates (format 'YYYY-MM-DD') des jours fériés
                          Si None, utilise une liste par défaut pour la France
        
    Returns:
        DataFrame avec colonne jour_ferie ajoutée
    """
    df = meteo_future_df.copy()
    
    # Jours fériés fixes en France (à adapter selon le pays)
    if jours_feries_list is None:
        # Extraire les années couvertes
        annees = df['datetime'].dt.year.unique()
        jours_feries_list = []
        
        for annee in annees:
            jours_feries_list.extend([
                f"{annee}-01-01",  # Nouvel An
                f"{annee}-05-01",  # Fête du Travail
                f"{annee}-05-08",  # Victoire 1945
                f"{annee}-07-14",  # Fête Nationale
                f"{annee}-08-15",  # Assomption
                f"{annee}-11-01",  # Toussaint
                f"{annee}-11-11",  # Armistice 1918
                f"{annee}-12-25",  # Noël
            ])
    
    # Convertir en dates
    jours_feries = pd.to_datetime(jours_feries_list)
    
    # Ajouter la colonne
    df['jour_ferie'] = df['datetime'].dt.date.isin(jours_feries.date).astype(int)
    
    nb_feries = df['jour_ferie'].sum()
    print(f"✅ Jours fériés ajoutés : {nb_feries} jours sur {len(df)//24} jours")
    
    return df


def generate_climate_averages_pipeline(historique_path, output_path=None, 
                                       start_date=None, nb_annees=3,
                                       add_variability=True, config_path="config/config.yaml"):
    """
    Pipeline complet pour générer des données météo moyennes pour prédictions long terme.
    
    Args:
        historique_path: Chemin vers les données historiques
        output_path: Chemin de sortie (optionnel)
        start_date: Date de début (si None, utilise la dernière date de l'historique + 1h)
        nb_annees: Nombre d'années à générer
        add_variability: Ajouter de la variabilité aléatoire
        config_path: Chemin vers la configuration
        
    Returns:
        DataFrame avec données météo moyennes
    """
    print("=" * 80)
    print("GÉNÉRATION DE DONNÉES MÉTÉO MOYENNES POUR PRÉDICTIONS LONG TERME")
    print("=" * 80)
    
    # Charger l'historique
    print(f"\n📂 Chargement de l'historique : {historique_path}")
    historique = pd.read_csv(historique_path)
    historique['datetime'] = pd.to_datetime(historique['datetime'])
    
    # Calculer les moyennes climatiques
    print(f"\n🔄 Calcul des moyennes climatiques...")
    meteo_moyenne = calculate_climate_averages(historique)
    
    # Déterminer la date de début
    if start_date is None:
        start_date = historique['datetime'].max() + pd.Timedelta(hours=1)
        print(f"\n📅 Date de début automatique : {start_date}")
    else:
        start_date = pd.to_datetime(start_date)
        print(f"\n📅 Date de début fournie : {start_date}")
    
    # Générer les données futures
    nb_heures = nb_annees * 365 * 24
    print(f"\n🔮 Génération de {nb_heures:,} heures ({nb_annees} ans)...")
    meteo_future = generate_future_meteo(start_date, nb_heures, meteo_moyenne, add_variability)
    
    # Ajouter les jours fériés
    print(f"\n📅 Ajout des jours fériés...")
    meteo_future = add_jours_feries(meteo_future)
    
    # Sauvegarder
    if output_path is None:
        config = load_config(config_path)
        output_dir = Path(config['data']['raw'])
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"meteo_moyennes_{nb_annees}ans.csv"
    
    meteo_future.to_csv(output_path, index=False)
    print(f"\n✅ Données sauvegardées : {output_path}")
    
    # Statistiques
    print("\n" + "=" * 80)
    print("📊 STATISTIQUES DES DONNÉES GÉNÉRÉES")
    print("=" * 80)
    print(f"Période           : {meteo_future['datetime'].min()} → {meteo_future['datetime'].max()}")
    print(f"Nombre d'heures   : {len(meteo_future):,}")
    print(f"Nombre de jours   : {len(meteo_future)//24:,}")
    print(f"Colonnes générées : {list(meteo_future.columns)}")
    
    if 'temperature' in meteo_future.columns:
        print(f"\nTempérature :")
        print(f"  Min     : {meteo_future['temperature'].min():.1f}°C")
        print(f"  Max     : {meteo_future['temperature'].max():.1f}°C")
        print(f"  Moyenne : {meteo_future['temperature'].mean():.1f}°C")
    
    if 'humidite' in meteo_future.columns:
        print(f"\nHumidité :")
        print(f"  Min     : {meteo_future['humidite'].min():.1f}%")
        print(f"  Max     : {meteo_future['humidite'].max():.1f}%")
        print(f"  Moyenne : {meteo_future['humidite'].mean():.1f}%")
    
    print("\n⚠️  ATTENTION : Ces données sont basées sur des moyennes historiques.")
    print("    Les prédictions seront MOINS PRÉCISES que avec de vraies prévisions météo.")
    print("=" * 80)
    
    return meteo_future


if __name__ == "__main__":
    # Exemple d'utilisation
    historique_path = "dataFE_prm_30000250086126.csv"
    output_path = "data/raw/meteo_moyennes_3ans.csv"
    
    # Générer 3 ans de données météo moyennes
    meteo_3ans = generate_climate_averages_pipeline(
        historique_path=historique_path,
        output_path=output_path,
        nb_annees=3,
        add_variability=True  # Ajoute une variabilité réaliste
    )
    
    print(f"\n✅ Fichier prêt pour les prédictions long terme !")
    print(f"📁 Utilise ce fichier avec predict_longterm.py")
