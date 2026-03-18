"""
Dashboard Streamlit du projet Prophet (version pédagogique).

Objectif : permettre à un étudiant de visualiser simplement :
- l'historique et les prévisions,
- la qualité du modèle (métriques MLflow),
- un scénario de coût énergie (base/peak).
"""

from __future__ import annotations

from pathlib import Path
import re

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# ── Chemins projet ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRED_DIR = DATA_DIR / "predictions"
PROCESSED_DIR = DATA_DIR / "processed"
SITES_FILE = DATA_DIR / "raw" / "sites" / "table_sites.csv"
PRICE_FILE = DATA_DIR / "raw" / "prix" / "prix_spot.csv"

# ── Constantes de conversion ──────────────────────────────────────────────────
W_TO_KWH = 1 / 1_000          # W (sur 1 h) → kWh
W_TO_MWH = 1 / 1_000_000      # W (sur 1 h) → MWh


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

        # Normaliser en kW (données en W)
        if "puissance_moy_heure_pred" in df.columns:
            df["puissance_kw"] = df["puissance_moy_heure_pred"] / 1_000
        elif "puissance_kw_pred" in df.columns:
            df["puissance_kw"] = df["puissance_kw_pred"]

        frames.append(df)

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["prm"] = out["prm"].astype(str)
    out["data_type"] = "Prévision"
    return out


@st.cache_data
def load_historical_data() -> pd.DataFrame:
    if not PROCESSED_DIR.exists():
        return pd.DataFrame()

    frames = []
    for filepath in sorted(PROCESSED_DIR.glob("data_processed_*.csv")):
        df = pd.read_csv(filepath)
        if "datetime" not in df.columns:
            continue

        df["datetime"] = pd.to_datetime(df["datetime"])

        if "puissance_moy_heure" not in df.columns:
            continue

        if "prm" not in df.columns:
            prm = _extract_prm_from_name(filepath.name)
            if prm:
                df["prm"] = prm

        # puissance_moy_heure est déjà en kW dans les fichiers processed
        df["puissance_kw"] = df["puissance_moy_heure"] /1000
        frames.append(df[["prm", "datetime", "puissance_kw"]])

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["prm"] = out["prm"].astype(str)
    out["data_type"] = "Historique"
    return out


@st.cache_data
def load_prices() -> pd.DataFrame:
    if not PRICE_FILE.exists():
        return pd.DataFrame()

    df = pd.read_csv(PRICE_FILE)

    if "date_deb" in df.columns:
        df["date_deb"] = pd.to_datetime(df["date_deb"])
    if "date_fin" in df.columns:
        df["date_fin"] = pd.to_datetime(df["date_fin"])

    df["prix_base"] = pd.to_numeric(df["prix_base"], errors="coerce")
    df["prix_peak"] = pd.to_numeric(df["prix_peak"], errors="coerce")

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
    totals = df.groupby("site_label", as_index=False)["puissance_kw"].sum()
    return px.pie(
        totals,
        names="site_label",
        values="puissance_kw",
        title="Consommation prévisionnelle par site (kWh)",
    )




def build_consumption_curve(df: pd.DataFrame, aggregate: bool = False) -> px.line:
    """Courbes de consommation.

    Si *aggregate* est True, on additionne toutes les données par datetime
    (et par data_type si la colonne existe) pour obtenir un total multi-sites.
    """
    plot_df = df.copy()

    if aggregate:
        group_cols = ["datetime", "data_type"] if "data_type" in plot_df.columns else ["datetime"]
        plot_df = plot_df.groupby(group_cols, as_index=False)["puissance_kw"].sum()
        if "data_type" in plot_df.columns:
            plot_df["legend"] = "Total - " + plot_df["data_type"]
        else:
            plot_df["legend"] = "Total"
        title = "Courbes de consommation totale — tous sites (kW)"
    else:
        if "data_type" in plot_df.columns:
            plot_df["legend"] = plot_df["site_label"] + " - " + plot_df["data_type"]
        else:
            plot_df["legend"] = plot_df["site_label"]
        title = "Courbes de consommation (kW)"

    fig = px.line(
        plot_df,
        x="datetime",
        y="puissance_kw",
        color="legend",
        title=title,
        labels={"puissance_kw": "Puissance (kW)", "datetime": "Date", "legend": "Série"},
    )
    height = max(400, 300 + len(plot_df) * 0.01)
    fig.update_layout(height=min(height, 800))
    return fig



