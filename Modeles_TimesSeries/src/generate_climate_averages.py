"""
GÉNÉRATEUR DE CLIMAT SYNTHÉTIQUE LONG TERME
===========================================

Ce script ne produit PAS une prévision météo réelle (impossible >10 jours),
mais génère un climat futur réaliste statistiquement basé sur :

1) Climat historique saisonnier (mois + heure)
2) Variabilité météo corrélée dans le temps (persistance météo)
3) Tendance climatique long terme (réchauffement climatique)
4) Événements extrêmes simulés (canicules)
5) Jours fériés pour usage en modèles de consommation énergétique

Objectif :
Créer des données météo synthétiques réalistes pour :
- prévisions long terme (énergie, trafic, etc.)
- simulation de scénarios futurs
- entraînement de modèles ML

Ce dataset ≠ prévision météo opérationnelle.
C'est un "climat synthétique plausible".
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path
import sys



def load_config(config_path="config/config.yaml"):
    """Charge la configuration."""
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


def calculate_climate_averages(historique_df):
    """
    ÉTAPE 1 — CLIMATOLOGIE HISTORIQUE

    On transforme les données météo historiques en climat moyen saisonnier :
    moyenne par (mois, heure).

    Pourquoi ?
    → La météo varie énormément d’un jour à l’autre,
      mais le climat moyen est très stable.

    Exemple :
        Janvier 14h → moyenne historique de température.
        Juillet 16h → autre moyenne.

    On calcule aussi l'écart-type pour modéliser la variabilité météo.
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

    print(f"✅ Climat historique saisonnier calculé ({len(colonnes_disponibles)} variables)")
    print("📊 Ce climat servira de base pour générer le futur.")
    print(f"📅 Historique utilisé : {df['datetime'].min()} → {df['datetime'].max()}")
    print(f"📈 Volume de données : {len(df):,} heures")

    return meteo_moyenne

def add_climate_trend(df, start_date):
    """
    ÉTAPE 2 — AJOUT DU RÉCHAUFFEMENT CLIMATIQUE

    Les données historiques supposent un climat stationnaire,
    ce qui est FAUX aujourd’hui.

    On ajoute une tendance réaliste basée sur les observations Europe :
        +0.03 à +0.04 °C / an

    Sur 3 ans → ~ +0.1 °C
    Faible à court terme mais crucial statistiquement.

    On ajoute aussi une légère hausse d’humidité
    (air plus chaud = plus de vapeur d’eau).
    """
    df = df.copy()
    years_from_start = (df['datetime'] - pd.to_datetime(start_date)).dt.days / 365.25

    df['temperature'] += 0.035 * years_from_start   # +0.035°C/an
    df['humidite'] += 0.2 * years_from_start       # +0.2 %/an

    # S'assurer que les valeurs restent physiques
    df['humidite'] = np.clip(df['humidite'], 0, 100)
    df['temperature'] = np.clip(df['temperature'], -30, 50)

    print("🌍 Tendance climatique appliquée (réchauffement + humidité).")

    return df


def add_heatwaves(df):
    """
    ÉTAPE 3 — ÉVÉNEMENTS EXTRÊMES : CANICULES

    Les moyennes climatiques ne génèrent jamais d'extrêmes.
    Or le changement climatique augmente fortement :

        • fréquence des canicules
        • durée des épisodes chauds

    On simule ~3 canicules/an :
        durée : 2 à 5 jours
        intensité : +3 à +7°C
    """
    df = df.copy()
    summer_idx = df[df['datetime'].dt.month.isin([6,7,8,9])].index
    n_events = int(len(df) / (24*365) * 3)  # ~3 canicules/an

    for _ in range(n_events):
        if len(summer_idx) == 0:
            break
        start = np.random.choice(summer_idx[:-120])
        duration = np.random.randint(48, 120)
        df.loc[start:start+duration, 'temperature'] += np.random.uniform(3, 7)

    print("🔥 Simulation des événements extrêmes (canicules).")

    return df


def generate_correlated_noise(std_series, phi=0.9):
    """
    BRUIT MÉTÉO RÉALISTE (Processus AR(1))

    Sans ça :
        météo = bruit blanc → irréaliste

    Avec AR(1) :
        météo = persistante dans le temps

    Exemple réel :
        s'il fait 25°C → prochaine heure ≈ 24-26°C.

    phi = 0.9 → forte persistance météo.
    """
    noise = np.zeros(len(std_series))
    for i in range(1, len(noise)):
        noise[i] = phi * noise[i-1] + np.random.normal(0, std_series.iloc[i])
    return noise



