"""
Exemple d'utilisation du DataLoader pour charger et analyser les données.

Ce script montre comment utiliser le nouveau système de chargement des données
dans vos propres scripts.
"""
import sys
from pathlib import Path

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data_loader import get_data_loader
import pandas as pd


def example_1_list_sites():
    """Exemple 1 : Lister tous les sites disponibles."""
    print("\n" + "=" * 60)
    print("EXEMPLE 1 : Lister les sites disponibles")
    print("=" * 60 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv')

    # Lister les sites
    sites = loader.list_available_sites()

    print(f"Sites trouvés : {len(sites)}")
    for i, prm in enumerate(sites, 1):
        print(f"  {i}. PRM: {prm}")

    return sites


def example_2_load_one_site(prm):
    """Exemple 2 : Charger les données d'un site spécifique."""
    print("\n" + "=" * 60)
    print(f"EXEMPLE 2 : Charger un site spécifique ({prm})")
    print("=" * 60 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv')

    # Charger un site
    df = loader.load_site_data(prm=prm)

    print(f"✅ Données chargées : {len(df)} lignes")
    print(f"\nColonnes disponibles :")
    for col in df.columns:
        print(f"  - {col}")

    print(f"\nAperçu des données :")
    print(df.head())

    print(f"\nStatistiques de consommation :")
    if 'puissance_moy_heure' in df.columns:
        print(f"  Minimum  : {df['puissance_moy_heure'].min():.2f} Wh")
        print(f"  Maximum  : {df['puissance_moy_heure'].max():.2f} Wh")
        print(f"  Moyenne  : {df['puissance_moy_heure'].mean():.2f} Wh")
        print(f"  Médiane  : {df['puissance_moy_heure'].median():.2f} Wh")

    return df


def example_3_load_all_sites():
    """Exemple 3 : Charger tous les sites et comparer."""
    print("\n" + "=" * 60)
    print("EXEMPLE 3 : Charger tous les sites")
    print("=" * 60 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv')

    # Charger tous les sites
    df_all = loader.load_site_data()  # prm=None charge tous

    print(f"✅ Données chargées : {len(df_all)} lignes")

    # Analyser par site
    if 'prm' in df_all.columns:
        print(f"\nAnalyse par site :")
        grouped = df_all.groupby('prm')['puissance_moy_heure'].agg(['count', 'mean', 'std'])
        print(grouped)

    return df_all


def example_4_load_with_dates(prm):
    """Exemple 4 : Charger avec filtre de dates."""
    print("\n" + "=" * 60)
    print(f"EXEMPLE 4 : Charger avec filtre de dates")
    print("=" * 60 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv')

    # Charger avec dates
    df = loader.load_site_data(
        prm=prm,
        start_date='2023-01-01',
        end_date='2023-12-31'
    )

    print(f"✅ Données 2023 chargées : {len(df)} lignes")

    if 'datetime' in df.columns or 'date' in df.columns:
        date_col = 'datetime' if 'datetime' in df.columns else 'date'
        print(f"  Période : {df[date_col].min()} à {df[date_col].max()}")

    return df


def example_5_load_meteo():
    """Exemple 5 : Charger les données météo."""
    print("\n" + "=" * 60)
    print("EXEMPLE 5 : Charger les données météo")
    print("=" * 60 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv')

    try:
        # Charger météo
        df_meteo = loader.load_meteo_data()

        print(f"✅ Données météo chargées : {len(df_meteo)} lignes")
        print(f"\nColonnes météo :")
        for col in df_meteo.columns:
            print(f"  - {col}")

        print(f"\nAperçu :")
        print(df_meteo.head())

        return df_meteo

    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        return None


def example_6_combine_data(prm):
    """Exemple 6 : Combiner données site et météo."""
    print("\n" + "=" * 60)
    print("EXEMPLE 6 : Combiner site et météo")
    print("=" * 60 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv')

    # Charger site
    df_site = loader.load_site_data(prm=prm)

    try:
        # Charger météo
        df_meteo = loader.load_meteo_data()

        # Fusionner
        date_col = 'datetime' if 'datetime' in df_site.columns else 'date'
        df_merged = pd.merge(df_site, df_meteo, on=date_col, how='inner', suffixes=('_site', '_meteo'))

        print(f"✅ Données fusionnées : {len(df_merged)} lignes")
        print(f"✅ Colonnes combinées : {len(df_merged.columns)}")

        print(f"\nAperçu des données fusionnées :")
        print(df_merged.head())

        return df_merged

    except FileNotFoundError as e:
        print(f"⚠️ {e}")
        return df_site


def example_7_custom_analysis(prm):
    """Exemple 7 : Analyse personnalisée."""
    print("\n" + "=" * 60)
    print("EXEMPLE 7 : Analyse personnalisée")
    print("=" * 60 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv')

    # Charger les données
    df = loader.load_site_data(prm=prm)

    # Convertir datetime
    if 'datetime' in df.columns:
        df['datetime'] = pd.to_datetime(df['datetime'])
        df['heure'] = df['datetime'].dt.hour
        df['jour_semaine'] = df['datetime'].dt.dayofweek
        df['mois'] = df['datetime'].dt.month

    # Analyser par heure
    print("📊 Consommation moyenne par heure :")
    hourly = df.groupby('heure')['puissance_moy_heure'].mean().sort_index()
    for h, conso in hourly.items():
        bar = "█" * int(conso / 1000)  # Bar chart simple
        print(f"  {h:02d}h : {conso:6.0f} Wh  {bar}")

    # Analyser par jour de la semaine
    print("\n📊 Consommation moyenne par jour de la semaine :")
    days = ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche']
    daily = df.groupby('jour_semaine')['puissance_moy_heure'].mean()
    for i, conso in daily.items():
        print(f"  {days[i]:10s} : {conso:6.0f} Wh")

    # Analyser par mois
    print("\n📊 Consommation moyenne par mois :")
    monthly = df.groupby('mois')['puissance_moy_heure'].mean().sort_index()
    for m, conso in monthly.items():
        print(f"  Mois {m:02d} : {conso:6.0f} Wh")


def main():
    """Point d'entrée principal."""
    print("\n" + "🚀" * 30)
    print("EXEMPLES D'UTILISATION DU DATALOADER")
    print("🚀" * 30)

    # Exemple 1 : Lister les sites
    sites = example_1_list_sites()

    if not sites:
        print("\n❌ Aucun site trouvé!")
        print("Assurez-vous d'avoir des fichiers dans data/raw/sites/")
        return

    # Utiliser le premier site pour les exemples
    prm = sites[0]

    # Exemple 2 : Charger un site
    df = example_2_load_one_site(prm)

    # Exemple 3 : Charger tous les sites
    df_all = example_3_load_all_sites()

    # Exemple 4 : Charger avec dates
    df_filtered = example_4_load_with_dates(prm)

    # Exemple 5 : Charger météo
    df_meteo = example_5_load_meteo()

    # Exemple 6 : Combiner données
    df_combined = example_6_combine_data(prm)

    # Exemple 7 : Analyse personnalisée
    example_7_custom_analysis(prm)

    print("\n" + "✅" * 30)
    print("TOUS LES EXEMPLES TERMINÉS")
    print("✅" * 30)
    print("\n💡 Vous pouvez maintenant adapter ces exemples pour vos besoins !")


if __name__ == "__main__":
    main()
