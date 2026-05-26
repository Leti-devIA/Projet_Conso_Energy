"""
Génère prix_spot.csv au format horaire à partir des données existantes
(mensuel / trimestriel / annuel).

Méthode vectorisée (rapide) :
  - Construit la série horaire via broadcast numpy sur les plages de prix.
  - Applique un profil H24 et week-end pour simuler les variations spot.
  - Conserve les lignes non-horaires pour rétro-compatibilité.

Usage :
    python generate_hourly_prices.py
"""

import uuid
import pandas as pd
import numpy as np
from pathlib import Path

PRIX_FILE = Path(__file__).resolve().parent / "data" / "raw" / "prix" / "prix_spot.csv"

# ── Profil horaire (facteur multiplicatif / prix base) ────────────────────────
HOUR_FACTORS = np.array([
    0.78, 0.75, 0.73, 0.71, 0.72, 0.76,   # 0h-5h  nuit
    0.85, 0.95,                             # 6h-7h  rampe
    1.20, 1.30, 1.28, 1.25,                # 8h-11h matin peak
    1.12, 1.08,                             # 12h-13h midi
    1.10, 1.28, 1.32, 1.35, 1.30, 1.20,   # 14h-19h soir peak
    1.08, 1.00, 0.88, 0.82,                # 20h-23h rampe nuit
])

WEEKEND_FACTOR = 0.90
RNG = np.random.default_rng(42)


def main():
    print(f"Lecture de {PRIX_FILE} …")
    df = pd.read_csv(PRIX_FILE)
    df["date_deb"] = pd.to_datetime(df["date_deb"], format="mixed")
    df["date_fin"] = pd.to_datetime(df["date_fin"], format="mixed")

    # Exclure les lignes déjà horaires pour éviter les doublons
    df_agg = df[df["type"] != "horaire"].copy()
    print(f"  {len(df_agg)} lignes agrégées ({df_agg['type'].value_counts().to_dict()})")

    # ── Plage temporelle à couvrir ────────────────────────────────────────────
    start = df_agg["date_deb"].min().floor("h")
    end   = df_agg["date_fin"].max().floor("h")
    hours = pd.date_range(start, end, freq="h")
    print(f"  Plage : {start.date()} → {end.date()} ({len(hours):,} heures)")

    # ── Résolution vectorisée du prix pour chaque heure ──────────────────────
    priority_map = {"mensuel": 0, "trimestriel": 1, "annuel": 2}
    df_agg["prio"] = df_agg["type"].map(priority_map).fillna(99)

    hours_arr = hours.values.astype("datetime64[ns]")
    date_deb  = df_agg["date_deb"].values.astype("datetime64[ns]")
    date_fin  = df_agg["date_fin"].values.astype("datetime64[ns]")

    in_range    = (hours_arr[:, None] >= date_deb[None, :]) & \
                  (hours_arr[:, None] <= date_fin[None, :])
    prio_vals   = df_agg["prio"].values.astype(float)
    prio_matrix = np.where(in_range, prio_vals[None, :], np.inf)
    best_idx    = prio_matrix.argmin(axis=1)

    base_prices = df_agg["prix_base"].values[best_idx]
    peak_prices = df_agg["prix_peak"].values[best_idx]

    # Heures sans couverture → fallback
    no_cover = prio_matrix.min(axis=1) == np.inf
    base_prices[no_cover] = 55.0
    peak_prices[no_cover] = 65.0

    # ── Profil H24 + week-end + bruit ─────────────────────────────────────────
    hours_idx  = pd.DatetimeIndex(hours)
    h_factors  = HOUR_FACTORS[hours_idx.hour]
    we_factors = np.where(hours_idx.dayofweek >= 5, WEEKEND_FACTOR, 1.0)
    noise      = RNG.uniform(0.95, 1.05, size=len(hours))

    base_h = np.round(base_prices * h_factors * we_factors * noise, 4)
    peak_h = np.round(peak_prices * h_factors * we_factors * noise, 4)

    # ── Construction du DataFrame horaire ─────────────────────────────────────
    date_fin_h = hours + pd.Timedelta(hours=1) - pd.Timedelta(seconds=1)
    df_hourly  = pd.DataFrame({
        "periode":      hours_idx.strftime("%Y-%m-%d %H:%M"),
        "prix_base":    base_h,
        "type":         "horaire",
        "date_maj":     pd.Timestamp.now().isoformat(),
        "date_deb":     hours_idx.astype(str),
        "date_fin":     pd.DatetimeIndex(date_fin_h).astype(str),
        "id_prev_prix": [str(uuid.uuid4()) for _ in range(len(hours))],
        "prix_peak":    peak_h,
    })

    # ── Sauvegarde : horaire en premier (prioritaire dans le dashboard) ────────
    df_out = pd.concat([df_hourly, df_agg], ignore_index=True)
    PRIX_FILE.write_text(df_out.to_csv(index=False), encoding="utf-8")

    print(f"Fichier mis à jour : {PRIX_FILE}")
    print(f"  {len(df_hourly):,} lignes horaires + {len(df_agg)} agrégées = {len(df_out):,} total")
    print("\nAperçu (5 premières heures) :")
    print(df_hourly[["periode", "prix_base", "prix_peak", "type"]].head(5).to_string(index=False))


if __name__ == "__main__":
    main()
