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
from generate_climate_averages import generate_climate_averages_pipeline


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
    Entraîne un ou plusieurs modèles LSTM.
    """
    print("\n" + "🚀" * 40)
    print("PIPELINE D'ENTRAÎNEMENT")
    print("🚀" * 40 + "\n")

    # Charger le DataLoader
    loader = get_data_loader('csv', args.config)

    # Déterminer les sites à traiter
    if args.all_sites:
        sites_df = loader.load_sites_table()
        prms = sites_df['prm'].astype(str).tolist()  # Convertir en string
        print(f"📊 Entraînement sur {len(prms)} sites : {', '.join(prms)}\n")
    else:
        prms = [str(args.prm)]  # Convertir en string

    # Traiter chaque site
    for prm in prms:
        try:
            print("\n" + "=" * 60)
            print(f"TRAITEMENT DU SITE : {prm}")
            print("=" * 60)

            # 1. Charger les données du site
            print("\n📂 Chargement des données...")
            df_conso = loader.load_site_data(prm=prm)

            # 2. Charger les données météo correspondantes
            print(f"📂 Chargement de la météo pour le site {prm}...")
            try:
                df_meteo = loader.load_meteo_data(prm=prm)

                # Fusionner consommation et météo
                print("🔗 Fusion des données de consommation et météo...")
                df_meteo['datetime'] = pd.to_datetime(df_meteo['datetime'])
                df_conso['datetime'] = pd.to_datetime(df_conso['datetime'])

                df = df_conso.merge(df_meteo, on='datetime', how='left', suffixes=('', '_meteo'))

                print(f"   ✅ {len(df)} lignes après fusion")
                print(f"   📋 Colonnes après fusion : {list(df.columns)[:10]}...")  # Afficher premières colonnes

            except FileNotFoundError as e:
                print(f"⚠️  Pas de données météo trouvées pour {prm}")
                print(f"   Génération automatique de la météo...")

                # Générer la météo pour ce site
                df_meteo = generate_climate_averages_pipeline(
                    historique_path=f"data/raw/sites/dataclean_prm_{prm}.csv",
                    output_path=f"data/raw/meteo/meteo_moyennes_3ans_{prm}.csv",
                    start_date=None,
                    nb_annees=3,
                    add_variability=True,
                    config_path=args.config
                )

                # Réessayer la fusion
                df_meteo['datetime'] = pd.to_datetime(df_meteo['datetime'])
                df = df_conso.merge(df_meteo, on='datetime', how='left', suffixes=('', '_meteo'))

            # 3. Preprocessing
            print("\n🔧 ÉTAPE 1/3 : Preprocessing")
            df_preprocessed = preprocess_pipeline(
                df,
                output_filepath=f"data/processed/data_preprocessed_{prm}.csv",
                config_path=args.config
            )

            # 4. Feature Engineering
            print("\n🔧 ÉTAPE 2/3 : Feature Engineering")
            df_features = feature_engineering_pipeline(
                df_preprocessed,
                config_path=args.config
            )

            # Sauvegarder
            output_path = f"data/processed/data_with_features_{prm}.csv"
            df_features.to_csv(output_path, index=False)
            print(f"✅ Données avec features sauvegardées : {output_path}")

            # 5. Entraînement
            print("\n🔧 ÉTAPE 3/3 : Entraînement")
            model, history, metrics = train_model(
                data_path=output_path,
                config_path=args.config,
                model_suffix=f"lstm_energy_forecast_{prm}"
            )

            # Afficher les résultats
            print("\n" + "=" * 60)
            print(f"✅ MODÈLE ENTRAÎNÉ POUR LE SITE {prm}")
            print("=" * 60)
            print(f"📊 Métriques finales :")
            print(f"   Test RMSE  : {metrics['test_rmse']:.2f} kW")
            print(f"   Test MAE   : {metrics['test_mae']:.2f} kW")
            print(f"   Test R²    : {metrics['test_r2']:.4f}")

        except Exception as e:
            print(f"\n❌ ERREUR pour le site {prm} : {e}")
            import traceback
            traceback.print_exc()
            continue

    print("\n" + "🎉" * 40)
    print("ENTRAÎNEMENT TERMINÉ POUR TOUS LES SITES")
    print("🎉" * 40)


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

    # Construire les chemins automatiquement
    prm = args.prm
    historique_path = f"data/processed/data_preprocessed_{prm}.csv"
    model_suffix = f"lstm_energy_forecast_{prm}"

    # Vérifier que le fichier historique existe
    if not Path(historique_path).exists():
        print(f"❌ Erreur : Fichier historique introuvable : {historique_path}")
        print(f"\nAssurez-vous d'avoir entraîné le modèle pour le PRM {prm} :")
        print(f"   python main.py train --prm {prm}")
        sys.exit(1)

    # Vérifier que le modèle existe
    model_path = Path(args.model_dir) / f"lstm_energy_forecast_latest_{model_suffix}.h5"
    if not model_path.exists():
        print(f"❌ Erreur : Modèle introuvable : {model_path}")
        print(f"\nAssurez-vous d'avoir entraîné le modèle pour le PRM {prm} :")
        print(f"   python main.py train --prm {prm}")
        sys.exit(1)

    print(f"📂 Historique : {historique_path}")
    print(f"🤖 Modèle : {model_path}")
    print()

    # Prédire
    predictions = predict_longterm(
        historique_path=historique_path,
        nb_annees=args.years,
        batch_size=args.batch_size,
        add_trend=args.add_trend,
        model_dir=args.model_dir,
        config_path=args.config,
        prm=prm
    )

    # Sauvegarder avec le PRM
    output_path = save_longterm_predictions(predictions, args.output, args.config, prm=prm)

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
    train_parser.add_argument('--epochs', type=int, default=50,
                            help='Nombre d\'époques d\'entraînement (défaut: 50)')
    train_parser.add_argument('--batch-size', type=int, default=32,
                            help='Taille des batchs (défaut: 32)')

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
    longterm_parser.add_argument('--prm', type=str, required=True,
                               help='Code PRM du site (ex: 30000540191777)')
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