def build_yearly_consumption_histogram(df: pd.DataFrame) -> px.bar:
    """Crée un histogramme des consommations par année et site."""
    plot_df = df.copy()
    plot_df["year"] = plot_df["datetime"].dt.year
    plot_df["year_str"] = plot_df["year"].astype(str)

    # Agréger par year et site_label
    yearly_data = plot_df.groupby(["year_str", "site_label"], as_index=False)["puissance_kw"].sum()
    yearly_data = yearly_data.rename(columns={"puissance_kw": "Consommation (kWh)"})

    fig = px.bar(
        yearly_data,
        x="year_str",
        y="Consommation (kWh)",
        color="site_label",
        barmode="group",
        title="Consommations annuelles par site",
        labels={"year_str": "Année", "site_label": "Site"},
    )
    fig.update_layout(height=400)
    return fig


def build_monthly_price_series(
    price_df: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    price_priority: list[str],
) -> pd.DataFrame:
    """Construit une série mensuelle de prix avec colonnes prix_base et prix_peak."""
    date_range = pd.date_range(start=start_date, end=end_date, freq="MS")
    monthly_df = pd.DataFrame({"month": date_range})

    # Chercher les prix pour chaque mois
    monthly_df["prix_base"] = monthly_df["month"].apply(
        lambda dt: price_for_datetimes(
            pd.Series([dt]), price_df, "prix_base", price_priority
        ).iloc[0]
    )
    monthly_df["prix_peak"] = monthly_df["month"].apply(
        lambda dt: price_for_datetimes(
            pd.Series([dt]), price_df, "prix_peak", price_priority
        ).iloc[0]
    )

    return monthly_df.dropna(subset=["prix_base", "prix_peak"], how="all")


def build_price_curve(df: pd.DataFrame, price_col: str, title: str, y_range: list = None) -> px.line:
    fig = px.line(
        df,
        x="month",
        y=price_col,
        markers=True,
        title=title,
    )
    height = max(300, 250 + len(df) * 15)
    fig.update_layout(height=height)
    if y_range:
        fig.update_yaxes(range=y_range)
    return fig


MLRUNS_DIR = BASE_DIR / "mlruns"


@st.cache_data
def load_mlflow_metrics(prm: str) -> dict | None:
    """Cherche dans mlruns le run correspondant au PRM et retourne ses métriques."""
    metric_names = ["val_mae", "val_rmse", "val_mape", "val_r2"]

    for exp_dir in MLRUNS_DIR.iterdir():
        if not exp_dir.is_dir() or exp_dir.name in (".trash", "models"):
            continue
        for run_dir in exp_dir.iterdir():
            if not run_dir.is_dir():
                continue
            prm_file = run_dir / "params" / "site_prm"
            if not prm_file.exists():
                continue
            stored_prm = prm_file.read_text().strip()
            if stored_prm != prm:
                continue
            # Run trouvé — lire les métriques
            metrics: dict = {}
            for metric in metric_names:
                mf = run_dir / "metrics" / metric
                if mf.exists():
                    try:
                        # Format MLflow : "timestamp value step"
                        last_line = mf.read_text().strip().splitlines()[-1]
                        metrics[metric] = float(last_line.split()[1])
                    except (IndexError, ValueError):
                        pass
            if metrics:
                return metrics
    return None


# ── Application ───────────────────────────────────────────────────────────────

st.set_page_config(
    layout="wide",
    page_title="Conso Energ Dashboard",
)

st.title("Dashboard previsions conso et prix")

sites_df = load_sites()
prices_df = load_prices()
preds_df = load_predictions()
hist_df = load_historical_data()

if preds_df.empty:
    st.warning("Aucune prediction disponible dans data/predictions.")
    st.stop()

if "puissance_kw" not in preds_df.columns:
    st.error("Colonne puissance_kw manquante dans les predictions.")
    st.stop()

preds_df = preds_df.merge(
    sites_df[["prm", "site_label"]],
    on="prm",
    how="left",
)
preds_df["site_label"] = preds_df["site_label"].fillna("PRM " + preds_df["prm"])

# Merge site_label sur l'historique aussi
if not hist_df.empty:
    hist_df = hist_df.merge(
        sites_df[["prm", "site_label"]],
        on="prm",
        how="left",
    )
    hist_df["site_label"] = hist_df["site_label"].fillna("PRM " + hist_df["prm"])

min_date_pred = preds_df["datetime"].min()
max_date_pred = preds_df["datetime"].max()

st.sidebar.header("Filtres")
site_options = sorted(preds_df["site_label"].unique())
selected_sites = st.sidebar.multiselect("Sites", site_options, default=site_options)

show_historical = st.sidebar.checkbox("Afficher l'historique", value=False)

# Plage de dates : si historique activé, partir du début de l'historique
if show_historical and not hist_df.empty:
    global_min = hist_df["datetime"].min()
