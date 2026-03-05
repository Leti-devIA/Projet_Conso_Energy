from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRED_DIR = DATA_DIR / "predictions"
SITES_FILE = DATA_DIR / "raw" / "sites" / "table_sites.csv"
PRICE_FILE = BASE_DIR.parent / "Scraping_prix" / "prix_electricite.csv"
PRICE_FILE_FALLBACK = DATA_DIR / "raw" / "prix" / "prix_spot.csv"


@st.cache_data
def load_sites() -> pd.DataFrame:
    if not SITES_FILE.exists():
        return pd.DataFrame(columns=["prm", "ville", "id_site"])

    df = pd.read_csv(SITES_FILE)
    df["prm"] = df["prm"].astype(str)
    df["site_label"] = df["ville"].astype(str) + " (" + df["prm"] + ")"
    return df


def _extract_prm_from_name(filename: str) -> str | None:
    match = re.search(r"(\d{8,})", filename)
    return match.group(1) if match else None


@st.cache_data
def load_predictions() -> pd.DataFrame:
    if not PRED_DIR.exists():
        return pd.DataFrame()

    frames = []
    for filepath in sorted(PRED_DIR.glob("*.csv")):
        df = pd.read_csv(filepath)
        if "datetime" not in df.columns:
            continue

        df["datetime"] = pd.to_datetime(df["datetime"])
        if "prm" not in df.columns:
            prm = _extract_prm_from_name(filepath.name)
            if prm:
                df["prm"] = prm
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["prm"] = out["prm"].astype(str)
    return out


@st.cache_data
def load_prices() -> pd.DataFrame:
    price_path = PRICE_FILE if PRICE_FILE.exists() else PRICE_FILE_FALLBACK
    if not price_path.exists():
        return pd.DataFrame()

    df = pd.read_csv(price_path)

    if "date_deb" in df.columns:
        df["date_deb"] = pd.to_datetime(df["date_deb"])
    if "date_fin" in df.columns:
        df["date_fin"] = pd.to_datetime(df["date_fin"])

    if "prix_heures_pleines" not in df.columns:
        df["prix_heures_pleines"] = df.get("prix_base")

    df["prix_base"] = pd.to_numeric(df["prix_base"], errors="coerce")
    df["prix_heures_pleines"] = pd.to_numeric(df["prix_heures_pleines"], errors="coerce")

    if "type" not in df.columns:
        df["type"] = "mensuel"

    return df


def price_for_datetimes(
    datetimes: pd.Series,
    price_df: pd.DataFrame,
    price_col: str,
    priority: list[str],
) -> pd.Series:
    result = pd.Series(np.nan, index=datetimes.index)
    for price_type in priority:
        df = price_df[price_df["type"] == price_type].copy()
        df = df[df[price_col].notna()].sort_values("date_deb")
        if df.empty:
            continue

        tmp = pd.DataFrame({"datetime": datetimes})
        merged = pd.merge_asof(
            tmp.sort_values("datetime"),
            df[["date_deb", "date_fin", price_col]],
            left_on="datetime",
            right_on="date_deb",
            direction="backward",
        )

        in_range = merged["datetime"] <= merged["date_fin"]
        assign_mask = in_range & result.loc[merged.index].isna()
        result.loc[merged.index[assign_mask]] = merged.loc[assign_mask, price_col].values

    return result


def build_consumption_pie(df: pd.DataFrame) -> px.pie:
    totals = df.groupby("site_label", as_index=False)["puissance_kw_pred"].sum()
    return px.pie(
        totals,
        names="site_label",
        values="puissance_kw_pred",
        title="Consommation previsionnelle par site",
    )


def build_consumption_curve(df: pd.DataFrame) -> px.line:
    return px.line(
        df,
        x="datetime",
        y="puissance_kw_pred",
        color="site_label",
        title="Courbes de consommation previsionnelle",
    )


def build_price_curve(df: pd.DataFrame, price_col: str, title: str) -> px.line:
    return px.line(
        df.sort_values("date_deb"),
        x="date_deb",
        y=price_col,
        color="type",
        markers=True,
        title=title,
    )


st.set_page_config(page_title="Conso Energ Dashboard", layout="wide")

st.title("Dashboard previsions conso et prix")

sites_df = load_sites()
prices_df = load_prices()
preds_df = load_predictions()

if preds_df.empty:
    st.warning("Aucune prediction disponible dans data/predictions.")
    st.stop()

if "puissance_kw_pred" not in preds_df.columns:
    st.error("Colonne puissance_kw_pred manquante dans les predictions.")
    st.stop()

preds_df = preds_df.merge(
    sites_df[["prm", "site_label"]],
    on="prm",
    how="left",
)

preds_df["site_label"] = preds_df["site_label"].fillna("PRM " + preds_df["prm"])

min_date = preds_df["datetime"].min()
max_date = preds_df["datetime"].max()

st.sidebar.header("Filtres")
site_options = sorted(preds_df["site_label"].unique())
selected_sites = st.sidebar.multiselect("Sites", site_options, default=site_options)

start_date = st.sidebar.date_input("Date debut", value=min_date.date())
end_date = st.sidebar.date_input("Date fin", value=max_date.date())

price_types = sorted(prices_df["type"].dropna().unique()) if not prices_df.empty else []
selected_types = st.sidebar.multiselect(
    "Types de prix", price_types, default=price_types
)

