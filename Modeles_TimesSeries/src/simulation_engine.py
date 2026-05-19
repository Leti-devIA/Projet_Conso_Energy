"""
Moteur de simulation d'achats à terme — calcul horaire.

Formule de coût horaire :
    C_h = V_achetés_h × P_achetés_h + P_spot_h × (C_réelle_h − V_achetés_h)

Ce module :
  - Expanse le portefeuille existant en volumes/prix horaires
  - Expanse les achats simulés selon leur typologie (Base, Peak, OffPeak, custom)
  - Calcule le scénario A (référence) et B (simulé) heure par heure
  - Produit les KPIs comparatifs et les séries temporelles
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Literal


# ── Définition d'un achat simulé ──────────────────────────────────────────────

@dataclass
class SimulatedPurchase:
    """Un achat (ou vente) à terme envisagé par l'utilisateur."""
    label: str                          # ex: "BaseLoad", "Peakload", "Bloc custom"
    direction: Literal["Achat", "Vente"]
    volume_mw: float                    # puissance en MW (toujours positif)
    price_eur_mwh: float                # prix contractuel €/MWh
    hour_start: int = 0                 # début de la plage horaire (0–23)
    hour_end: int = 24                  # fin exclusive (1–24)
    days: Literal["all", "business", "weekend"] = "all"  # jours couverts


# ── Utilitaires calendrier ────────────────────────────────────────────────────

def is_business_day(dt: pd.Timestamp) -> bool:
    """Jour ouvré = lundi–vendredi (sans gestion des jours fériés)."""
    return dt.weekday() < 5


def build_hourly_index(start: pd.Timestamp, end: pd.Timestamp) -> pd.DatetimeIndex:
    """Génère un index horaire complet entre start et end (inclus)."""
    return pd.date_range(start=start, end=end, freq="h")


# ── Expansion du portefeuille existant ────────────────────────────────────────