else:
    global_min = min_date_pred

start_date = st.sidebar.date_input("Date debut", value=global_min.date())
end_date = st.sidebar.date_input("Date fin", value=max_date_pred.date())

# Filtrer les prédictions
mask_pred = (
    preds_df["site_label"].isin(selected_sites)
    & (preds_df["datetime"] >= pd.to_datetime(start_date))
    & (preds_df["datetime"] <= pd.to_datetime(end_date))
)
filtered = preds_df.loc[mask_pred].copy()

# Combinaison historique + prévisions
if show_historical and not hist_df.empty:
    mask_hist = (
        hist_df["site_label"].isin(selected_sites)
        & (hist_df["datetime"] >= pd.to_datetime(start_date))
        & (hist_df["datetime"] <= pd.to_datetime(end_date))
    )
    filtered_hist = hist_df.loc[mask_hist].copy()

    if not filtered_hist.empty:
        filtered = pd.concat([filtered, filtered_hist], ignore_index=True)

if filtered.empty:
    st.warning("Aucune donnee apres filtrage.")
    st.stop()


multi_site = len(selected_sites) > 1

if multi_site:
    st.subheader("Répartition de la consommation par site")
    st.plotly_chart(build_consumption_pie(filtered), use_container_width=True)
elif len(selected_sites) == 1:
    # Un seul site : afficher les métriques du modèle
    st.subheader("Qualité du modèle")
    single_prm = preds_df.loc[preds_df["site_label"] == selected_sites[0], "prm"].iloc[0]
    mlflow_metrics = load_mlflow_metrics(single_prm)

    if mlflow_metrics:
        m_cols = st.columns(4)
        mae  = mlflow_metrics.get("val_mae")
        rmse = mlflow_metrics.get("val_rmse")
        mape = mlflow_metrics.get("val_mape")
        r2   = mlflow_metrics.get("val_r2")

        m_cols[0].metric(
            label="MAE (W)",
            value=f"{mae:,.0f}" if mae is not None else "N/A",
            help="Mean Absolute Error — erreur absolue moyenne entre la prévision et la consommation réelle. Plus la valeur est basse, meilleur est le modèle.",
        )
        m_cols[1].metric(
            label="RMSE (W)",
            value=f"{rmse:,.0f}" if rmse is not None else "N/A",
            help="Root Mean Squared Error — pénalise davantage les grandes erreurs. Comparer au MAE : si RMSE >> MAE, il y a des pics d'erreur importants.",
        )
        m_cols[2].metric(
            label="MAPE (%)",
            value=f"{mape:.1f} %" if mape is not None else "N/A",
            help="Mean Absolute Percentage Error — erreur relative moyenne en %. Une valeur < 20 % est généralement considérée comme bonne pour la prévision énergétique.",
        )
        m_cols[3].metric(
            label="R²",
            value=f"{r2:.3f}" if r2 is not None else "N/A",
            help="Coefficient de détermination — mesure la part de la variance expliquée par le modèle. 1.0 = parfait, > 0.8 = bon, < 0.5 = à améliorer.",
        )

        with st.expander("ℹ️ Comment interpréter ces métriques ?"):
            st.markdown(
                """
| Métrique | Description | Idéal |
|---|---|---|
| **MAE** | Erreur absolue moyenne (en Watts). Représente l'écart typique entre la prédiction et la réalité. | La plus basse possible |
| **RMSE** | Erreur quadratique moyenne (en Watts). Amplifie les grandes erreurs : utile pour détecter des pics de mauvaise prédiction. | La plus basse possible |
| **MAPE** | Erreur relative moyenne (en %). Indépendante de l'échelle ; facilement interprétable. | < 20 %  |
| **R²** | Part de la variance de la consommation expliquée par le modèle. 1 = parfait. | > 0,80 |
                """
            )
    else:
        st.info("Aucune métrique MLflow trouvée pour ce site.")

st.subheader("Consommation dans le temps")
st.plotly_chart(build_consumption_curve(filtered, aggregate=multi_site), use_container_width=True)

if not filtered.empty:
    st.plotly_chart(build_yearly_consumption_histogram(filtered), use_container_width=True)

if prices_df.empty:
    st.warning("Aucune donnee de prix disponible.")
