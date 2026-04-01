"""
Générateur de climat synthétique long terme (support de formation).

Ce module crée une météo future "plausible" pour tester les scénarios long terme,
en combinant climatologie, variabilité, tendance et événements extrêmes simulés.

Important : ce n'est pas une prévision météo opérationnelle.
"""

import pandas as pd
import numpy as np
import yaml
from pathlib import Path
import sys


def load_config(config_path="config/config.yaml"):
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)


# ============================================================
# ÉTAPE 1 — CLIMATOLOGIE HISTORIQUE
# ============================================================

def calculate_climate_averages(historique_df):
    """
    Calcule la climatologie moyenne par (mois, heure) depuis l'historique.
    Retourne mean + std pour chaque variable météo.
    """
    df = historique_df.copy()
    df['datetime'] = pd.to_datetime(df['datetime'])
    df['mois']  = df['datetime'].dt.month
    df['heure'] = df['datetime'].dt.hour

    colonnes_meteo = ['temperature', 'humidite', 'vitesse_vent', 'couverture_nuages']
    colonnes_disponibles = [c for c in colonnes_meteo if c in df.columns]

    meteo_moyenne = df.groupby(['mois', 'heure'])[colonnes_disponibles].agg(['mean', 'std']).reset_index()
    meteo_moyenne.columns = ['_'.join(c).strip('_') for c in meteo_moyenne.columns.values]

    print(f"✅ Climatologie calculée ({len(colonnes_disponibles)} variables)")
    print(f"   Période historique : {df['datetime'].min().date()} → {df['datetime'].max().date()}")
    print(f"   Volume : {len(df):,} heures")

    return meteo_moyenne


# ============================================================
# ÉTAPE 2 — TENDANCE CLIMATIQUE
# ============================================================

def add_climate_trend(df, start_date):
    """
    Ajoute un réchauffement progressif réaliste (+0.035°C/an).
    Impact sur 3 ans : ~+0.1°C (faible mais correct physiquement).
    """
    df = df.copy()
    years_from_start = (df['datetime'] - pd.to_datetime(start_date)).dt.days / 365.25

    df['temperature'] += 0.035 * years_from_start
    df['humidite']    += 0.2   * years_from_start

    df['temperature'] = np.clip(df['temperature'], -30, 50)
    df['humidite']    = np.clip(df['humidite'],      0, 100)

    print("🌍 Tendance climatique appliquée (+0.035°C/an, +0.2%HR/an)")
    return df


# ============================================================
# ÉTAPE 3 — CANICULES (NON SUPERPOSABLES)
# ============================================================

def add_heatwaves(df):
    """
    Simule ~2 canicules par an en été.

    Corrections vs version précédente :
    - Utilise iloc (positions) et non loc (labels) → pas d'accumulation sur labels répétés
    - Vérifie qu'une canicule ne se superpose pas à une autre
    - Intensité plafonnée à +6°C pour rester physiquement plausible
    """
    df = df.copy()

    # Identifier les indices de position des mois d'été
    summer_mask = df['datetime'].dt.month.isin([6, 7, 8, 9])
    summer_positions = np.where(summer_mask)[0]

    if len(summer_positions) == 0:
        return df

    # ~2 canicules par an
    n_years = (df['datetime'].max() - df['datetime'].min()).days / 365.25
    n_events = max(1, int(round(n_years * 2)))

    occupied = np.zeros(len(df), dtype=bool)  # positions déjà occupées par une canicule

    placed = 0
    attempts = 0
    max_attempts = n_events * 20  # éviter boucle infinie

    while placed < n_events and attempts < max_attempts:
        attempts += 1

        # Choisir un point de départ aléatoire en été
        candidate_starts = summer_positions[summer_positions < len(df) - 120]
        if len(candidate_starts) == 0:
            break

        start_pos = int(np.random.choice(candidate_starts))
        duration  = np.random.randint(48, 96)  # 2 à 4 jours
        end_pos   = min(start_pos + duration, len(df) - 1)

        # Vérifier qu'il n'y a pas de chevauchement avec une canicule existante
        if occupied[start_pos:end_pos].any():
            continue

        # Appliquer la canicule
        intensity = np.random.uniform(3, 6)  # +3 à +6°C max
        df.iloc[start_pos:end_pos, df.columns.get_loc('temperature')] += intensity

        occupied[start_pos:end_pos] = True
        placed += 1

    df['temperature'] = np.clip(df['temperature'], -30, 50)

    print(f"🔥 {placed} canicule(s) simulée(s) (non superposées, +3 à +6°C, 2-4 jours)")
    return df


# ============================================================
# BRUIT MÉTÉO CORRÉLÉ (AR(1))
# ============================================================

def generate_correlated_noise(std_series, phi=0.85):
    """
    Génère un bruit AR(1) pour simuler la persistance météo.
    phi=0.85 → forte persistance (s'il fait chaud, ça reste chaud quelques heures).
    """
    noise = np.zeros(len(std_series))
    std_vals = std_series.fillna(0).values
    for i in range(1, len(noise)):
        noise[i] = phi * noise[i-1] + np.random.normal(0, max(std_vals[i], 1e-6))
    return noise


# ============================================================
# ÉTAPE 4 — GÉNÉRATION DU CLIMAT FUTUR
# ============================================================

