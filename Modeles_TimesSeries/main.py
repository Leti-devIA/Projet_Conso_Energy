"""
Point d'entrée principal pour entraîner ou prédire avec le modèle LSTM.

Usage:
    # Entraîner avec un site spécifique
    python main.py train --prm 30000250086126

    # Entraîner avec tous les sites disponibles
    python main.py train --all-sites

    # Lister les sites disponibles
    python main.py list-sites

    # Prédiction
    python main.py predict --historique hist.csv --meteo meteo.csv --horizon 360
"""
import argparse
import sys
from pathlib import Path

# Ajouter le répertoire src au path si nécessaire
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from preprocessing import preprocess_pipeline
from feature_engineering import feature_engineering_pipeline
from train import train_model
from predict import predict_future, save_predictions
from predict_longterm import predict_longterm, save_longterm_predictions
from data_loader import get_data_loader
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
    Pipeline complet d'entraînement.

    Args:
        args: Arguments de la ligne de commande
    """
    print("\n" + "🚀" * 30)
    print("PIPELINE D'ENTRAÎNEMENT")
    print("🚀" * 30 + "\n")

    # Créer le data loader
    loader = get_data_loader('csv', args.config)

    # Déterminer les PRMs à traiter
    if args.all_sites:
        prms = loader.list_available_sites()
        if not prms:
            print("❌ Aucun site trouvé!")
            sys.exit(1)
        print(f"📊 Entraînement sur {len(prms)} sites : {', '.join(prms)}\n")
    elif args.prm:
        prms = [args.prm]
        print(f"📊 Entraînement sur le site : {args.prm}\n")
    else:
        print("❌ Vous devez spécifier --prm ou --all-sites")
        sys.exit(1)

    # Traiter chaque site
    for prm in prms:
        print("\n" + "=" * 60)
        print(f"TRAITEMENT DU SITE : {prm}")
        print("=" * 60 + "\n")

        # 1. Charger les données
        print("📂 Chargement des données...")
        df = loader.load_site_data(prm=prm)

        # 2. Preprocessing
        if args.skip_preprocessing:
            print("⏭️ Preprocessing ignoré")
        else:
            print("\n🔧 ÉTAPE 1/3 : Preprocessing")
            output_preprocessed = f"data/processed/data_preprocessed_{prm}.csv"
            df = preprocess_pipeline(df, output_preprocessed, args.config, from_dataframe=True)

        # 3. Feature Engineering
        if args.skip_features:
            print("⏭️ Feature engineering ignoré")
            df_fe = df
        else:
            print("\n🔧 ÉTAPE 2/3 : Feature Engineering")
            df_fe = feature_engineering_pipeline(df, args.config)
            output_features = f"data/processed/data_with_features_{prm}.csv"
            df_fe.to_csv(output_features, index=False)
            print(f"✅ Données avec features sauvegardées : {output_features}")

        # 4. Entraînement
        print("\n🔧 ÉTAPE 3/3 : Entraînement")
        data_path = f"data/processed/data_with_features_{prm}.csv"
        model, history, metrics = train_model(
            data_path,
            args.config,
            use_tensorboard=not args.no_tensorboard,
            model_suffix=prm
        )

        print("\n" + "🎉" * 30)
        print(f"ENTRAÎNEMENT TERMINÉ POUR LE SITE {prm}")
        print("🎉" * 30)
        print(f"\n📊 Résultats finaux :")
        print(f"   MAE  : {metrics['mae']:.2f} kW")
        print(f"   RMSE : {metrics['rmse']:.2f} kW")
        print(f"   R²   : {metrics['r2']:.4f}")
        print(f"   MAPE : {metrics['mape']:.2f}%")



def main_predict(args):
    """
    Pipeline de prédiction.

    Args:
        args: Arguments de la ligne de commande
    """
    print("\n" + "🔮" * 30)
    print("PIPELINE DE PRÉDICTION")
    print("🔮" * 30 + "\n")

    # Charger les données
    print("📂 Chargement des données...")
    historique = pd.read_csv(args.historique)
    meteo_future = pd.read_csv(args.meteo)

    print(f"✅ Historique : {len(historique)} lignes")
    print(f"✅ Météo future : {len(meteo_future)} lignes")

    # Prédire
    predictions = predict_future(
        historique,
        meteo_future,
        model_dir=args.model_dir,
        config_path=args.config,
        horizon=args.horizon
    )

    # Sauvegarder
    output_path = save_predictions(predictions, args.output, args.config)

    print("\n" + "✅" * 30)
    print("PRÉDICTION TERMINÉE AVEC SUCCÈS")
    print("✅" * 30)
    print(f"\n📁 Fichier de sortie : {output_path}")


def main_predict_longterm(args):
    """
    Pipeline de prédiction long terme (3 ans).

    Args:
        args: Arguments de la ligne de commande
    """
    print("\n" + "🔮" * 30)
    print(f"PIPELINE DE PRÉDICTION LONG TERME ({args.years} ANS)")
    print("🔮" * 30 + "\n")

    print("⚠️  ATTENTION : Utilise des moyennes climatiques (moins précis)")
    print()

    # Prédire
    predictions = predict_longterm(
        historique_path=args.historique,
        nb_annees=args.years,
        batch_size=args.batch_size,
        add_trend=args.add_trend,
        model_dir=args.model_dir,
        config_path=args.config
    )

    # Sauvegarder
    output_path = save_longterm_predictions(predictions, args.output, args.config)

    print("\n" + "✅" * 30)
    print("PRÉDICTION LONG TERME TERMINÉE")
    print("✅" * 30)
    print(f"\n📁 Fichier de sortie : {output_path}")


def main():
    """Point d'entrée principal."""
    parser = argparse.ArgumentParser(
        description="Entraînement et prédiction de consommation énergétique avec LSTM"
    )

    subparsers = parser.add_subparsers(dest='command', help='Commandes disponibles')

    # Commande LIST-SITES
    list_parser = subparsers.add_parser('list-sites', help='Lister les sites disponibles')
    list_parser.add_argument('--config', type=str, default='config/config.yaml',
                           help='Chemin vers le fichier de configuration')

    # Commande TRAIN
    train_parser = subparsers.add_parser('train', help='Entraîner le modèle')
    train_group = train_parser.add_mutually_exclusive_group(required=True)
    train_group.add_argument('--prm', type=str,
                           help='PRM du site à entraîner')
    train_group.add_argument('--all-sites', action='store_true',
                           help='Entraîner sur tous les sites disponibles')
    train_parser.add_argument('--config', type=str, default='config/config.yaml',
                            help='Chemin vers le fichier de configuration')
    train_parser.add_argument('--skip-preprocessing', action='store_true',
                            help='Ignorer le preprocessing')
    train_parser.add_argument('--skip-features', action='store_true',
                            help='Ignorer le feature engineering')
    train_parser.add_argument('--no-tensorboard', action='store_true',
                            help='Désactiver TensorBoard')

    # Commande PREDICT
    predict_parser = subparsers.add_parser('predict', help='Faire des prédictions')
    predict_parser.add_argument('--historique', type=str, required=True,
                              help='Chemin vers les données historiques (48h min)')
    predict_parser.add_argument('--meteo', type=str, required=True,
                              help='Chemin vers les prévisions météo')
    predict_parser.add_argument('--horizon', type=int, default=None,
                              help='Nombre d\'heures à prédire (défaut: toute la météo)')
    predict_parser.add_argument('--output', type=str, default=None,
                              help='Chemin du fichier de sortie')
    predict_parser.add_argument('--model-dir', type=str, default='models/saved',
                              help='Répertoire des modèles sauvegardés')
    predict_parser.add_argument('--config', type=str, default='config/config.yaml',
                              help='Chemin vers le fichier de configuration')

    # Commande PREDICT-LONGTERM (3 ans avec moyennes climatiques)
    longterm_parser = subparsers.add_parser('predict-longterm',
                                          help='Prédictions long terme (3 ans) avec moyennes climatiques')
    longterm_parser.add_argument('--historique', type=str, required=True,
                               help='Chemin vers les données historiques complètes')
    longterm_parser.add_argument('--years', type=int, default=3,
                               help='Nombre d\'années à prédire (défaut: 3)')
    longterm_parser.add_argument('--batch-size', type=int, default=1000,
                               help='Taille des batchs (défaut: 1000)')
    longterm_parser.add_argument('--add-trend', action='store_true', default=True,
                               help='Ajouter une tendance de croissance')
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
