"""
Script pour générer les prévisions météo climatiques pour un ou plusieurs sites.

Usage:
    # Pour un site spécifique
    python generate_meteo_all.py --prm 30000250086126

    # Pour tous les sites
    python generate_meteo_all.py --all-sites

    # Avec options
    python generate_meteo_all.py --all-sites --nb-annees 5 --no-variability
"""
import sys
from pathlib import Path
import argparse

# Ajouter src au path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data_loader import get_data_loader
from generate_climate_averages import generate_climate_averages_pipeline


def generate_meteo_for_site(prm, nb_annees=3, add_variability=True, config_path='config/config.yaml'):
    """
    Génère les prévisions météo pour un site spécifique.

    Args:
        prm: Code PRM du site
        nb_annees: Nombre d'années à générer
        add_variability: Ajouter de la variabilité
        config_path: Chemin vers la configuration
    """
    print("\n" + "=" * 80)
    print(f"🌤️  Génération météo pour le site {prm}")
    print("=" * 80)

    try:
        # Charger les infos du site
        loader = get_data_loader('csv', config_path)
        site_info = loader.get_site_info(prm)

        print(f"📍 Site : {site_info.get('ville', 'Inconnu')} (PRM: {prm})")

        # Générer les prévisions
        meteo_df = generate_climate_averages_pipeline(
            prm=prm,
            nb_annees=nb_annees,
            add_variability=add_variability,
            config_path=config_path
        )

        print(f"✅ Prévisions générées pour {site_info.get('ville', prm)}")
        return True

    except Exception as e:
        print(f"❌ Erreur pour le site {prm} : {e}")
        return False


def generate_meteo_all_sites(nb_annees=3, add_variability=True, config_path='config/config.yaml'):
    """
    Génère les prévisions météo pour tous les sites disponibles.

    Args:
        nb_annees: Nombre d'années à générer
        add_variability: Ajouter de la variabilité
        config_path: Chemin vers la configuration
    """
    print("\n" + "🌟" * 40)
    print("GÉNÉRATION MÉTÉO POUR TOUS LES SITES")
    print("🌟" * 40 + "\n")

    # Charger la liste des sites
    loader = get_data_loader('csv', config_path)
    sites_df = loader.load_sites_table()

    if sites_df.empty:
        print("❌ Aucun site trouvé dans la table des sites")
        return

    # Lister les sites avec fichiers de données
    sites_with_data = loader.list_available_sites_with_data()

    if not sites_with_data:
        print("❌ Aucun fichier de données trouvé dans data/raw/sites/")
        return

    print(f"📊 {len(sites_with_data)} site(s) détecté(s) avec données\n")

    # Afficher la liste
    for prm in sites_with_data:
        site_info = loader.get_site_info(prm)
        print(f"   • {site_info.get('ville', 'Inconnu'):20s} (PRM: {prm})")

    print("\n" + "-" * 80 + "\n")

    # Générer pour chaque site
    success_count = 0
    failed_count = 0

    for i, prm in enumerate(sites_with_data, 1):
        site_info = loader.get_site_info(prm)
        print(f"\n[{i}/{len(sites_with_data)}] Traitement de {site_info.get('ville', prm)}...")

        if generate_meteo_for_site(prm, nb_annees, add_variability, config_path):
            success_count += 1
        else:
            failed_count += 1

    # Résumé
    print("\n" + "=" * 80)
    print("📊 RÉSUMÉ DE LA GÉNÉRATION")
    print("=" * 80)
    print(f"✅ Réussis : {success_count}/{len(sites_with_data)}")
    if failed_count > 0:
        print(f"❌ Échoués : {failed_count}/{len(sites_with_data)}")
    print(f"\n📁 Fichiers générés dans : data/raw/meteo/")
    print(f"   Format : meteo_moyennes_3ans_<PRM>.csv")

    if success_count > 0:
        print("\n💡 Prochaines étapes :")
        print("   1. Vérifier les fichiers générés")
        print("   2. Entraîner les modèles : python main.py train --all-sites")
        print("   3. Faire des prédictions long terme")


def main():
    parser = argparse.ArgumentParser(
        description="Génération de prévisions météo climatiques pour les sites"
    )

    # Options de sélection de sites
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--prm', type=str, help='Code PRM du site à traiter')
    group.add_argument('--all-sites', action='store_true', help='Traiter tous les sites')

    # Options de génération
    parser.add_argument('--nb-annees', type=int, default=3,
                       help='Nombre d\'années à générer (défaut: 3)')
    parser.add_argument('--no-variability', action='store_true',
                       help='Désactiver la variabilité météo')
    parser.add_argument('--config', type=str, default='config/config.yaml',
                       help='Chemin vers le fichier de configuration')

    args = parser.parse_args()

    # Exécuter
    add_variability = not args.no_variability

    if args.all_sites:
        generate_meteo_all_sites(
            nb_annees=args.nb_annees,
            add_variability=add_variability,
            config_path=args.config
        )
    else:
        generate_meteo_for_site(
            prm=args.prm,
            nb_annees=args.nb_annees,
            add_variability=add_variability,
            config_path=args.config
        )


if __name__ == "__main__":
    main()