def generate_future_meteo(start_date, nb_heures, meteo_moyenne, add_variability=True):
    """
    Génère le DataFrame météo futur en combinant :
    - climatologie moyenne saisonnière
    - bruit AR(1) calibré sur l'écart-type historique
    """
    dates = pd.date_range(start=start_date, periods=nb_heures, freq='h')

    meteo_future = pd.DataFrame({
        'datetime': dates,
        'mois':  dates.month,
        'heure': dates.hour,
    })

    meteo_future = meteo_future.merge(meteo_moyenne, on=['mois', 'heure'], how='left')

    colonnes_base = ['temperature', 'humidite', 'vitesse_vent', 'couverture_nuages']

    for col in colonnes_base:
        col_mean = f"{col}_mean"
        col_std  = f"{col}_std"

        if col_mean not in meteo_future.columns:
            continue

        if add_variability and col_std in meteo_future.columns:
            noise = generate_correlated_noise(meteo_future[col_std] * 0.3)
            meteo_future[col] = meteo_future[col_mean] + noise
        else:
            meteo_future[col] = meteo_future[col_mean]

        # Clipping physique
        clips = {
            'temperature':      (-30, 50),
            'humidite':         (0, 100),
            'vitesse_vent':     (0, 100),
            'couverture_nuages':(0, 100),
        }
        if col in clips:
            meteo_future[col] = np.clip(meteo_future[col], *clips[col])

    colonnes_finales = ['datetime'] + [c for c in colonnes_base if c in meteo_future.columns]
    meteo_future = meteo_future[colonnes_finales].reset_index(drop=True)

    print(f"🌦️  Météo synthétique générée : {nb_heures:,} heures")
    print(f"    Période : {meteo_future['datetime'].min()} → {meteo_future['datetime'].max()}")

    return meteo_future


# ============================================================
# PIPELINE PRINCIPAL
# ============================================================

def generate_climate_averages_pipeline(
    historique_path=None,
    output_path=None,
    start_date=None,
    nb_annees=3,
    add_variability=True,
    config_path="config/config.yaml",
    prm=None
):
    print("=" * 70)
    print("🌍 GÉNÉRATION D'UN CLIMAT FUTUR SYNTHÉTIQUE")
    print("=" * 70)

    # Résolution automatique des chemins via PRM
    if prm is not None:
        historique_path = historique_path or f"data/raw/sites/dataclean_prm_{prm}.csv"
        output_path     = output_path     or f"data/raw/meteo/meteo_horaire_{prm}.csv"
        print(f"📍 PRM : {prm}")
        print(f"   Historique : {historique_path}")
        print(f"   Sortie     : {output_path}")

    if historique_path is None:
        raise ValueError("Spécifiez --prm ou --historique")

    # Chargement
    print(f"\n📂 Chargement : {historique_path}")
    historique = pd.read_csv(historique_path)
    historique['datetime'] = pd.to_datetime(historique['datetime'])

    # Climatologie
    print("\n🔄 Calcul de la climatologie historique...")
    meteo_moyenne = calculate_climate_averages(historique)

    # Date de départ
    if start_date is None:
        start_date = (historique['datetime'].max() + pd.Timedelta(hours=1)).ceil('h')
    else:
        start_date = pd.to_datetime(start_date).ceil('h')
    print(f"\n📅 Départ : {start_date}")

    # Génération
    nb_heures = nb_annees * 365 * 24
    print(f"\n🔮 Génération de {nb_heures:,} heures ({nb_annees} an(s))...")
    meteo_future = generate_future_meteo(start_date, nb_heures, meteo_moyenne, add_variability)

    # Tendance
    print("\n📈 Tendance climatique...")
    meteo_future = add_climate_trend(meteo_future, start_date)

    # Canicules
    print("\n🔥 Événements extrêmes...")
    meteo_future = add_heatwaves(meteo_future)

    # Sauvegarde
    if output_path is None:
        config = load_config(config_path)
        output_dir = Path(config['data']['raw']) / "meteo"
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"meteo_horaire_{nb_annees}ans.csv"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    meteo_future.to_csv(output_path, index=False)
    print(f"\n✅ Fichier sauvegardé : {output_path}")

    # Statistiques finales
    print("\n" + "=" * 70)
    print("📊 STATISTIQUES FINALES")
    print("=" * 70)
    for col in ['temperature', 'humidite', 'vitesse_vent', 'couverture_nuages']:
        if col in meteo_future.columns:
            s = meteo_future[col]
            print(f"  {col:<20} min={s.min():.1f}  moy={s.mean():.1f}  max={s.max():.1f}")

    print("\n⚠️  Ce dataset est un scénario climatique plausible, pas une prévision réelle.")
    print("=" * 70)

    return meteo_future


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Génération de climat synthétique long terme")
    parser.add_argument('--prm',          type=str, help='Code PRM du site')
    parser.add_argument('--historique',   type=str, help='Chemin historique météo CSV')
    parser.add_argument('--output',       type=str, help='Chemin de sortie CSV')
    parser.add_argument('--nb-annees',    type=int, default=3, help='Années à générer (défaut: 3)')
    parser.add_argument('--start-date',   type=str, help='Date de début (YYYY-MM-DD)')
    parser.add_argument('--no-variability', action='store_true', help='Désactiver la variabilité aléatoire')
    parser.add_argument('--config',       type=str, default='config/config.yaml')

    args = parser.parse_args()

    if not args.prm and not args.historique:
        print("❌ Spécifiez --prm ou --historique")
        parser.print_help()
        sys.exit(1)

    start_date = pd.Timestamp(args.start_date) if args.start_date else None

    generate_climate_averages_pipeline(
        prm=args.prm,
        historique_path=args.historique,
        output_path=args.output,
        start_date=start_date,
        nb_annees=args.nb_annees,
        add_variability=not args.no_variability,
        config_path=args.config,
    )