else:
    price_priority = ["mensuel", "trimestriel", "annuel"]
    monthly_prices = build_monthly_price_series(
        prices_df,
        pd.to_datetime(start_date),
        pd.to_datetime(end_date),
        price_priority,
    )

    st.subheader("Prix futur dans le temps")

    monthly_prices_long = monthly_prices.melt(
        id_vars="month",
        value_vars=["prix_base", "prix_peak"],
        var_name="type_prix",
        value_name="prix",
    )
    monthly_prices_long["type_prix"] = monthly_prices_long["type_prix"].map({
        "prix_base": "Base",
        "prix_peak": "Peak",
    })

    fig_prices = px.line(
        monthly_prices_long.dropna(subset=["prix"]),
        x="month",
        y="prix",
        color="type_prix",
        markers=True,
        title="Evolution prix spot base vs peak",
        labels={"month": "Mois", "prix": "Prix (EUR/MWh)", "type_prix": "Type"},
    )
    # Adapter hauteur en fonction du nombre de points
    height = max(300, 250 + len(monthly_prices) * 15)
    fig_prices.update_layout(height=height)
    st.plotly_chart(fig_prices, use_container_width=True)

st.divider()

st.subheader("Simulation achat base/peak")

sim_site = st.selectbox("Site pour la simulation", site_options, index=0)

sim_df = filtered[filtered["site_label"] == sim_site].copy()

if sim_df.empty:
    st.info("Selectionnez un site avec des donnees de prediction.")
    st.stop()

with st.expander("Parametres de simulation", expanded=True):
    base_volume = st.number_input("Volume base achete (kW)", min_value=0.0, value=500.0, step=10.0)
    peak_volume = st.number_input("Volume peak achete (kW)", min_value=0.0, value=200.0, step=10.0)
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
sim_df["price_peak"] = price_for_datetimes(sim_df["datetime"], prices_df, "prix_peak", priority)

sim_df["hour"] = sim_df["datetime"].dt.hour
sim_df["weekday"] = sim_df["datetime"].dt.weekday
is_peak = sim_df["hour"].between(peak_start, peak_end)
if not include_weekend:
    is_peak = is_peak & (sim_df["weekday"] < 5)

sim_df["is_peak"] = is_peak
sim_df["purchased_kw"] = base_volume + np.where(sim_df["is_peak"], peak_volume, 0.0)

# Prix en EUR/MWh, conso en kWh (1 kW × 1h = 1 kWh), division par 1000 pour passer kWh→MWh
sim_df["contract_cost_eur"] = (
    base_volume * sim_df["price_base"] / 1000.0
    + np.where(sim_df["is_peak"], peak_volume * sim_df["price_peak"] / 1000.0, 0.0)
)

sim_df["spot_price"] = np.where(sim_df["is_peak"], sim_df["price_peak"], sim_df["price_base"])

sim_df["spot_cost_eur"] = (
    (sim_df["puissance_kw"] - sim_df["purchased_kw"]) * sim_df["spot_price"] / 1000.0
)

sim_df["energy_cost_eur"] = sim_df["contract_cost_eur"] + sim_df["spot_cost_eur"]
sim_df["turpe_eur"] = sim_df["puissance_kw"] * turpe_kwh
sim_df["subtotal_eur"] = sim_df["energy_cost_eur"] + sim_df["turpe_eur"]
sim_df["taxes_eur"] = sim_df["subtotal_eur"] * tax_rate
sim_df["total_eur"] = sim_df["subtotal_eur"] + sim_df["taxes_eur"]

kpis = st.columns(4)

kpis[0].metric("Conso totale (kWh)", f"{sim_df['puissance_kw'].sum():,.0f}")
kpis[1].metric("Cout energie (EUR)", f"{sim_df['energy_cost_eur'].sum():,.0f}")
kpis[2].metric("Cout total (EUR)", f"{sim_df['total_eur'].sum():,.0f}")
kpis[3].metric("Prix moyen (EUR/MWh)", f"{(sim_df['total_eur'].sum() / (sim_df['puissance_kw'].sum() / 1000.0)):.2f}")

cost_cols = st.columns(2)

with cost_cols[0]:
    fig_cost = px.line(
        sim_df,
        x="datetime",
        y="total_eur",
        title="Cout horaire total",
    )
    # Adapter hauteur en fonction du nombre de points
    height = max(400, 300 + len(sim_df) * 0.01)
    fig_cost.update_layout(height=min(height, 800))
    st.plotly_chart(fig_cost, use_container_width=True)

with cost_cols[1]:
    sim_df["total_cum_eur"] = sim_df["total_eur"].cumsum()
    fig_cum = px.line(
        sim_df,
        x="datetime",
        y="total_cum_eur",
        title="Cout cumule",
    )
    # Adapter hauteur en fonction du nombre de points
    height = max(400, 300 + len(sim_df) * 0.01)
    fig_cum.update_layout(height=min(height, 800))
    st.plotly_chart(fig_cum, use_container_width=True)