def generate_future_meteo(start_date, nb_heures, meteo_moyenne, add_variability=True):
    """
    ÉTAPE 4 — GÉNÉRATION DU CLIMAT FUTUR SYNTHÉTIQUE

    On combine :
        • climat moyen saisonnier
        • variabilité météo corrélée dans le temps

    On obtient une météo "réaliste statistiquement".
    """
    # Créer les dates futures
    dates = pd.date_range(start=start_date, periods=nb_heures, freq='h')

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
                noise = generate_correlated_noise(meteo_future[col_std] * 0.3)
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

    print(f"🌦️ Génération météo synthétique : {nb_heures:,} heures")
    print("🔁 Variabilité météo corrélée activée (persistance météo).")
    print(f"📅 Période simulée : {meteo_future['datetime'].min()} → {meteo_future['datetime'].max()}")

    return meteo_future


def generate_climate_averages_pipeline(historique_path=None, output_path=None,
                                       start_date=None, nb_annees=3,
                                       add_variability=True, config_path="config/config.yaml",
                                       prm=None):
    """
    Pipeline complet pour générer des données météo moyennes pour prédictions long terme.

    Args:
        historique_path: Chemin vers les données historiques (si None, utilise prm)
        output_path: Chemin de sortie (optionnel)
        start_date: Date de début (si None, utilise la dernière date de l'historique + 1h)
        nb_annees: Nombre d'années à générer
        add_variability: Ajouter de la variabilité aléatoire
        config_path: Chemin vers la configuration
        prm: PRM du site (si fourni, charge automatiquement le dataclean correspondant)

    Returns:
        DataFrame avec données météo moyennes
    """
    print("=" * 80)
    print("🌍 GÉNÉRATION D’UN CLIMAT FUTUR SYNTHÉTIQUE")
    print("   (Basé sur climat historique + tendances climatiques)")
    print("=" * 80)
    # Si prm est fourni, charger automatiquement le fichier dataclean correspondant
    if prm is not None:
        if historique_path is None:
            historique_path = f"data/raw/sites/dataclean_prm_{prm}.csv"
            print(f"\n📍 PRM fourni : {prm}")
            print(f"   → Chargement automatique : {historique_path}")
        if output_path is None:
            output_path = f"data/raw/meteo/meteo_moyennes_3ans_{prm}.csv"
            print(f"   → Sortie automatique : {output_path}")
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

    # Ajout d'une tendance climatique réaliste (augementation des températures et humidité)
    print("📈 Ajout de la tendance climatique long terme...")
    meteo_future = add_climate_trend(meteo_future, start_date)

    # Ajout d'événements extrêmes (canicules)
    print("🔥 Ajout des événements extrêmes...")
    meteo_future = add_heatwaves(meteo_future)

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
    print("ℹ️ INTERPRÉTATION DU DATASET")
    print("=" * 80)
    print("✔️ Climat saisonnier réaliste")
    print("✔️ Variabilité météo temporelle")
    print("✔️ Réchauffement climatique intégré")
    print("✔️ Canicules simulées")
    print("")
    print("❌ Ce dataset n'est PAS une prévision météo réelle.")
    print("➡️ C'est un scénario climatique plausible pour simulations long terme.")
    print("=" * 80)


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
    import argparse

    parser = argparse.ArgumentParser(
        description="Génération de prévisions météo climatiques pour un site"
    )
    parser.add_argument('--prm', type=str, help='Code PRM du site')
    parser.add_argument('--historique', type=str, help='Chemin vers historique météo (optionnel si --prm fourni)')
    parser.add_argument('--output', type=str, help='Chemin de sortie (optionnel)')
    parser.add_argument('--nb-annees', type=int, default=3, help='Nombre d\'années à générer (défaut: 3)')
    parser.add_argument('--start-date', type=str, help='Date de début (format YYYY-MM-DD)')
    parser.add_argument('--no-variability', action='store_true', help='Désactiver la variabilité')

    args = parser.parse_args()

    if not args.prm and not args.historique:
        print("❌ Vous devez spécifier --prm ou --historique")
        parser.print_help()
        sys.exit(1)

    start_date = pd.Timestamp(args.start_date) if args.start_date else None

    generate_climate_averages_pipeline(
        prm=args.prm,
        historique_path=args.historique,
        output_path=args.output,
        start_date=start_date,
        nb_annees=args.nb_annees,
        add_variability=not args.no_variability
    )

    # Exemple d'utilisation (code original commenté)
    # historique = "dataFE_prm_30000250086126.csv"
    output_path = "data/raw/meteo/meteo_moyennes_3ans.csv"

    # Générer 3 ans de données météo moyennes
    meteo_3ans = generate_climate_averages_pipeline(
        historique_path=historique_path,
        output_path=output_path,
        nb_annees=3,
        add_variability=True  # Ajoute une variabilité réaliste
    )

    print(f"\n✅ Fichier prêt pour les prédictions long terme !")
    print(f"📁 Utilise ce fichier avec predict_longterm.py")
