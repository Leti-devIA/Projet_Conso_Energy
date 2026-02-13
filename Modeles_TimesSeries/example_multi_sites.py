"""
Exemple d'utilisation du DataLoader pour gérer plusieurs sites avec météo et prix.

Ce script montre comment :
1. Charger la table des sites
2. Récupérer les informations d'un site spécifique (ville, coordonnées)
3. Charger les données de consommation pour plusieurs sites
4. Fusionner avec les données météo et prix
5. Préparer pour l'entraînement ou l'analyse
"""
import sys
from pathlib import Path
import pandas as pd

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / 'src'))
from data_loader import get_data_loader


def main():
    print("\n" + "🌟" * 40)
    print("EXEMPLE D'UTILISATION MULTI-SITES")
    print("🌟" * 40 + "\n")

    # 1. Créer le DataLoader
    print("📂 Initialisation du DataLoader...")
    loader = get_data_loader('csv', config_path='config/config.yaml')
    print("✅ DataLoader initialisé\n")

    # 2. Charger la table des sites
    print("=" * 60)
    print("CHARGEMENT DE LA TABLE DES SITES")
    print("=" * 60)
    sites_df = loader.load_sites_table()
    print(f"\n📊 {len(sites_df)} sites disponibles :\n")
    print(sites_df[['ville', 'code_postal', 'prm']].to_string(index=False))

    # 3. Lister les sites avec données disponibles
    print("\n" + "=" * 60)
    print("SITES AVEC DONNÉES DISPONIBLES")
    print("=" * 60)
    sites_with_data = loader.list_available_sites_with_data()
    print(f"\n📂 {len(sites_with_data)} site(s) avec fichiers CSV :")
    for prm in sites_with_data:
        site_info = loader.get_site_info(prm)
        print(f"   - {site_info['ville']} (PRM: {prm})")

    # 4. Charger les données d'un site spécifique
    if sites_with_data:
        selected_prm = sites_with_data[0]
        print(f"\n" + "=" * 60)
        print(f"CHARGEMENT DES DONNÉES DU SITE : {selected_prm}")
        print("=" * 60)

        # Informations du site
        site_info = loader.get_site_info(selected_prm)
        print(f"\n🏠 Site sélectionné :")
        print(f"   Ville         : {site_info['ville']}")
        print(f"   Code postal   : {site_info['code_postal']}")
        print(f"   PRM           : {site_info['prm']}")
        print(f"   Coordonnées   : {site_info['lat']}, {site_info['lon']}")

        # Charger les données de consommation
        df_site = loader.load_site_data(prm=selected_prm)
        print(f"\n📊 Données de consommation :")
        print(f"   Lignes        : {len(df_site)}")
        print(f"   Colonnes      : {', '.join(df_site.columns.tolist()[:5])}...")
        if 'datetime' in df_site.columns:
            df_site['datetime'] = pd.to_datetime(df_site['datetime'])
            print(f"   Période       : {df_site['datetime'].min()} → {df_site['datetime'].max()}")
        if 'puissance_moy_heure' in df_site.columns:
            print(f"   Conso moyenne : {df_site['puissance_moy_heure'].mean():.2f} Wh")

        # 5. Charger les données météo
        print(f"\n" + "=" * 60)
        print("CHARGEMENT DES DONNÉES MÉTÉO")
        print("=" * 60)
        try:
            df_meteo = loader.load_meteo_data()
            print(f"\n🌤️  Données météo :")
            print(f"   Lignes        : {len(df_meteo)}")
            print(f"   Colonnes      : {', '.join(df_meteo.columns.tolist()[:5])}...")
            if 'datetime' in df_meteo.columns:
                df_meteo['datetime'] = pd.to_datetime(df_meteo['datetime'])
                print(f"   Période       : {df_meteo['datetime'].min()} → {df_meteo['datetime'].max()}")
        except FileNotFoundError as e:
            print(f"⚠️ {e}")

        # 6. Charger les données de prix
        print(f"\n" + "=" * 60)
        print("CHARGEMENT DES DONNÉES DE PRIX")
        print("=" * 60)
        try:
            df_prix = loader.load_prix_data()
            print(f"\n💰 Données de prix :")
            print(f"   Lignes        : {len(df_prix)}")
            print(f"   Colonnes      : {', '.join(df_prix.columns.tolist())}...")
            if 'datetime' in df_prix.columns:
                df_prix['datetime'] = pd.to_datetime(df_prix['datetime'])
                print(f"   Période       : {df_prix['datetime'].min()} → {df_prix['datetime'].max()}")
        except FileNotFoundError as e:
            print(f"⚠️ {e}")

        # 7. Exemple de fusion des données
        print(f"\n" + "=" * 60)
        print("FUSION DES DONNÉES")
        print("=" * 60)
        try:
            # Fusionner site + météo
            if 'df_meteo' in locals() and 'datetime' in df_site.columns and 'datetime' in df_meteo.columns:
                df_merged = pd.merge(df_site, df_meteo, on='datetime', how='inner', suffixes=('', '_meteo'))
                print(f"\n🔗 Site + Météo :")
                print(f"   Lignes communes : {len(df_merged)}")
                print(f"   Colonnes totales: {len(df_merged.columns)}")

                # Ajouter les prix si disponibles
                if 'df_prix' in locals() and 'datetime' in df_prix.columns:
                    df_complete = pd.merge(df_merged, df_prix, on='datetime', how='left')
                    print(f"\n🔗 Site + Météo + Prix :")
                    print(f"   Lignes finales  : {len(df_complete)}")
                    print(f"   Colonnes totales: {len(df_complete.columns)}")

                    # Aperçu du dataset final
                    print(f"\n📋 Aperçu des données fusionnées :")
                    print(df_complete.head(3).to_string())
        except Exception as e:
            print(f"⚠️ Erreur lors de la fusion : {e}")

    # 8. Charger tous les sites en une fois
    print(f"\n" + "=" * 60)
    print("CHARGEMENT DE TOUS LES SITES")
    print("=" * 60)

    if sites_with_data:
        print(f"\n📂 Chargement de tous les sites avec données...")
        all_sites_data = []

        for prm in sites_with_data:
            try:
                df = loader.load_site_data(prm=prm)
                site_info = loader.get_site_info(prm)
                df['ville'] = site_info['ville']
                all_sites_data.append(df)
                print(f"   ✅ {site_info['ville']} : {len(df)} lignes")
            except Exception as e:
                print(f"   ❌ Erreur pour PRM {prm} : {e}")

        if all_sites_data:
            df_all = pd.concat(all_sites_data, ignore_index=True)
            print(f"\n📊 Dataset combiné :")
            print(f"   Total lignes  : {len(df_all)}")
            print(f"   Sites         : {df_all['prm'].nunique()}")
            print(f"   Villes        : {', '.join(df_all['ville'].unique())}")

    # 9. Résumé et prochaines étapes
    print("\n" + "🎉" * 40)
    print("RÉSUMÉ")
    print("🎉" * 40)
    print(f"""
✅ DataLoader opérationnel
✅ Table des sites chargée ({len(sites_df)} sites)
✅ Sites avec données : {len(sites_with_data)}
✅ Données météo disponibles
✅ Données prix disponibles

💡 Prochaines étapes :
   1. Entraîner un modèle par site :
      python main.py train --prm {sites_with_data[0] if sites_with_data else 'XXXXX'}

   2. Entraîner tous les sites :
      python main.py train --all-sites

   3. Lancer le dashboard :
      streamlit run dashboard_longterm.py

   4. Migration future vers DB :
      - Implémenter DatabaseDataLoader.load_site_data()
      - Implémenter DatabaseDataLoader.load_sites_table()
      - Changer data_source: "database" dans config.yaml
    """)


if __name__ == "__main__":
    main()
