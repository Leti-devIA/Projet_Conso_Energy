"""
Point d'entrée principal pour entraîner ou prédire avec le modèle Prophet.

Usage:
    # Entraîner avec un site spécifique
    python main.py train --prm 30000250086126

    # Entraîner avec tous les sites disponibles
    python main.py train --all-sites

    # Lister les sites disponibles
    python main.py list-sites

    # Prédiction long terme
    python main.py predict-longterm --prm 30000250086126 --years 3

    # Générer toutes les prédictions
    python generate_all_predictions.py
"""
import argparse
import sys
import pickle
import json
from pathlib import Path
from datetime import datetime

# Ajouter le répertoire src au path si nécessaire
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from data_loader import get_data_loader
from train import train_one_site
from predict import predict_future, load_prophet_model
from utils import load_config, detect_prms
from generate_climate_averages import generate_climate_averages_pipeline
import pandas as pd


def list_sites(config_path='config/config.yaml'):
    """
    Liste tous les sites disponibles.

    Args:
        config_path: Chemin vers le fichier de configuration
    """
    print("\n" + "📋" * 30)
    print("SITES DISPONIBLES")
    print("📋" * 30 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv', config_path)
    sites = loader.list_available_sites()

    if not sites:
        print("❌ Aucun site trouvé dans data/raw/sites/")
        print("\nAssurez-vous d'avoir des fichiers au format :")
        print("  data/raw/sites/dataclean_prm_XXXXX.csv")
        return []

    print(f"✅ {len(sites)} site(s) trouvé(s) :\n")
    for i, prm in enumerate(sites, 1):
        print(f"  {i}. PRM: {prm}")

    return sites


def main_train(args):
    """
    Entraîne un ou plusieurs modèles Prophet.
    """
    print("\n" + "🚀" * 40)
    print("PIPELINE D'ENTRAÎNEMENT PROPHET")
    print("🚀" * 40 + "\n")

    config = load_config(args.config)
    raw_data_dir = Path(config["data"]["raw"]) / "sites"

    # Détecter tous les sites disponibles
    all_prm_files = detect_prms(raw_data_dir)

    if not all_prm_files:
        print(f"❌ Aucun fichier dataclean_prm_*.csv trouvé dans {raw_data_dir}")
        return

    # Déterminer les sites à traiter
    if args.all_sites:
        prm_files = all_prm_files
        print(f"📊 Entraînement Prophet sur {len(prm_files)} sites :\n")
        for prm in prm_files.keys():
            print(f"  • {prm}")
    else:
        prm = str(args.prm)
        if prm in all_prm_files:
            prm_files = {prm: all_prm_files[prm]}
            print(f"📊 Entraînement Prophet sur le site : {prm}\n")
        else:
            print(f"❌ Site {prm} non trouvé dans {raw_data_dir}")
            return

    # Entraîner chaque site
    results = {}
    for prm, data_path in prm_files.items():
        try:
            model, metrics = train_one_site(data_path, config, prm, args.config)
            results[prm] = metrics
        except Exception as e:
            print(f"\n❌ ERREUR pour le site {prm} : {e}")
            import traceback
            traceback.print_exc()
            results[prm] = None
            continue

    # Résumé
    print("\n" + "=" * 60)
    print("RÉSUMÉ DE L'ENTRAÎNEMENT")
    print("=" * 60)
    print(f"  {'PRM':<20} {'MAE (W)':>8} {'RMSE (W)':>8} {'MAPE':>7} {'R²':>8}")
    print(f"  {'-'*55}")

    for prm, metrics in results.items():
        if metrics:
            print(f"  {prm:<20} {metrics['mae']:>7.1f}  {metrics['rmse']:>7.1f}  "
                  f"{metrics['mape']:>6.1f}%  {metrics['r2']:>7.4f}")
        else:
            print(f"  {prm:<20}  {'ÉCHEC':>40}")

    print("\n" + "🎉" * 40)
    print("ENTRAÎNEMENT TERMINÉ")
    print("🎉" * 40)


def main_predict(args):
    """
    Pipeline de prédiction long terme avec Prophet.
    """
    print("\n" + "🔮" * 30)
    print("PIPELINE DE PRÉDICTION PROPHET")
    print("🔮" * 30 + "\n")

    prm = str(args.prm)

    # Charger la configuration
    config = load_config(args.config)

    # Vérifier que le modèle existe
    model_dir = Path(args.model_dir)
    model_path = model_dir / f"prophet_model_{prm}_latest.pkl"

    if not model_path.exists():
        print(f"❌ Erreur : Modèle introuvable : {model_path}")
        print(f"\nAssurez-vous d'avoir entraîné le modèle pour le PRM {prm} :")
        print(f"   python main.py train --prm {prm}")
        sys.exit(1)

    # Charger les données météo futures
    print("📂 Chargement des données météo futures...")
    try:
        meteo_future = pd.read_csv(args.meteo)
        print(f"✅ Météo future : {len(meteo_future)} lignes")
    except FileNotFoundError:
        print(f"❌ Erreur : Fichier météo non trouvé : {args.meteo}")
        sys.exit(1)

    # Prédire
    print("\n🔮 Génération des prédictions...")
    try:
        df_predictions = predict_future(
            prm=prm,
            meteo_future_df=meteo_future,
            model_dir=args.model_dir,
            config_path=args.config
        )

        # Définir le chemin de sortie
        if args.output:
            output_path = Path(args.output)
        else:
            pred_dir = Path(config["data"]["predictions"])
            pred_dir.mkdir(parents=True, exist_ok=True)
            output_path = pred_dir / f"predictions_{prm}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        # Sauvegarder
        df_predictions.to_csv(output_path, index=False)
        print(f"✅ Prédictions sauvegardées : {output_path}")

        print("\n" + "✅" * 30)
        print("PRÉDICTION TERMINÉE AVEC SUCCÈS")
        print("✅" * 30)
        print(f"\n📁 Fichier de sortie : {output_path}")

    except Exception as e:
        print(f"❌ Erreur lors de la prédiction : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main_predict_longterm(args):
    """
    Pipeline de prédiction long terme (1-3 ans) avec Prophet.

    Utilise des moyennes climatiques historiques pour générer la météo future.
    """
    print("\n" + "🔮" * 30)
    print(f"PIPELINE DE PRÉDICTION LONG TERME ({args.years} ANS)")
    print("🔮" * 30 + "\n")

    print("ℹ️  Utilise des moyennes climatiques (moins précis que court terme)\n")

    prm = str(args.prm)
    config = load_config(args.config)

    # Vérifier que le modèle existe
    model_dir = Path(args.model_dir)
    model_path = model_dir / f"prophet_model_{prm}_latest.pkl"

    if not model_path.exists():
        print(f"❌ Erreur : Modèle introuvable : {model_path}")
        print(f"\nAssurez-vous d'avoir entraîné le modèle pour le PRM {prm} :")
        print(f"   python main.py train --prm {prm}")
        sys.exit(1)

    # Fichier de données historiques
    historique_path = Path(config["data"]["raw"]) / "sites" / f"dataclean_prm_{prm}.csv"

    if not historique_path.exists():
        print(f"❌ Erreur : Fichier historique introuvable : {historique_path}")
        sys.exit(1)

    print(f"📂 Historique : {historique_path}")
    print(f"🤖 Modèle     : {model_path}")
    print()

    # Générer la météo future basée sur les moyennes climatiques
    print("🌦️  Génération de la météo future (moyennes climatiques)...")
    try:
        # Déterminer l'horizon (nombre d'heures)
        horizon_hours = args.years * 365.25 * 24  # Approximation
        horizon_hours = int(args.years * 8784)  # Utiliser 8784 h/an pour cohérence

        # Générer le fichier météo futur
        meteo_future = generate_climate_averages_pipeline(
            historique_path=str(historique_path),
            output_path=None,  # Pas de sauvegarde fichier, retourner directement
            start_date=None,
            nb_annees=args.years,
            add_variability=args.add_variability,
            config_path=args.config
        )

        print(f"✅ Météo générée : {len(meteo_future)} heures\n")

    except Exception as e:
        print(f"❌ Erreur lors de la génération de météo : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Prédire avec Prophet
    print("🔮 Génération des prédictions avec Prophet...")
    try:
        df_predictions = predict_future(
            prm=prm,
            meteo_future_df=meteo_future,
            model_dir=args.model_dir,
            config_path=args.config
        )

        # Définir le chemin de sortie
        if args.output:
            output_path = Path(args.output)
        else:
            pred_dir = Path(config["data"]["predictions"])
            pred_dir.mkdir(parents=True, exist_ok=True)
            output_path = pred_dir / f"predictions_longterm_{args.years}ans_{prm}.csv"

        # Sauvegarder
        df_predictions.to_csv(output_path, index=False)
        print(f"✅ Prédictions sauvegardées : {output_path}")

        # Afficher les statistiques
        print("\n" + "📊" * 20)
        print("STATISTIQUES DES PRÉDICTIONS")
        print("📊" * 20)

        stats = {
            'Nombre de points': len(df_predictions),
            'Puissance moyenne (W)': f"{df_predictions['yhat'].mean():.1f}",
            'Puissance max (W)': f"{df_predictions['yhat'].max():.1f}",
            'Puissance min (W)': f"{df_predictions['yhat'].min():.1f}",
            'Période': f"{df_predictions['datetime'].min()} → {df_predictions['datetime'].max()}"
        }

        for key, value in stats.items():
            print(f"  {key:<30}: {value}")

        print("\n" + "✅" * 30)
        print("PRÉDICTION LONG TERME TERMINÉE")
        print("✅" * 30)
        print(f"\n📁 Fichier de sortie : {output_path}")

    except Exception as e:
        print(f"❌ Erreur lors de la prédiction : {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Entraînement et prédiction de consommation énergétique avec Prophet"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')

    # Commande LIST-SITES
    list_parser = subparsers.add_parser('list-sites', help='Lister les sites disponibles')
    list_parser.add_argument('--config', type=str, default='config/config.yaml',
                           help='Chemin vers le fichier de configuration')

    # Commande TRAIN
    train_parser = subparsers.add_parser('train', help='Entraîner les modèles Prophet')
    train_group = train_parser.add_mutually_exclusive_group(required=True)
    train_group.add_argument('--prm', type=str,
                           help='PRM du site à entraîner')
    train_group.add_argument('--all-sites', action='store_true',
                           help='Entraîner sur tous les sites disponibles')
    train_parser.add_argument('--config', type=str, default='config/config.yaml',
                            help='Chemin vers le fichier de configuration')

    # Commande PREDICT (court terme avec météo réelle)
    predict_parser = subparsers.add_parser('predict', help='Prédiction court terme avec Prophet')
    predict_parser.add_argument('--prm', type=str, required=True,
                              help='Code PRM du site (ex: 30000540191777)')
    predict_parser.add_argument('--meteo', type=str, required=True,
                              help='Chemin vers les prévisions météo (fichier CSV)')
    predict_parser.add_argument('--output', type=str, default=None,
                              help='Chemin du fichier de sortie')
    predict_parser.add_argument('--model-dir', type=str, default='models/saved',
                              help='Répertoire des modèles sauvegardés')
    predict_parser.add_argument('--config', type=str, default='config/config.yaml',
                              help='Chemin vers le fichier de configuration')

    # Commande PREDICT-LONGTERM (long terme avec moyennes climatiques)
    longterm_parser = subparsers.add_parser('predict-longterm',
                                          help='Prédiction long terme avec moyennes climatiques')
    longterm_parser.add_argument('--prm', type=str, required=True,
                               help='Code PRM du site (ex: 30000540191777)')
    longterm_parser.add_argument('--years', type=int, default=3,
                               help='Nombre d\'années à prédire (défaut: 3)')
    longterm_parser.add_argument('--add-variability', action='store_true', default=True,
                               help='Ajouter de la variabilité météo réaliste')
    longterm_parser.add_argument('--output', type=str, default=None,
                               help='Chemin du fichier de sortie')
    longterm_parser.add_argument('--model-dir', type=str, default='models/saved',
                               help='Répertoire des modèles sauvegardés')
    longterm_parser.add_argument('--config', type=str, default='config/config.yaml',
                               help='Chemin vers le fichier de configuration')

    args = parser.parse_args()

    # Exécuter la commande appropriée
    if args.command == 'list-sites':
        list_sites(args.config)
    elif args.command == 'train':
        main_train(args)
    elif args.command == 'predict':
        main_predict(args)
    elif args.command == 'predict-longterm':
        main_predict_longterm(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
