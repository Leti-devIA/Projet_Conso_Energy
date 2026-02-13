"""
Prédictions long terme (3 ans) en utilisant des moyennes climatiques.
"""
import pandas as pd
import numpy as np
from pathlib import Path
import yaml

from predict import predict_future
from generate_climate_averages import generate_climate_averages_pipeline


def load_config(config_path="config/config.yaml"):
    """Charge la configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def predict_longterm(historique_path, nb_annees=3, batch_size=1000,
                     use_existing_meteo=None, add_trend=True,
                     model_dir="models/saved", config_path="config/config.yaml", prm=None):
    """
    Prédictions long terme (plusieurs années) avec données météo moyennes.

    Args:
        historique_path: Chemin vers les données historiques avec météo
        nb_annees: Nombre d'années à prédire
        batch_size: Nombre d'heures par batch (pour éviter les problèmes mémoire)
        use_existing_meteo: Chemin vers un fichier météo déjà généré (optionnel)
        add_trend: Ajouter une tendance de croissance annuelle
        model_dir: Répertoire des modèles
        config_path: Chemin vers la configuration
        prm: Code PRM du site (optionnel, pour charger le bon modèle)

    Returns:
        DataFrame avec toutes les prédictions
    """
    print("=" * 80)
    print(f"PRÉDICTIONS LONG TERME : {nb_annees} ANS")
    print("=" * 80)

    # Construire le suffixe du modèle si PRM fourni
    model_suffix = f"lstm_energy_forecast_{prm}" if prm else None
    if model_suffix:
        print(f"📌 Modèle spécifique au site : {model_suffix}")

    # Charger la configuration
    config = load_config(config_path)

    print(f"\n📂 Chargement de l'historique...")
    historique = pd.read_csv(historique_path)
    historique['datetime'] = pd.to_datetime(historique['datetime'])

    # Prendre les 48 dernières heures pour initialisation
    print(f"📊 Extraction des 48 dernières heures d'historique...")
    historique_48h = historique.tail(48).copy()

    # Renommer la colonne si nécessaire
    if 'puissance_moy_heure' in historique_48h.columns:
        historique_48h['puissance_kw'] = historique_48h['puissance_moy_heure'] / 1000

    # Vérifier les colonnes nécessaires
    colonnes_requises = ['datetime', 'puissance_kw', 'temperature', 'humidite']
    colonnes_manquantes = [col for col in colonnes_requises if col not in historique_48h.columns]
    if colonnes_manquantes:
        raise ValueError(f"Colonnes manquantes dans l'historique : {colonnes_manquantes}")

    historique_48h = historique_48h[['datetime', 'puissance_kw', 'temperature', 'humidite']]

    # Générer ou charger les données météo
    if use_existing_meteo:
        print(f"\n📂 Chargement des données météo : {use_existing_meteo}")
        meteo_future = pd.read_csv(use_existing_meteo)
        meteo_future['datetime'] = pd.to_datetime(meteo_future['datetime'])
    elif prm:
        # Construire le chemin automatiquement depuis data/raw/meteo/ avec le PRM
        meteo_path = Path(f"data/raw/meteo/meteo_moyennes_{nb_annees}ans_{prm}.csv")

        if meteo_path.exists():
            print(f"\n📂 Chargement des données météo depuis : {meteo_path}")
            meteo_future = pd.read_csv(meteo_path)
            meteo_future['datetime'] = pd.to_datetime(meteo_future['datetime'])
        else:
            print(f"\n⚠️  Fichier météo introuvable : {meteo_path}")
            print(f"🔄 Génération des données météo moyennes pour {nb_annees} ans...")
            meteo_future = generate_climate_averages_pipeline(
                historique_path=historique_path,
                output_path=str(meteo_path),
                nb_annees=nb_annees,
                add_variability=True,
                config_path=config_path
            )
            print(f"✅ Données météo sauvegardées : {meteo_path}")
    else:
        print(f"\n🔄 Génération des données météo moyennes pour {nb_annees} ans...")
        meteo_future = generate_climate_averages_pipeline(
            historique_path=historique_path,
            output_path=None,
            nb_annees=nb_annees,
            add_variability=True,
            config_path=config_path
        )

    # Ajouter jour_ferie si manquant dans les données météo futures
    if 'jour_ferie' not in meteo_future.columns:
        print("⚠️  Colonne 'jour_ferie' absente, ajout avec valeurs par défaut (0)")
        meteo_future['jour_ferie'] = 0

    # Nombre total d'heures à prédire
    total_heures = len(meteo_future)
    print(f"\n🔮 Prédiction de {total_heures:,} heures en batchs de {batch_size}...")

    # Initialiser la liste des prédictions
    all_predictions = []

    # Prédire par batchs
    nb_batchs = (total_heures + batch_size - 1) // batch_size

    for batch_idx in range(nb_batchs):
        # Déterminer les indices du batch
        start_idx = batch_idx * batch_size
        end_idx = min(start_idx + batch_size, total_heures)
        meteo_batch = meteo_future.iloc[start_idx:end_idx].copy()

        print(f"\n📦 Batch {batch_idx + 1}/{nb_batchs} : heures {start_idx} à {end_idx}")

        # Pour le premier batch, utiliser l'historique réel
        # Pour les suivants, utiliser les dernières prédictions
        if batch_idx == 0:
            hist_batch = historique_48h.copy()
            # Ajouter jour_ferie si manquant
            if 'jour_ferie' not in hist_batch.columns:
                hist_batch['jour_ferie'] = 0
        else:
            # Prendre les 48 dernières prédictions comme "historique"
            last_predictions = all_predictions[-48:]
            hist_batch = pd.DataFrame(last_predictions)
            hist_batch = hist_batch.rename(columns={'puissance_kw_pred': 'puissance_kw'})

            # Récupérer les données météo correspondantes
            meteo_hist = meteo_future.iloc[start_idx-48:start_idx].copy()
            hist_batch['temperature'] = meteo_hist['temperature'].values
            hist_batch['humidite'] = meteo_hist['humidite'].values
            if 'jour_ferie' in meteo_hist.columns:
                hist_batch['jour_ferie'] = meteo_hist['jour_ferie'].values
            else:
                hist_batch['jour_ferie'] = 0

        # Prédire ce batch
        try:
            predictions_batch = predict_future(
                hist_batch,
                meteo_batch,
                model_dir=model_dir,
                config_path=config_path,
                horizon=len(meteo_batch),
                model_suffix=model_suffix
            )

            all_predictions.extend(predictions_batch.to_dict('records'))
            print(f"✅ Batch {batch_idx + 1} terminé : {len(predictions_batch)} prédictions")

        except Exception as e:
            print(f"❌ Erreur sur le batch {batch_idx + 1} : {e}")
            break

    # Créer le DataFrame final
    df_predictions = pd.DataFrame(all_predictions)

    # Ajouter une tendance si demandé
    if add_trend and len(df_predictions) > 0:
        print(f"\n📈 Ajout d'une tendance de croissance annuelle...")

        # Calculer une tendance de +1% par an (à ajuster selon le contexte)
        croissance_annuelle = 0.01  # 1% par an

        # Calculer le nombre de jours depuis le début
        df_predictions['jours_depuis_debut'] = (
            (df_predictions['datetime'] - df_predictions['datetime'].min()).dt.total_seconds() / 86400
        )

        # Calculer le facteur de croissance
        facteur_croissance = 1 + (croissance_annuelle * df_predictions['jours_depuis_debut'] / 365)

        # Appliquer la tendance
        df_predictions['puissance_kw_pred_original'] = df_predictions['puissance_kw_pred'].copy()
        df_predictions['puissance_kw_pred'] = df_predictions['puissance_kw_pred'] * facteur_croissance

        print(f"✅ Tendance ajoutée : +{croissance_annuelle*100}% par an")
        print(f"📊 Impact :")
        print(f"   Début  : {df_predictions['puissance_kw_pred'].iloc[:100].mean():.2f} kW")
        print(f"   Fin    : {df_predictions['puissance_kw_pred'].iloc[-100:].mean():.2f} kW")
        print(f"   Augmentation : +{((df_predictions['puissance_kw_pred'].iloc[-100:].mean() / df_predictions['puissance_kw_pred'].iloc[:100].mean()) - 1) * 100:.1f}%")

    # Statistiques finales
    print("\n" + "=" * 80)
    print("📊 RÉSULTATS FINAUX")
    print("=" * 80)
    print(f"Nombre de prédictions : {len(df_predictions):,} heures")
    print(f"Période               : {df_predictions['datetime'].min()} → {df_predictions['datetime'].max()}")
    print(f"Consommation prédite  :")
    print(f"  Min     : {df_predictions['puissance_kw_pred'].min():.2f} kW")
    print(f"  Max     : {df_predictions['puissance_kw_pred'].max():.2f} kW")
    print(f"  Moyenne : {df_predictions['puissance_kw_pred'].mean():.2f} kW")

    # Statistiques par année
    df_predictions['annee'] = df_predictions['datetime'].dt.year
    print(f"\n📅 Consommation moyenne par année :")
    for annee, groupe in df_predictions.groupby('annee'):
        print(f"  {annee} : {groupe['puissance_kw_pred'].mean():.2f} kW")

    print("\n⚠️  AVERTISSEMENT :")
    print("    Ces prédictions sont basées sur des MOYENNES CLIMATIQUES.")
    print("    Elles sont INDICATIVES et moins précises que des prévisions à court terme.")
    print("    À utiliser pour des projections macro, pas pour de l'opérationnel quotidien.")
    print("=" * 80)

    return df_predictions


def save_longterm_predictions(df_predictions, output_path=None, config_path="config/config.yaml", prm=None):
    """
    Sauvegarde les prédictions long terme avec métadonnées.

    Args:
        df_predictions: DataFrame avec les prédictions
        output_path: Chemin de sortie (optionnel)
        config_path: Chemin vers la configuration
        prm: Code PRM du site (optionnel)
    """
    if output_path is None:
        config = load_config(config_path)
        predictions_dir = Path(config['data']['predictions'])
        predictions_dir.mkdir(parents=True, exist_ok=True)

        # Calculer le nombre d'années correctement (arrondi au supérieur)
        nb_jours = (df_predictions['datetime'].max() - df_predictions['datetime'].min()).days
        nb_annees_calcul = int(np.ceil(nb_jours / 365))

        # Ajouter le PRM au nom du fichier si disponible
        if prm:
            output_path = predictions_dir / f"predictions_longterm_{nb_annees_calcul}ans_{prm}.csv"
        else:
            output_path = predictions_dir / f"predictions_longterm_{nb_annees_calcul}ans.csv"

    # Sauvegarder
    df_predictions.to_csv(output_path, index=False)
    print(f"\n✅ Prédictions sauvegardées : {output_path}")

    # Créer aussi un fichier de statistiques
    stats_path = Path(output_path).parent / f"{Path(output_path).stem}_stats.txt"
    with open(stats_path, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("STATISTIQUES DES PRÉDICTIONS LONG TERME\n")
        f.write("=" * 80 + "\n\n")
        f.write(f"Période : {df_predictions['datetime'].min()} → {df_predictions['datetime'].max()}\n")
        f.write(f"Nombre d'heures : {len(df_predictions):,}\n")
        f.write(f"Nombre de jours : {len(df_predictions)//24:,}\n\n")
        f.write("Consommation prédite :\n")
        f.write(f"  Min     : {df_predictions['puissance_kw_pred'].min():.2f} kW\n")
        f.write(f"  Max     : {df_predictions['puissance_kw_pred'].max():.2f} kW\n")
        f.write(f"  Moyenne : {df_predictions['puissance_kw_pred'].mean():.2f} kW\n")
        f.write(f"  Médiane : {df_predictions['puissance_kw_pred'].median():.2f} kW\n")
        f.write(f"  Écart-type : {df_predictions['puissance_kw_pred'].std():.2f} kW\n\n")

        if 'annee' in df_predictions.columns:
            f.write("Consommation moyenne par année :\n")
            for annee, groupe in df_predictions.groupby('annee'):
                f.write(f"  {annee} : {groupe['puissance_kw_pred'].mean():.2f} kW\n")

        f.write("\n" + "=" * 80 + "\n")
        f.write("AVERTISSEMENT\n")
        f.write("=" * 80 + "\n")
        f.write("Ces prédictions sont basées sur des MOYENNES CLIMATIQUES.\n")
        f.write("Elles sont INDICATIVES et moins précises que des prévisions à court terme.\n")

    print(f"✅ Statistiques sauvegardées : {stats_path}")

    return output_path