def expand_portfolio_hourly(
    achats_df: pd.DataFrame,
    hourly_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Expanse le portefeuille d'achats existants en volume/prix par heure.

    Retourne un DataFrame indexé sur datetime avec colonnes :
        - vol_portfolio_mwh : volume total couvert (MW × 1h = MWh)
        - prix_portfolio_wavg : prix moyen pondéré du portefeuille
    """
    # Initialiser les séries horaires
    vol = pd.Series(0.0, index=hourly_index, name="vol_portfolio_mwh")
    cost = pd.Series(0.0, index=hourly_index, name="cost_portfolio_eur")

    if achats_df.empty:
        result = pd.DataFrame({"vol_portfolio_mwh": vol, "cost_portfolio_eur": cost})
        result["prix_portfolio_wavg"] = 0.0
        return result

    for _, row in achats_df.iterrows():
        deb = pd.Timestamp(row["DEB_PERIODE"])
        fin = pd.Timestamp(row["FIN_PERIODE"])
        mw = float(row["FIXATION_PUISSANCE_ACHAT_MW"])
        prix = float(row["PRIX_FIXATION"])
        type_achat = str(row.get("TYPE_ACHAT", "Base")).strip().upper()

        # Masque temporel : heures comprises dans la période du contrat
        mask = (hourly_index >= deb) & (hourly_index <= fin)

        # Appliquer la typologie horaire
        if "PEAK" in type_achat or "POINTE" in type_achat:
            # Peakload : 8h–20h, jours ouvrés
            hour_mask = (hourly_index.hour >= 8) & (hourly_index.hour < 20)
            bday_mask = pd.Series(hourly_index, index=hourly_index).apply(
                lambda dt: dt.weekday() < 5
            )
            mask = mask & hour_mask & bday_mask
        elif "OFF" in type_achat:
            # OffPeak : heures hors peakload
            peak_mask = (
                (hourly_index.hour >= 8) & (hourly_index.hour < 20)
                & pd.Series(hourly_index, index=hourly_index).apply(
                    lambda dt: dt.weekday() < 5
                )
            )
            mask = mask & ~peak_mask
        # Sinon Base : toutes les heures → mask déjà correct

        # Chaque heure couverte reçoit mw MWh (puissance MW × 1 heure)
        vol[mask] += mw      # MWh par heure
        cost[mask] += mw * prix  # € par heure

    result = pd.DataFrame({
        "vol_portfolio_mwh": vol,
        "cost_portfolio_eur": cost,
    })
    result["prix_portfolio_wavg"] = np.where(
        result["vol_portfolio_mwh"] > 0,
        result["cost_portfolio_eur"] / result["vol_portfolio_mwh"],
        0.0,
    )
    return result


# ── Expansion d'un achat simulé ───────────────────────────────────────────────

def expand_purchase_hourly(
    purchase: SimulatedPurchase,
    hourly_index: pd.DatetimeIndex,
) -> pd.DataFrame:
    """
    Expanse un achat simulé en volume/prix par heure.

    Retourne un DataFrame indexé sur datetime avec colonnes :
        - vol_sim_mwh : volume signé (+ achat, − vente) en MWh par heure
        - cost_sim_eur : coût signé en € par heure
    """
    sign = 1.0 if purchase.direction == "Achat" else -1.0
    vol = pd.Series(0.0, index=hourly_index)

    # Masque horaire
    hour_mask = (hourly_index.hour >= purchase.hour_start) & (
        hourly_index.hour < purchase.hour_end
    )

    # Masque jours
    if purchase.days == "business":
        day_mask = pd.Series(hourly_index, index=hourly_index).apply(
            lambda dt: dt.weekday() < 5
        )
    elif purchase.days == "weekend":
        day_mask = pd.Series(hourly_index, index=hourly_index).apply(
            lambda dt: dt.weekday() >= 5
        )
    else:
        day_mask = pd.Series(True, index=hourly_index)

    mask = hour_mask & day_mask
    vol[mask] = sign * purchase.volume_mw  # MWh = MW × 1h

    return pd.DataFrame({
        "vol_sim_mwh": vol,
        "cost_sim_eur": vol * purchase.price_eur_mwh,
    })


# ── Calcul d'un scénario ─────────────────────────────────────────────────────

def compute_scenario(
    conso_mwh: pd.Series,
    vol_forward_mwh: pd.Series,
    cost_forward_eur: pd.Series,
    spot_price: pd.Series,
) -> pd.DataFrame:
    """
    Applique la formule de coût heure par heure.

    C_h = cost_forward_h + P_spot_h × (C_réelle_h − V_forward_h)

    Arguments :
        conso_mwh        : consommation réelle/prévue par heure (MWh)
        vol_forward_mwh  : volume couvert par achats à terme (MWh)
        cost_forward_eur : coût des achats à terme (€)
        spot_price       : prix spot prédit (€/MWh)

    Retourne un DataFrame avec les colonnes de résultat par heure.
    """
    ecart_mwh = conso_mwh - vol_forward_mwh
    cost_spot = spot_price * ecart_mwh
    cost_total = cost_forward_eur + cost_spot

    return pd.DataFrame({
        "conso_mwh": conso_mwh,
        "vol_forward_mwh": vol_forward_mwh,
        "cost_forward_eur": cost_forward_eur,
        "spot_price": spot_price,
        "ecart_mwh": ecart_mwh,
        "cost_spot_eur": cost_spot,
        "cost_total_eur": cost_total,
    })


# ── Moteur principal ─────────────────────────────────────────────────────────

@dataclass
class SimulationResult:
    """Résultat complet d'une simulation A vs B."""
    # Séries horaires
    scenario_a: pd.DataFrame          # scénario référence (hourly)
    scenario_b: pd.DataFrame          # scénario simulé (hourly)
    # Séries quotidiennes (pour graphiques)
    daily_a: pd.DataFrame
    daily_b: pd.DataFrame
    # KPIs globaux
    kpi_a: dict
    kpi_b: dict
    # Détail par achat simulé (mode individuel)
    individual_impacts: list[dict] = field(default_factory=list)


def run_simulation(
    consumption_hourly: pd.DataFrame,
    spot_prices_hourly: pd.Series,
    portfolio_hourly: pd.DataFrame,
    simulated_purchases: list[SimulatedPurchase],
    hourly_index: pd.DatetimeIndex,
    mode: Literal["individual", "cumulated"] = "cumulated",
) -> SimulationResult:
    """
    Exécute la simulation complète.

    Arguments :
        consumption_hourly : DataFrame avec colonne 'conso_mwh' indexé par datetime
        spot_prices_hourly : Series de prix spot par heure
        portfolio_hourly   : DataFrame avec 'vol_portfolio_mwh', 'cost_portfolio_eur'
        simulated_purchases: liste des achats simulés
        hourly_index       : index horaire de la période
        mode               : 'individual' ou 'cumulated'

    Retourne un SimulationResult.
    """
    conso = consumption_hourly["conso_mwh"].reindex(hourly_index, fill_value=0.0)
    spot = spot_prices_hourly.reindex(hourly_index, fill_value=0.0)
    vol_pf = portfolio_hourly["vol_portfolio_mwh"].reindex(hourly_index, fill_value=0.0)
    cost_pf = portfolio_hourly["cost_portfolio_eur"].reindex(hourly_index, fill_value=0.0)

    # ── Scénario A : portefeuille actuel seul ─────────────────────────
    scenario_a = compute_scenario(conso, vol_pf, cost_pf, spot)

    # ── Expansion des achats simulés ──────────────────────────────────
    sim_expansions = []
    for p in simulated_purchases:
        exp = expand_purchase_hourly(p, hourly_index)
        sim_expansions.append((p, exp))

    # ── Scénario B : portefeuille + achats simulés ────────────────────
    vol_sim_total = pd.Series(0.0, index=hourly_index)
    cost_sim_total = pd.Series(0.0, index=hourly_index)
    for _, exp in sim_expansions:
        vol_sim_total += exp["vol_sim_mwh"]
        cost_sim_total += exp["cost_sim_eur"]

    vol_b = vol_pf + vol_sim_total
    cost_b = cost_pf + cost_sim_total
    scenario_b = compute_scenario(conso, vol_b, cost_b, spot)

    # ── Agrégation quotidienne ────────────────────────────────────────
    daily_a = _aggregate_daily(scenario_a)
    daily_b = _aggregate_daily(scenario_b)

    # ── KPIs globaux ──────────────────────────────────────────────────
    kpi_a = _compute_kpis(scenario_a)
    kpi_b = _compute_kpis(scenario_b)

    # ── Impacts individuels (mode individuel) ─────────────────────────
    individual_impacts = []
    if mode == "individual":
        for purchase, exp in sim_expansions:
            vol_ind = vol_pf + exp["vol_sim_mwh"]
            cost_ind = cost_pf + exp["cost_sim_eur"]
            sc_ind = compute_scenario(conso, vol_ind, cost_ind, spot)
            kpi_ind = _compute_kpis(sc_ind)

            individual_impacts.append({
                "purchase": purchase,
                "kpi": kpi_ind,
                "delta_prix_mwh": kpi_ind["prix_moyen_mwh"] - kpi_a["prix_moyen_mwh"],
                "delta_cout_total": kpi_ind["cout_total_eur"] - kpi_a["cout_total_eur"],
                "vol_sim_mwh": float(exp["vol_sim_mwh"].sum()),
            })

    return SimulationResult(
        scenario_a=scenario_a,
        scenario_b=scenario_b,
        daily_a=daily_a,
        daily_b=daily_b,
        kpi_a=kpi_a,
        kpi_b=kpi_b,
        individual_impacts=individual_impacts,
    )


# ── Fonctions internes ────────────────────────────────────────────────────────

def _aggregate_daily(scenario: pd.DataFrame) -> pd.DataFrame:
    """Agrège un scénario horaire en totaux quotidiens."""
    df = scenario.copy()
    df["date"] = df.index.date
    return df.groupby("date").agg(
        conso_mwh=("conso_mwh", "sum"),
        vol_forward_mwh=("vol_forward_mwh", "sum"),
        cost_total_eur=("cost_total_eur", "sum"),
        cost_spot_eur=("cost_spot_eur", "sum"),
        cost_forward_eur=("cost_forward_eur", "sum"),
        ecart_mwh=("ecart_mwh", "sum"),
    ).reset_index()


def _compute_kpis(scenario: pd.DataFrame) -> dict:
    """Calcule les KPIs agrégés d'un scénario."""
    conso_total = scenario["conso_mwh"].sum()
    vol_forward_total = scenario["vol_forward_mwh"].sum()
    cost_total = scenario["cost_total_eur"].sum()
    cost_forward = scenario["cost_forward_eur"].sum()
    cost_spot = scenario["cost_spot_eur"].sum()

    # Volume couvert au spot (= écart positif uniquement)
    ecart_pos = scenario["ecart_mwh"].clip(lower=0).sum()
    # Volume excédentaire vendu au spot (= écart négatif)
    ecart_neg = scenario["ecart_mwh"].clip(upper=0).sum()

    # Prix moyen pondéré du portefeuille terme
    prix_moyen_forward = cost_forward / vol_forward_total if vol_forward_total > 0 else 0.0

    return {
        "conso_total_mwh": float(conso_total),
        "vol_forward_mwh": float(vol_forward_total),
        "vol_spot_mwh": float(ecart_pos),
        "vol_excedent_mwh": float(abs(ecart_neg)),
        "pct_spot": float(ecart_pos / conso_total * 100) if conso_total > 0 else 0.0,
        "pct_forward": float(vol_forward_total / conso_total * 100) if conso_total > 0 else 0.0,
        "cout_total_eur": float(cost_total),
        "cout_forward_eur": float(cost_forward),
        "cout_spot_eur": float(cost_spot),
        "prix_moyen_mwh": float(cost_total / conso_total) if conso_total > 0 else 0.0,
        "prix_moyen_forward_mwh": float(prix_moyen_forward),
    }
