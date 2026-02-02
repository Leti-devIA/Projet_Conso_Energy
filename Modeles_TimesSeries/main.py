"""
Point d'entrée principal pour entraîner ou prédire avec le modèle LSTM.

Usage:
    python main.py train --data dataFE_prm_30000250086126.csv
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
import pandas as pd


def main_train(args):
    """
    Pipeline complet d'entraînement.
    
    Args:
        args: Arguments de la ligne de commande
    """
    print("\n" + "🚀" * 30)
    print("PIPELINE D'ENTRAÎNEMENT")
    print("🚀" * 30 + "\n")
    
    # 1. Preprocessing
    if args.skip_preprocessing:
        print("⏭️ Preprocessing ignoré")
        df = pd.read_csv(args.data)
    else:
        print("🔧 ÉTAPE 1/3 : Preprocessing")
        output_preprocessed = "data/processed/data_preprocessed.csv"
        df = preprocess_pipeline(args.data, output_preprocessed, args.config)
    
    # 2. Feature Engineering
    if args.skip_features:
        print("⏭️ Feature engineering ignoré")
        df_fe = df
    else:
        print("\n🔧 ÉTAPE 2/3 : Feature Engineering")
        df_fe = feature_engineering_pipeline(df, args.config)
        output_features = "data/processed/data_with_features.csv"
        df_fe.to_csv(output_features, index=False)
        print(f"✅ Données avec features sauvegardées : {output_features}")
    
    # 3. Entraînement
    print("\n🔧 ÉTAPE 3/3 : Entraînement")
    data_path = "data/processed/data_with_features.csv"
    model, history, metrics = train_model(data_path, args.config, use_tensorboard=not args.no_tensorboard)
    
    print("\n" + "🎉" * 30)
    print("ENTRAÎNEMENT TERMINÉ AVEC SUCCÈS")
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
    
    # Commande TRAIN
    train_parser = subparsers.add_parser('train', help='Entraîner le modèle')
    train_parser.add_argument('--data', type=str, required=True,
                             help='Chemin vers les données brutes')
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
    if args.command == 'train':
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