mask = (
    preds_df["site_label"].isin(selected_sites)
    & (preds_df["datetime"] >= pd.to_datetime(start_date))
    & (preds_df["datetime"] <= pd.to_datetime(end_date))
)
filtered = preds_df.loc[mask].copy()

if filtered.empty:
    st.warning("Aucune donnee apres filtrage.")
    st.stop()

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Consommation par site")
    st.plotly_chart(build_consumption_pie(filtered), use_container_width=True)

with right_col:
    st.subheader("Consommation dans le temps")
    st.plotly_chart(build_consumption_curve(filtered), use_container_width=True)

if prices_df.empty:
    st.warning("Aucune donnee de prix disponible.")
else:
    price_view = prices_df.copy()
    if selected_types:
        price_view = price_view[price_view["type"].isin(selected_types)]

    st.subheader("Prix futur dans le temps")
    price_cols = st.columns(2)

    with price_cols[0]:
        st.plotly_chart(
            build_price_curve(price_view, "prix_base", "Evolution prix spot (base)"),
            use_container_width=True,
        )

    with price_cols[1]:
        st.plotly_chart(
            build_price_curve(price_view, "prix_heures_pleines", "Evolution prix peak"),
            use_container_width=True,
        )

st.divider()

st.subheader("Simulation achat base/peak")

sim_site = st.selectbox("Site pour la simulation", site_options, index=0)

sim_df = filtered[filtered["site_label"] == sim_site].copy()

if sim_df.empty:
    st.info("Selectionnez un site avec des donnees de prediction.")
    st.stop()

with st.expander("Parametres de simulation", expanded=True):
    base_volume = st.number_input("Volume base achete (kW)", min_value=0.0, value=50000.0, step=1000.0)
    peak_volume = st.number_input("Volume peak achete (kW)", min_value=0.0, value=20000.0, step=1000.0)
    peak_start = st.slider("Heure debut peak", min_value=0, max_value=23, value=8)
    peak_end = st.slider("Heure fin peak", min_value=0, max_value=23, value=20)
    include_weekend = st.checkbox("Inclure weekend en peak", value=False)

    turpe_kwh = st.number_input("TURPE (EUR/kWh)", min_value=0.0, value=0.0, step=0.001, format="%.3f")
    tax_rate = st.number_input("Taxes (taux, ex: 0.20)", min_value=0.0, value=0.0, step=0.01, format="%.2f")

if prices_df.empty:
    st.warning("Simulation impossible sans donnees de prix.")
    st.stop()

priority = ["mensuel", "trimestriel", "annuel"]

sim_df = sim_df.sort_values("datetime").reset_index(drop=True)

sim_df["price_base"] = price_for_datetimes(sim_df["datetime"], prices_df, "prix_base", priority)
sim_df["price_peak"] = price_for_datetimes(sim_df["datetime"], prices_df, "prix_heures_pleines", priority)

sim_df["hour"] = sim_df["datetime"].dt.hour
sim_df["weekday"] = sim_df["datetime"].dt.weekday
is_peak = sim_df["hour"].between(peak_start, peak_end)
if not include_weekend:
    is_peak = is_peak & (sim_df["weekday"] < 5)

sim_df["is_peak"] = is_peak
sim_df["purchased_kw"] = base_volume + np.where(sim_df["is_peak"], peak_volume, 0.0)

sim_df["contract_cost_eur"] = (
    base_volume * sim_df["price_base"] / 1000.0
    + np.where(sim_df["is_peak"], peak_volume * sim_df["price_peak"] / 1000.0, 0.0)
)

sim_df["spot_price"] = np.where(sim_df["is_peak"], sim_df["price_peak"], sim_df["price_base"])

sim_df["spot_cost_eur"] = (
    (sim_df["puissance_kw_pred"] - sim_df["purchased_kw"]) * sim_df["spot_price"] / 1000.0
)

sim_df["energy_cost_eur"] = sim_df["contract_cost_eur"] + sim_df["spot_cost_eur"]
sim_df["turpe_eur"] = sim_df["puissance_kw_pred"] * turpe_kwh
sim_df["subtotal_eur"] = sim_df["energy_cost_eur"] + sim_df["turpe_eur"]
sim_df["taxes_eur"] = sim_df["subtotal_eur"] * tax_rate
sim_df["total_eur"] = sim_df["subtotal_eur"] + sim_df["taxes_eur"]

kpis = st.columns(4)

kpis[0].metric("Conso totale (kWh)", f"{sim_df['puissance_kw_pred'].sum():,.0f}")
kpis[1].metric("Cout energie (EUR)", f"{sim_df['energy_cost_eur'].sum():,.0f}")
kpis[2].metric("Cout total (EUR)", f"{sim_df['total_eur'].sum():,.0f}")
kpis[3].metric("Prix moyen (EUR/MWh)", f"{(sim_df['total_eur'].sum() / (sim_df['puissance_kw_pred'].sum() / 1000.0)):.2f}")

cost_cols = st.columns(2)

with cost_cols[0]:
    fig_cost = px.line(
        sim_df,
        x="datetime",
        y="total_eur",
        title="Cout horaire total",
    )
    st.plotly_chart(fig_cost, use_container_width=True)

with cost_cols[1]:
    sim_df["total_cum_eur"] = sim_df["total_eur"].cumsum()
    fig_cum = px.line(
        sim_df,
        x="datetime",
        y="total_cum_eur",
        title="Cout cumule",
    )
    st.plotly_chart(fig_cum, use_container_width=True)
