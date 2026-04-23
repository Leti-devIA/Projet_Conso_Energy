"""
Dashboard Streamlit — Prévisions consommation & prix énergie.

Structure attendue :
    data/
    ├── predictions/   *.csv  (datetime, prm, puissance_kw | puissance_kw_pred | puissance_moy_heure_pred)
    ├── processed/     data_processed_*.csv  (datetime, prm, puissance_moy_heure | puissance_kw)
    └── raw/
        ├── prix/      prix_spot.csv  (date_deb, date_fin, prix_base, prix_peak, type)
        └── sites/     table_sites.csv  (prm, ville, [id_site])

Logo : déposer logo.png à côté de ce script (facultatif).
Métriques MLflow : dossier mlruns/ à côté du script (facultatif).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import sqlite3
import time
import random
from pathlib import Path
from datetime import timedelta

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG & CHEMINS
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR      = Path(__file__).resolve().parent
DATA_DIR      = BASE_DIR / "data"
PRED_DIR      = DATA_DIR / "predictions"
PROCESSED_DIR = DATA_DIR / "processed"
SITES_FILE    = DATA_DIR / "raw" / "sites" / "table_sites.csv"
PRICE_FILE    = DATA_DIR / "raw" / "prix"  / "prix_spot.csv"
MLRUNS_DIR    = BASE_DIR / "mlruns"
USERS_DB_FILE = BASE_DIR / "users_demo.db"
LOGO_FILE     = BASE_DIR / "logo.png"

# URL de l'API d'entraînement (à configurer selon l'environnement)
API_TRAIN_URL = "http://localhost:8001"

C_PRIMARY   = "#222D41"
C_SECONDARY = "#D76C58"
C_TEXT      = "#222D41"
C_MUTED     = "#374158"
C_ACCENT    = "#7F5056"

PALETTE = ["#222D41", "#374158", "#7F5056", "#D76C58"]
PALETTE_DARK = [
    "#1F77B4",
    "#FFBB78",
    "#2CA02C",
    "#D62728",
    "#C5B0D5",
    "#8C564B",
    "#E377C2",
    "#7F7F7F",
    "#BCBD22",
    "#17BECF",
    "#AEC7E8",
    "#FF7F0E",
    "#98DF8A",
    "#FF9896",
    "#9467BD",
]

# ══════════════════════════════════════════════════════════════════════════════
# CSS PERSONNALISÉ
# ══════════════════════════════════════════════════════════════════════════════

def build_custom_css(dark_mode: bool = False) -> str:
    if dark_mode:
        colors = {
            "bg": "#0F172A",
            "surface": "#111B2E",
            "surface_alt": "#0E182A",
            "border": "#23324A",
            "text": "#E5E7EB",
            "muted": "#9CA3AF",
            "primary": "#DCE3EE",
            "primary_soft": "#1A2233",
            "secondary": "#D76C58",
            "sidebar": "#0C1423",
            "badge_bg": "#152238",
            "shadow": "0 8px 24px rgba(0, 0, 0, 0.30)",
        }
    else:
        colors = {
            "bg": "#F7F6F5",
            "surface": "#FFFFFF",
            "surface_alt": "#F6F3F2",
            "border": "#E7DFDD",
            "text": C_TEXT,
            "muted": C_MUTED,
            "primary": C_PRIMARY,
            "primary_soft": "#EEF1F5",
            "secondary": C_SECONDARY,
            "sidebar": "#F3F0EF",
            "badge_bg": "#F1ECEB",
            "shadow": "0 8px 24px rgba(16, 24, 40, 0.06)",
        }

    return """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --bg: """ + colors["bg"] + """;
        --surface: """ + colors["surface"] + """;
        --surface-alt: """ + colors["surface_alt"] + """;
        --border: """ + colors["border"] + """;
        --text: """ + colors["text"] + """;
        --muted: """ + colors["muted"] + """;
        --primary: """ + colors["primary"] + """;
        --primary-soft: """ + colors["primary_soft"] + """;
        --secondary: """ + colors["secondary"] + """;
        --sidebar: """ + colors["sidebar"] + """;
        --badge-bg: """ + colors["badge_bg"] + """;
        --shadow-soft: """ + colors["shadow"] + """;
    }

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; color: var(--text); font-size: 16px; }
    .stApp { background: var(--bg); }
    .main .block-container { padding-top: 1.1rem; padding-bottom: 2.2rem; max-width: 1500px; }

    .dash-header {
        display: flex; align-items: center; gap: 1rem;
        padding: 0.35rem 0 1.1rem 0;
        margin-bottom: 0.8rem;
        border-bottom: 1px solid var(--border);
    }
    .dash-header img { height: 42px; border-radius: 10px; }
    .dash-header h1 {
        margin: 0;
        font-size: 2.2rem;
        line-height: 1.05;
        font-weight: 800;
        letter-spacing: -0.03em;
        color: var(--primary);
    }
    .dash-header .header-kicker {
        font-size: 0.82rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        text-transform: uppercase;
        color: var(--secondary);
        margin-bottom: 0.25rem;
    }
    .dash-header .header-subtitle {
        font-size: 1rem;
        color: var(--muted);
        margin-top: 0.3rem;
    }
    .dash-header .header-meta {
        text-align: right;
        font-size: 0.9rem;
        color: var(--muted);
        line-height: 1.45;
    }

    .kpi-card {
        background: var(--surface); border: 1px solid var(--border); border-radius: 14px;
        padding: 1rem 1rem; text-align: center; box-shadow: var(--shadow-soft);
        transition: transform .16s ease, box-shadow .16s ease, border-color .16s ease;
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        min-height: 10rem;
    }
    .kpi-card:hover { transform: translateY(-2px); border-color: var(--primary); }
    .kpi-card .kpi-value { font-size: 1.65rem; font-weight: 700; color: var(--primary); margin: 0.3rem 0 0.15rem; line-height: 1.2; }
    .kpi-card .kpi-label { font-size: 0.85rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.08em; }
    .kpi-card .kpi-sub { font-size: 0.9rem; color: var(--muted); margin-top: 0.2rem; min-height: 1.1em; }

    .date-badge {
        display: inline-flex; align-items: center; gap: 0.35rem; border-radius: 999px;
        padding: 0.36rem 0.88rem; font-size: 0.92rem; font-weight: 500;
        border: 1px solid var(--border); background: var(--badge-bg); color: var(--text);
    }

    .admin-section {
        background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--primary);
        border-radius: 14px; padding: 1rem 1.05rem; margin-top: 0.9rem; box-shadow: var(--shadow-soft);
    }

    .section-title {
        font-size: 1.15rem; font-weight: 600; color: var(--text);
        border-bottom: 1px solid var(--border); padding-bottom: 0.45rem;
        margin-top: 1.5rem; margin-bottom: 0.95rem;
    }

    .info-subtle {
        background: var(--surface); border: 1px solid var(--border); border-left: 3px solid var(--secondary);
        border-radius: 10px; padding: 0.62rem 0.82rem; font-size: 0.96rem; color: var(--text);
    }

    section[data-testid="stSidebar"] {
        background: var(--sidebar);
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stDateInput label,
    section[data-testid="stSidebar"] .stCheckbox label,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] p {
        color: var(--text) !important;
    }

    .stTextInput > div > div > input,
    .stDateInput input,
    .stSelectbox > div > div,
    .stNumberInput input,
    textarea {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 10px !important;
        color: var(--text) !important;
    }

    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        border-radius: 10px !important;
        border: 1px solid var(--border) !important;
        background: var(--surface) !important;
        color: var(--text) !important;
        transition: all .15s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
        border-color: var(--primary) !important;
        color: var(--primary) !important;
        transform: translateY(-1px);
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background: var(--primary_soft) !important;
        border-color: var(--primary_soft) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 0.95rem !important;
        padding: 0.55rem 1.2rem !important;
        border-radius: 10px !important;
        letter-spacing: 0.03em !important;
        transition: all .18s ease !important;
    }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
        background: #B85A47 !important;
        border-color: #B85A47 !important;
        color: #ffffff !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 14px rgba(215, 108, 88, 0.35) !important;
    }
    /* Bouton désactivé (entraînement terminé) */
    .stButton > button[kind="primary"]:disabled {
        background: var(--border) !important;
        border-color: var(--border) !important;
        color: var(--muted) !important;
        cursor: not-allowed !important;
        transform: none !important;
        box-shadow: none !important;
    }

    div[data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.55rem 0.7rem;
        box-shadow: var(--shadow-soft);
    }

    div[data-testid="stPlotlyChart"] {
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 0.2rem;
        background: var(--surface);
        box-shadow: var(--shadow-soft);
    }

    hr {
        border: 0;
        height: 1px;
        background: var(--border);
        margin: 0.8rem 0;
    }

    /* Section block avec titre enrichi */
    .section-block { margin-top: 2.2rem; }
    .section-heading {
        display: flex; align-items: baseline; gap: 0.7rem;
        border-left: 4px solid var(--secondary);
        padding-left: 0.75rem; margin-bottom: 1.1rem;
    }
    .section-heading h2 {
        font-size: 1.35rem; font-weight: 700; margin: 0;
        color: var(--text); letter-spacing: -0.01em;
    }
    .section-heading .section-desc {
        font-size: 0.95rem; color: var(--muted);
    }

    /* Bandeau ré-entraînement */
    .retrain-banner {
        display: flex; align-items: flex-start;
        background: var(--surface);
        border: 1px solid var(--border);
        border-left: 4px solid var(--secondary);
        border-radius: 12px; padding: 0.85rem 1.1rem;
        margin-bottom: 0.8rem; box-shadow: var(--shadow-soft);
    }

    /* Delta KPI */
    .kpi-delta-up   { font-size: 0.94rem; font-weight: 600; color: #E57373; margin-top: 0.2rem; }
    .kpi-delta-down { font-size: 0.94rem; font-weight: 600; color: #81C784; margin-top: 0.2rem; }
</style>
"""


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _extract_prm_from_name(filename: str) -> str | None:
    match = re.search(r"(\d{8,})", filename)
    return match.group(1) if match else None


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_sites() -> pd.DataFrame:
    if not SITES_FILE.exists():
        return pd.DataFrame(columns=["prm", "ville", "id_site", "site_label"])
    try:
        df = pd.read_csv(SITES_FILE)
        df["prm"] = df["prm"].astype(str)
        if "ville"   not in df.columns: df["ville"]   = "Site inconnu"
        if "id_site" not in df.columns: df["id_site"] = ""
        # Déduplication : si plusieurs sites ont la même ville, ajouter un numéro
        _ville_count = df["ville"].astype(str).value_counts()
        _ville_seen: dict = {}
        labels = []
        for _, row in df.iterrows():
            v = str(row["ville"])
            if _ville_count[v] > 1:
                _ville_seen[v] = _ville_seen.get(v, 0) + 1
                labels.append(f"{v} #{_ville_seen[v]}")
            else:
                labels.append(v)
        df["site_label"] = labels
        return df
    except Exception as e:
        st.error(f"Erreur lecture sites : {e}")
        return pd.DataFrame(columns=["prm", "ville", "id_site", "site_label"])


@st.cache_data
def load_predictions() -> pd.DataFrame:
    if not PRED_DIR.exists():
        return pd.DataFrame()
    csv_files = sorted(PRED_DIR.glob("*.csv"))
    if not csv_files:
        return pd.DataFrame()

    frames = []
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath)
        except Exception:
            continue
        if "datetime" not in df.columns:
            continue
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"])

        if "prm" not in df.columns:
            prm = _extract_prm_from_name(filepath.name)
            if prm is None: continue
            df["prm"] = prm

        if "puissance_kw" not in df.columns:
            if "puissance_kw_pred" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance_kw_pred"], errors="coerce")
            elif "puissance_moy_heure_pred" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance_moy_heure_pred"], errors="coerce") / 1_000
            else:
                continue
        else:
            df["puissance_kw"] = pd.to_numeric(df["puissance_kw"], errors="coerce")

        frames.append(df[["prm", "datetime", "puissance_kw"]].copy())

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["prm"] = out["prm"].astype(str)
    out["data_type"] = "Prévision"
    sites_map = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_map, on="prm", how="left")
    out["site_label"] = out["site_label"].fillna("Site " + out["prm"].str[-4:])
    return out


@st.cache_data
def load_historical_data() -> pd.DataFrame:
    if not PROCESSED_DIR.exists():
        return pd.DataFrame()
    csv_files = sorted(PROCESSED_DIR.glob("data_processed_*.csv"))
    if not csv_files:
        csv_files = sorted(PROCESSED_DIR.glob("*.csv"))
    if not csv_files:
        return pd.DataFrame()

    frames = []
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath)
        except Exception:
            continue
        if "datetime" not in df.columns:
            continue
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"])

        if "prm" not in df.columns:
            prm = _extract_prm_from_name(filepath.name)
            if prm is None: continue
            df["prm"] = prm

        if "puissance_kw" not in df.columns:
            if "puissance_moy_heure" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance_moy_heure"], errors="coerce") / 1_000
            elif "puissance" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance"], errors="coerce") / 1_000
            else:
                continue
        else:
            df["puissance_kw"] = pd.to_numeric(df["puissance_kw"], errors="coerce")

        frames.append(df[["prm", "datetime", "puissance_kw"]].copy())

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames, ignore_index=True)
    out["prm"] = out["prm"].astype(str)
    out["data_type"] = "Historique"
    sites_map = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_map, on="prm", how="left")
    out["site_label"] = out["site_label"].fillna("Site " + out["prm"].str[-4:])
    return out


@st.cache_data
def load_prices() -> pd.DataFrame:
    if not PRICE_FILE.exists():
        return pd.DataFrame()
    try:
        df = pd.read_csv(PRICE_FILE)
        for col in ("date_deb", "date_fin"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")
        df["prix_base"] = pd.to_numeric(df.get("prix_base"), errors="coerce")
        df["prix_peak"] = pd.to_numeric(df.get("prix_peak"), errors="coerce")
        if "type" not in df.columns:
            df["type"] = "mensuel"
        return df
    except Exception as e:
        st.error(f"Erreur lecture prix : {e}")
        return pd.DataFrame()


@st.cache_data
def load_mlflow_metrics(prm: str) -> dict | None:
    if not MLRUNS_DIR.exists():
        return None
    for exp_dir in MLRUNS_DIR.iterdir():
        if not exp_dir.is_dir() or exp_dir.name in (".trash", "models"):
            continue
        for run_dir in exp_dir.iterdir():
            if not run_dir.is_dir():
                continue
            prm_file = run_dir / "params" / "site_prm"
            if not prm_file.exists() or prm_file.read_text().strip() != prm:
                continue
            metrics: dict = {}
            for metric in ["val_mae", "val_rmse", "val_mape", "val_r2"]:
                mf = run_dir / "metrics" / metric
                if mf.exists():
                    try:
                        last_line = mf.read_text().strip().splitlines()[-1]
                        metrics[metric] = float(last_line.split()[1])
                    except (IndexError, ValueError):
                        pass
            if metrics:
                return metrics
    return None


# ══════════════════════════════════════════════════════════════════════════════
# FONCTIONS GRAPHIQUES
# ══════════════════════════════════════════════════════════════════════════════

def price_for_datetimes(datetimes, price_df, price_col, priority):
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
            left_on="datetime", right_on="date_deb", direction="backward",
        )
        in_range = merged["datetime"] <= merged["date_fin"]
        assign_mask = in_range & result.loc[merged.index].isna()
        result.loc[merged.index[assign_mask]] = merged.loc[assign_mask, price_col].values
    return result


def _is_dark_mode() -> bool:
    return bool(st.session_state.get("dark_mode", True))


def _chart_palette() -> list[str]:
    return PALETTE_DARK if _is_dark_mode() else PALETTE


def _title_color() -> str:
    return "#F3F6FB" if _is_dark_mode() else C_TEXT


def _plotly_layout(
    fig: go.Figure,
    *,
    height: int,
    x_grid: bool = True,
    y_grid: bool = True,
    show_legend: bool = True,
) -> None:
    dark_mode = _is_dark_mode()
    plot_bg = "rgba(0,0,0,0)"
    paper_bg = "rgba(0,0,0,0)"
    grid_col = "#3A475F" if dark_mode else "#EAEFF5"
    font_col = "#F3F6FB" if dark_mode else C_TEXT
    muted_col = "#C9D3E4" if dark_mode else C_MUTED
    hover_bg = "#1B2435" if dark_mode else "#FFFFFF"

    fig.update_layout(
        height=height,
        margin=dict(t=46, b=18, l=12, r=12),
        hovermode="x unified",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(color=font_col, family="Inter", size=12),
        title_font=dict(color=font_col),
        legend=dict(orientation="h", y=-0.18, font=dict(size=11, color=muted_col)),
        hoverlabel=dict(bgcolor=hover_bg, bordercolor=grid_col, font=dict(color=font_col)),
        showlegend=show_legend,
    )
    fig.update_xaxes(
        showgrid=x_grid,
        gridcolor=grid_col,
        zeroline=False,
        linecolor=grid_col,
        tickfont=dict(color=muted_col),
        title=None,
    )
    fig.update_yaxes(
        showgrid=y_grid,
        gridcolor=grid_col,
        zeroline=False,
        linecolor=grid_col,
        tickfont=dict(color=muted_col),
        title=None,
    )


def fig_consumption_curve(df: pd.DataFrame, aggregate: bool = False) -> go.Figure:
    plot_df = df.copy()
    if aggregate:
        group_cols = ["datetime", "data_type"] if "data_type" in plot_df.columns else ["datetime"]
        plot_df = plot_df.groupby(group_cols, as_index=False)["puissance_kw"].sum()
        plot_df["legend"] = "Total - " + plot_df.get("data_type", "")
        title = "Consommation totale — tous sites"
    else:
        plot_df["legend"] = (
            plot_df["site_label"] + " — " + plot_df["data_type"]
            if "data_type" in plot_df.columns else plot_df["site_label"]
        )
        title = "Consommation dans le temps"

    fig = px.line(
        plot_df, x="datetime", y="puissance_kw", color="legend",
        title=title, color_discrete_sequence=_chart_palette(),
        labels={"puissance_kw": "Puissance (kW)", "datetime": "Date", "legend": ""},
    )
    fig.update_traces(line=dict(width=2.5))
    fig.update_layout(title=dict(font=dict(size=14, color=_title_color()), x=0))
    _plotly_layout(fig, height=400, x_grid=True, y_grid=True)
    return fig


def fig_yearly_bar(df: pd.DataFrame) -> go.Figure:
    """Histogramme comparatif annuel par site."""
    plot_df = df.copy()
    plot_df["year"] = plot_df["datetime"].dt.year.astype(str)
    yearly = (
        plot_df.groupby(["year", "site_label"], as_index=False)["puissance_kw"]
        .sum()
        .rename(columns={"puissance_kw": "Consommation (kWh)"})
    )
    fig = px.bar(
        yearly, x="year", y="Consommation (kWh)", color="site_label",
        barmode="group", title="Comparaison annuelle par site",
        color_discrete_sequence=_chart_palette(),
        labels={"year": "Année", "site_label": "Site"},
    )
    fig.update_layout(title=dict(font=dict(size=14, color=_title_color()), x=0), bargap=0.24, bargroupgap=0.08)
    _plotly_layout(fig, height=380, x_grid=False, y_grid=True)
    return fig


def fig_annual_total_bar(df: pd.DataFrame) -> go.Figure:
    """Barres de consommation totale (tous sites) par année, avec delta en annotation."""
    plot_df = df.copy()
    plot_df["year"] = plot_df["datetime"].dt.year
    yearly = (
        plot_df.groupby("year", as_index=False)["puissance_kw"]
        .sum()
        .sort_values("year")
    )
    yearly["conso_mwh"] = yearly["puissance_kw"] / 1_000
    # Calcul delta % vs année précédente
    yearly["delta_pct"] = yearly["conso_mwh"].pct_change() * 100

    pal = _chart_palette()
    # Couleurs selon la nature de l'année (historique / prévision / mixte)
    C_HIST = "#4FC3F7"  # bleu ciel  — historique
    C_PRED = "#FFB74D"  # ambre      — prévision
    C_MIX  = "#81C784"  # vert doux  — mixte

    if "data_type" in plot_df.columns:
        _nature = plot_df.groupby("year")["data_type"].apply(lambda s: set(s.unique()))
        def _pick_color(year):
            types = _nature.get(year, set())
            if "Historique" in types and "Prévision" in types:
                return C_MIX
            elif "Historique" in types:
                return C_HIST
            else:
                return C_PRED
        bar_colors = [_pick_color(y) for y in yearly["year"]]
    else:
        bar_colors = [pal[i % len(pal)] for i in range(len(yearly))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=yearly["year"].astype(str),
        y=yearly["conso_mwh"],
        marker_color=bar_colors,
        marker_line=dict(width=0),
        name="Conso totale",
        hovertemplate="<b>%{x}</b><br>%{y:,.0f} MWh<extra></extra>",
        showlegend=False,
    ))

    # Pseudo-traces pour légende couleur
    _seen_colors = set(bar_colors)
    for color, label in [(C_HIST, "Historique"), (C_PRED, "Prévision"), (C_MIX, "Mixte")]:
        if color in _seen_colors:
            fig.add_trace(go.Bar(x=[None], y=[None], marker_color=color, name=label, showlegend=True))

    # Annotations delta
    for _, row in yearly.iterrows():
        if pd.notna(row["delta_pct"]):
            sign  = "+" if row["delta_pct"] >= 0 else ""
            color = "#E57373" if row["delta_pct"] > 0 else "#81C784"
            fig.add_annotation(
                x=str(int(row["year"])),
                y=row["conso_mwh"],
                text=f"{sign}{row['delta_pct']:.1f} %",
                showarrow=False,
                yshift=12,
                font=dict(size=11, color=color, family="Inter"),
            )

    fig.update_layout(
        title=dict(text="Consommation totale par année (MWh)", font=dict(size=14, color=_title_color()), x=0),
        bargap=0.35,
    )
    _plotly_layout(fig, height=360, x_grid=False, y_grid=True)
    return fig


def fig_pie(df: pd.DataFrame) -> go.Figure:
    totals = df.groupby("site_label", as_index=False)["puissance_kw"].sum()
    fig = px.pie(
        totals, names="site_label", values="puissance_kw",
        title="Répartition par site (kWh)",
        color_discrete_sequence=_chart_palette(), hole=0.38,
    )
    fig.update_traces(textposition="inside", textinfo="percent", textfont=dict(color=_title_color()))
    fig.update_layout(title=dict(font=dict(size=14, color=_title_color()), x=0))
    _plotly_layout(fig, height=360, x_grid=False, y_grid=False)
    return fig


def fig_price_curve(monthly_prices: pd.DataFrame) -> go.Figure:
    monthly_long = monthly_prices.melt(
        id_vars="month", value_vars=["prix_base", "prix_peak"],
        var_name="type_prix", value_name="prix",
    )
    monthly_long["type_prix"] = monthly_long["type_prix"].map(
        {"prix_base": "Base", "prix_peak": "Peak"}
    )
    fig = px.line(
        monthly_long.dropna(subset=["prix"]),
        x="month", y="prix", color="type_prix", markers=True,
        title="Évolution prix spot — Base vs Peak",
        color_discrete_sequence=[_chart_palette()[0], _chart_palette()[3]],
        labels={"month": "Mois", "prix": "Prix (EUR/MWh)", "type_prix": ""},
    )
    fig.update_traces(line=dict(width=2.8), marker=dict(size=7, line=dict(width=1, color="#0F172A" if _is_dark_mode() else "#FFFFFF")))
    fig.update_layout(title=dict(font=dict(size=14, color=_title_color()), x=0))
    _plotly_layout(fig, height=340, x_grid=True, y_grid=True)
    return fig


def build_monthly_price_series(price_df, start_date, end_date, price_priority):
    date_range = pd.date_range(start=start_date, end=end_date, freq="MS")
    monthly_df = pd.DataFrame({"month": date_range})
    for col in ("prix_base", "prix_peak"):
        monthly_df[col] = monthly_df["month"].apply(
            lambda dt, c=col: price_for_datetimes(
                pd.Series([dt]), price_df, c, price_priority
            ).iloc[0]
        )
    return monthly_df.dropna(subset=["prix_base", "prix_peak"], how="all")


# ══════════════════════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ══════════════════════════════════════════════════════════════════════════════

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_users_db() -> None:
    with sqlite3.connect(USERS_DB_FILE) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT    UNIQUE NOT NULL,
                password_hash TEXT    NOT NULL,
                role          TEXT    NOT NULL CHECK(role IN ('admin', 'lecteur')),
                created_at    TEXT    DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.executemany(
            "INSERT OR IGNORE INTO users(username, password_hash, role) VALUES (?, ?, ?)",
            [
                ("admin",   hash_password("admin123"),   "admin"),
                ("lecteur", hash_password("lecteur123"), "lecteur"),
            ],
        )
        conn.commit()


def authenticate_user(username: str, password: str) -> dict | None:
    with sqlite3.connect(USERS_DB_FILE) as conn:
        row = conn.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()
    if not row:
        return None
    stored_username, stored_hash, role = row
    if not hmac.compare_digest(stored_hash, hash_password(password)):
        return None
    return {"username": stored_username, "role": role}


def create_user(username: str, password: str, role: str) -> tuple[bool, str]:
    username = username.strip()
    if not username:
        return False, "Le nom d'utilisateur est obligatoire."
    if len(password) < 6:
        return False, "Le mot de passe doit contenir au moins 6 caractères."
    if role not in {"admin", "lecteur"}:
        return False, "Rôle invalide."
    try:
        with sqlite3.connect(USERS_DB_FILE) as conn:
            conn.execute(
                "INSERT INTO users(username, password_hash, role) VALUES (?, ?, ?)",
                (username, hash_password(password), role),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return False, "Ce nom d'utilisateur existe déjà."
    return True, "Utilisateur créé avec succès."


# ══════════════════════════════════════════════════════════════════════════════
# SIMULATION ENTRAÎNEMENT
# ══════════════════════════════════════════════════════════════════════════════

def simulate_training(prm: str, old_metrics: dict | None) -> dict:
    """
    Simule un ré-entraînement et retourne des nouvelles métriques.
    En production, décommenter le bloc httpx ci-dessous et commenter la simulation.
    """
    # ── APPEL API RÉEL (décommenter en production) ────────────────────────────
    # import httpx
    # try:
    #     with httpx.Client(timeout=300.0) as client:
    #         resp = client.post(
    #             f"{API_TRAIN_URL}/train/{prm}",
    #             headers={"X-API-Key": "your-api-key"},
    #         )
    #     if resp.status_code == 200:
    #         return resp.json().get("metrics", {})
    #     else:
    #         st.error(f"Erreur API entraînement : {resp.status_code} — {resp.text}")
    #         return {}
    # except Exception as e:
    #     st.error(f"Impossible de joindre l'API d'entraînement : {e}")
    #     return {}
    # ─────────────────────────────────────────────────────────────────────────

    # ── SIMULATION ─────────────────────────────────────────────────────────────
    time.sleep(2)  # Simule le temps d'entraînement
    rng = random.Random(int(prm[-4:]) + int(time.time()) % 1000)

    base_mae  = (old_metrics or {}).get("val_mae",  9000)
    base_rmse = (old_metrics or {}).get("val_rmse", 13000)
    base_mape = (old_metrics or {}).get("val_mape", 14)
    base_r2   = (old_metrics or {}).get("val_r2",   0.90)

    # Amélioration aléatoire entre -5% et +15%
    improvement = rng.uniform(-0.05, 0.15)

    return {
        "val_mae":  round(base_mae  * (1 - improvement), 1),
        "val_rmse": round(base_rmse * (1 - improvement), 1),
        "val_mape": round(base_mape * (1 - improvement * 0.8), 2),
        "val_r2":   round(min(0.999, base_r2 + improvement * 0.05), 4),
    }


# ══════════════════════════════════════════════════════════════════════════════
# INITIALISATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(
    layout="wide",
    page_title="Énergie Dashboard",
    page_icon="⚡",
    initial_sidebar_state="expanded",
)
init_users_db()

# Session state
_defaults = {
    "authenticated": False, "username": "", "role": "",
    "training_prm": None, "training_new_metrics": None,
    "training_old_metrics": None, "training_accepted": False,
    "dark_mode": True,
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown(build_custom_css(st.session_state.dark_mode), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE DE LOGIN
# ══════════════════════════════════════════════════════════════════════════════

if not st.session_state.authenticated:
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        # Logo
        if LOGO_FILE.exists():
            st.image(str(LOGO_FILE), width=120)
        else:
            st.markdown(
                "<div style='font-size:3rem;text-align:center;margin-bottom:0.5rem'>⚡</div>",
                unsafe_allow_html=True,
            )

        st.markdown(
            f"<h2 style='text-align:center;color:{C_PRIMARY};margin-bottom:0.2rem'>Tableau de bord énergie</h2>",
            unsafe_allow_html=True,
        )
        st.markdown(
            f"<p style='text-align:center;color:{C_MUTED};font-size:0.88rem;margin-bottom:1.5rem'>"
            "Prévisions de consommation, prix spot et suivi des modèles</p>",
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username_input = st.text_input("Identifiant", placeholder="admin ou lecteur")
            password_input = st.text_input("Mot de passe", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Se connecter", use_container_width=True, type="primary")

        if submitted:
            user = authenticate_user(username_input.strip(), password_input)
            if user:
                st.session_state.authenticated = True
                st.session_state.username = user["username"]
                st.session_state.role = user["role"]
                st.rerun()
            else:
                st.error("Identifiants invalides")

        st.caption("Comptes de démonstration : `admin / admin123`  ·  `lecteur / lecteur123`")
    st.stop()


# ══════════════════════════════════════════════════════════════════════════════
# APPLICATION PRINCIPALE
# ══════════════════════════════════════════════════════════════════════════════

current_username = st.session_state.username
current_role     = st.session_state.role

# ── Chargement des données ────────────────────────────────────────────────────
_prog = st.progress(0, text="Chargement des données…")
sites_df  = load_sites();  _prog.progress(25)
prices_df = load_prices(); _prog.progress(50)
preds_df  = load_predictions(); _prog.progress(75)
hist_df   = load_historical_data(); _prog.progress(100)
_prog.empty()

# Garantir site_label
for _df in (preds_df, hist_df):
    if _df.empty: continue
    if "site_label" not in _df.columns:
        _df["site_label"] = "Site " + _df["prm"].astype(str).str[-4:]
    else:
        _df["site_label"] = _df["site_label"].fillna("Site " + _df["prm"].astype(str).str[-4:])

if preds_df.empty:
    st.error(
        f"Aucune prédiction chargée. Vérifiez le dossier `{PRED_DIR}` "
        "(colonnes attendues : `datetime`, `puissance_kw`)."
    )
    st.stop()

# Dates globales
global_min_hist = hist_df["datetime"].min() if not hist_df.empty else preds_df["datetime"].min()
global_max_pred = preds_df["datetime"].max()
global_max      = max(global_max_pred, hist_df["datetime"].max() if not hist_df.empty else global_max_pred)

# Dernière date historique
last_hist_date = hist_df["datetime"].max() if not hist_df.empty else None


# ── HEADER ────────────────────────────────────────────────────────────────────
logo_html = ""
if LOGO_FILE.exists():
    import base64
    logo_b64 = base64.b64encode(LOGO_FILE.read_bytes()).decode()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" />'
else:
    logo_html = '<div style="font-size:2.2rem;line-height:1">⚡</div>'

_hcol_title, _hcol_user = st.columns([5, 1])
with _hcol_title:
    st.markdown(f"""
    <div class="dash-header">
        {logo_html}
        <div>
            <div class="header-kicker">Pilotage énergétique</div>
            <h1>Tableau de bord énergie</h1>
            <div class="header-subtitle">Prévisions de consommation, prix spot et suivi des modèles</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
with _hcol_user:
    st.markdown(
        f"<div style='text-align:right;padding-top:0.6rem;font-size:0.82rem;color:var(--text)'>"
        f"<b>{current_username}</b> "
        f"<span style='color:var(--muted);font-size:0.75rem;text-transform:uppercase'>({current_role})</span></div>",
        unsafe_allow_html=True,
    )
    if st.button("⏏ Quitter", use_container_width=True, help="Se déconnecter"):
        for k in _defaults:
            st.session_state[k] = _defaults[k]
        st.rerun()


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    dark_mode_toggle = st.toggle("🌙 Thème sombre", value=st.session_state.dark_mode)
    if dark_mode_toggle != st.session_state.dark_mode:
        st.session_state.dark_mode = dark_mode_toggle
        st.rerun()

    st.markdown("---")
    st.markdown("### 🔍 Filtres")

    # Site
    site_options = sorted(preds_df["site_label"].unique())
    selected_site_filter = st.selectbox(
        "Site",
        ["Tous les sites"] + site_options,
        index=0,
    )
    if selected_site_filter == "Tous les sites":
        selected_sites     = site_options
        all_sites_selected = True
    else:
        selected_sites     = [selected_site_filter]
        all_sites_selected = False

    # Historique
    show_historical = st.checkbox("Afficher l'historique", value=True)

    st.markdown("**Période**")

    # Génère des jalons mensuels entre global_min_hist et global_max
    _slider_dates: list[pd.Timestamp] = []
    _cur = global_min_hist.to_period("M").to_timestamp()
    _end_ts = global_max.to_period("M").to_timestamp()
    while _cur <= _end_ts:
        _slider_dates.append(_cur)
        _cur += pd.DateOffset(months=1)
    if not _slider_dates:
        _slider_dates = [global_min_hist, global_max]

    # Labels affichés sur le slider (format court)
    _slider_labels = [d.strftime("%b %Y") for d in _slider_dates]

    # Déduplication au cas où (dates identiques)
    _seen: set = set()
    _uniq_labels: list[str] = []
    for lbl in _slider_labels:
        if lbl not in _seen:
            _seen.add(lbl)
            _uniq_labels.append(lbl)
    _slider_labels = _uniq_labels
    _label_to_ts   = {d.strftime("%b %Y"): d for d in _slider_dates}

    _sel_start, _sel_end = st.select_slider(
        "Période",
        options=_slider_labels,
        value=(_slider_labels[0], _slider_labels[-1]),
        label_visibility="collapsed",
    )
    start_date = _label_to_ts[_sel_start].date()
    end_date   = (_label_to_ts[_sel_end] + pd.offsets.MonthEnd(0)).date()
    st.caption(f"Du **{_sel_start}** au **{_sel_end}**")

    # Gestion utilisateurs (admin)
    if current_role == "admin":
        st.markdown("---")
        with st.expander("👥 Gestion des utilisateurs"):
            with st.form("create_user_form", clear_on_submit=True):
                new_username = st.text_input("Nom d'utilisateur")
                new_password = st.text_input("Mot de passe", type="password")
                new_role     = st.selectbox("Rôle", ["admin", "lecteur"])
                if st.form_submit_button("Créer", use_container_width=True):
                    ok, msg = create_user(new_username, new_password, new_role)
                    (st.success if ok else st.error)(msg)


# ══════════════════════════════════════════════════════════════════════════════
# FILTRAGE
# ══════════════════════════════════════════════════════════════════════════════

def _date_mask(df: pd.DataFrame) -> pd.Series:
    return (
        df["site_label"].isin(selected_sites)
        & (df["datetime"] >= pd.to_datetime(start_date))
        & (df["datetime"] <= pd.to_datetime(end_date))
    )

filtered_pred = preds_df.loc[_date_mask(preds_df)].copy() if not preds_df.empty else pd.DataFrame()
filtered_hist = hist_df.loc[_date_mask(hist_df)].copy()   if not hist_df.empty  else pd.DataFrame()

# Assemblage selon checkbox (pour affichage courbe)
if show_historical and not filtered_hist.empty:
    filtered = pd.concat([filtered_pred, filtered_hist], ignore_index=True)
else:
    filtered = filtered_pred.copy()

if filtered.empty:
    st.warning("Aucune donnée sur la plage sélectionnée. Modifiez les filtres.")
    st.stop()

multi_site = len(selected_sites) > 1

# ── Dataframe dédupliqué filtré par PÉRIODE (pour graphiques KPI / barres)
if not filtered_hist.empty and not filtered_pred.empty:
    _hist_dtimes = set(filtered_hist["datetime"].dt.floor("h"))
    _pred_complement = filtered_pred[~filtered_pred["datetime"].dt.floor("h").isin(_hist_dtimes)]
    filtered_total = pd.concat([filtered_hist, _pred_complement], ignore_index=True)
elif not filtered_hist.empty:
    filtered_total = filtered_hist.copy()
else:
    filtered_total = filtered_pred.copy()

# ── Dataframe dédupliqué sur TOUTE la plage de données (sites sélectionnés, sans filtre période)
# Utilisé pour les comparaisons inter-annuelles cohérentes (KPI delta + graphique barres annuelles)
def _site_mask(df: pd.DataFrame) -> pd.Series:
    return df["site_label"].isin(selected_sites)

_all_hist = hist_df.loc[_site_mask(hist_df)].copy() if not hist_df.empty else pd.DataFrame()
_all_pred = preds_df.loc[_site_mask(preds_df)].copy() if not preds_df.empty else pd.DataFrame()

if not _all_hist.empty and not _all_pred.empty:
    _all_hist_dtimes = set(_all_hist["datetime"].dt.floor("h"))
    _all_pred_compl  = _all_pred[~_all_pred["datetime"].dt.floor("h").isin(_all_hist_dtimes)]
    all_years_total  = pd.concat([_all_hist, _all_pred_compl], ignore_index=True)
elif not _all_hist.empty:
    all_years_total = _all_hist.copy()
else:
    all_years_total = _all_pred.copy()


# ══════════════════════════════════════════════════════════════════════════════
# TOP KPIs GLOBAUX
# ══════════════════════════════════════════════════════════════════════════════

_this_year = pd.Timestamp.now().year
_last_year = _this_year - 1
_VOL_ACHETE_MWH = 2_850  # Volume contractuel fictif — à remplacer

# Consommation année en cours et N-1 depuis all_years_total (toute la plage, sans filtre période)
_conso_this_yr = all_years_total[all_years_total["datetime"].dt.year == _this_year]["puissance_kw"].sum()
_conso_last_yr = all_years_total[all_years_total["datetime"].dt.year == _last_year]["puissance_kw"].sum()
_conso_delta_pct = (_conso_this_yr - _conso_last_yr) / _conso_last_yr * 100 if _conso_last_yr > 0 else None

if _conso_delta_pct is not None:
    _d_sign = "↑" if _conso_delta_pct > 0 else "↓"
    _d_cls  = "kpi-delta-up" if _conso_delta_pct > 0 else "kpi-delta-down"
    _d_html = f'<div class="{_d_cls}">{_d_sign} {abs(_conso_delta_pct):.1f} % vs {_last_year}</div>'
else:
    _d_html = ""

_last_hist_str  = last_hist_date.strftime("%d %b %Y  %H:%M") if last_hist_date else "—"
_nb_sites_total = len(site_options)

kc1, kc2, kc3, kc4 = st.columns(4, gap="medium")
if multi_site:
    with kc1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Consommation totale {_this_year}</div>
            <div class="kpi-value">{_conso_this_yr/1000:,.0f} MWh</div>
            <div class="kpi-sub">historique réel + prévisions</div>
            {_d_html}
        </div>""", unsafe_allow_html=True)
    with kc2:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Dernière mesure historique</div>
            <div class="kpi-value">{_last_hist_str}</div>
            <div class="kpi-sub">dernière donnée reçue</div>
        </div>""", unsafe_allow_html=True)
    with kc3:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Volume acheté {_this_year}</div>
            <div class="kpi-value">{_VOL_ACHETE_MWH:,.0f} MWh</div>
            <div class="kpi-sub">données contractuelles (fictif)</div>
        </div>""", unsafe_allow_html=True)
    with kc4:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Sites suivis</div>
            <div class="kpi-value">{_nb_sites_total}</div>
            <div class="kpi-sub">points de livraison actifs</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:1.4rem'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# BANDEAU RÉ-ENTRAÎNEMENT (admin + site unique sélectionné)
# ══════════════════════════════════════════════════════════════════════════════

_show_retrain    = current_role == "admin" and not multi_site
chosen_prm       = preds_df.loc[preds_df["site_label"] == selected_sites[0], "prm"].iloc[0] if not multi_site else None
chosen_train_site = selected_sites[0] if not multi_site else None

if _show_retrain and chosen_prm:
    _already_trained = (
        st.session_state.training_new_metrics is not None
        and st.session_state.training_prm == chosen_prm
        and not st.session_state.training_accepted
    )
    _b_text, _b_btn = st.columns([4, 1])
    with _b_text:
        st.markdown(
            f"<div style='font-size:0.85rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.09em;color:var(--secondary);margin-bottom:0.18rem'>"
            f"Modèle IA — {chosen_train_site}</div>"
            f"<div style='font-size:0.9rem;color:var(--muted)'>"
            f"Déclenchez un ré-entraînement pour mettre à jour les prédictions de ce site. "
            f"<b>Cette opération peut durer plusieurs minutes.</b></div>",
            unsafe_allow_html=True,
        )
    with _b_btn:
        _launch = st.button(
            "🔄 Ré-entraîner le modèle" if not _already_trained else "✅ Entraînement terminé",
            use_container_width=True,
            type="primary",
            disabled=_already_trained,
            key="btn_retrain_top",
        )
    st.markdown("</div>", unsafe_allow_html=True)

    if _launch:
        st.session_state.training_prm         = chosen_prm
        st.session_state.training_old_metrics = load_mlflow_metrics(chosen_prm)
        st.session_state.training_new_metrics = None
        st.session_state.training_accepted    = False
        st.warning("⏳ Entraînement lancé. Cette opération peut prendre **5 à 30 minutes** selon la taille des données. Veuillez ne pas fermer la page.", icon="⚠️")
        with st.spinner(f"Entraînement en cours pour {chosen_train_site}… Merci de patienter."):
            new_metrics = simulate_training(chosen_prm, st.session_state.training_old_metrics)
        st.session_state.training_new_metrics = new_metrics
        st.rerun()

    # Affichage des métriques comparées après entraînement
    if st.session_state.training_new_metrics is not None and st.session_state.training_old_metrics is not None:
        with st.expander("📊 Comparaison des métriques — Ancien vs Nouveau modèle", expanded=True):
            old_m = st.session_state.training_old_metrics
            new_m = st.session_state.training_new_metrics

            metrics_display = {
                "RMSE": ("val_rmse", "lower is better"),
                "MAE": ("val_mae", "lower is better"),
                "MAPE": ("val_mape", "lower is better"),
                "R² Score": ("val_r2", "higher is better"),
            }

            cols = st.columns(4)
            for idx, (label, (key, desc)) in enumerate(metrics_display.items()):
                with cols[idx]:
                    old_val = old_m.get(key, None)
                    new_val = new_m.get(key, None)

                    if old_val is not None and new_val is not None:
                        # Calcul du changement
                        if key == "val_r2":
                            # R² plus haut est mieux
                            change_pct = ((new_val - old_val) / abs(old_val) * 100) if old_val != 0 else 0
                            improved = new_val > old_val
                        else:
                            # MAE, RMSE, MAPE plus bas est mieux
                            change_pct = ((old_val - new_val) / old_val * 100) if old_val != 0 else 0
                            improved = new_val < old_val

                        # Affichage
                        color = "🟢" if improved else "🔴"
                        arrow = "↓" if key != "val_r2" else "↑"

                        st.markdown(
                            f"<div style='background-color:rgba(255,255,255,0.05);padding:1rem;border-radius:0.5rem;border-left:3px solid var(--secondary);'>"
                            f"<div style='font-size:0.85rem;color:var(--muted);margin-bottom:0.5rem'>{label}</div>"
                            f"<div style='display:flex;gap:0.5rem;align-items:baseline;margin-bottom:0.5rem'>"
                            f"<span style='font-size:1rem;color:var(--text)'>Ancien: <b>{old_val:.4f}</b></span>"
                            f"<span style='font-size:0.9rem;color:var(--muted)'>→</span>"
                            f"<span style='font-size:1rem;color:var(--text)'>Nouveau: <b>{new_val:.4f}</b></span>"
                            f"</div>"
                            f"<div style='font-size:0.9rem'>{color} {arrow} {abs(change_pct):.1f}% {'Amélioration' if improved else 'Dégradation'}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div style='background-color:rgba(255,255,255,0.05);padding:1rem;border-radius:0.5rem;'>"
                            f"<div style='font-size:0.85rem;color:var(--muted);margin-bottom:0.5rem'>{label}</div>"
                            f"<div style='color:var(--muted);font-size:0.9rem'>Données indisponibles</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )

            # Bouton pour accepter le nouveau modèle
            st.divider()
            _accept_col, _reject_col = st.columns(2)
            with _accept_col:
                if st.button("✅ Accepter le nouveau modèle", use_container_width=True, type="primary"):
                    st.session_state.training_accepted = True
                    st.success("✅ Nouveau modèle accepté et activé pour ce site !")
                    st.rerun()
            with _reject_col:
                if st.button("❌ Rejeter et conserver l'ancien", use_container_width=True):
                    st.session_state.training_new_metrics = None
                    st.session_state.training_old_metrics = None
                    st.info("Ancien modèle conservé")
                    st.rerun()


# Répartition par site EN PREMIER, puis courbe, puis totaux annuels, puis barres par site
if multi_site:
    _pc1, _pc2, _pc3 = st.columns([1, 2, 1])
    with _pc2:
        st.plotly_chart(fig_pie(filtered), use_container_width=True)
    st.plotly_chart(fig_consumption_curve(filtered, aggregate=True), use_container_width=True)
    st.plotly_chart(fig_annual_total_bar(all_years_total), use_container_width=True)
    st.plotly_chart(fig_yearly_bar(all_years_total), use_container_width=True)
else:
    st.plotly_chart(fig_consumption_curve(filtered, aggregate=False), use_container_width=True)
    st.plotly_chart(fig_annual_total_bar(all_years_total), use_container_width=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — PRIX SPOT
# ══════════════════════════════════════════════════════════════════════════════

if multi_site:
    st.markdown("""
    <div class="section-block">
        <div class="section-heading">
            <h2>💶 Prix spot</h2>
            <span class="section-desc">Évolution mensuelle Base et Peak sur la période sélectionnée</span>
        </div>
    </div>""", unsafe_allow_html=True)

    if prices_df.empty:
        st.markdown('<div class="info-subtle">⚠️ Aucune donnée de prix disponible.</div>', unsafe_allow_html=True)
    else:
        price_priority = ["mensuel", "trimestriel", "annuel"]
        monthly_prices = build_monthly_price_series(
            prices_df, pd.to_datetime(start_date), pd.to_datetime(end_date), price_priority
        )
        if not monthly_prices.empty:
            st.plotly_chart(fig_price_curve(monthly_prices), use_container_width=True)
        else:
            st.markdown('<div class="info-subtle">Aucun prix sur la plage sélectionnée.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SIMULATION ACHAT (admin + multi-sites uniquement)
# ══════════════════════════════════════════════════════════════════════════════

if multi_site:
    st.markdown("""
<div class="section-block">
    <div class="section-heading">
        <h2>🧮 Simulation achat</h2>
        <span class="section-desc">Modélisation des coûts Base / Peak selon vos paramètres contractuels</span>
    </div>
</div>""", unsafe_allow_html=True)

    if current_role != "admin":
        st.markdown('<div class="info-subtle">🔒 Réservé aux administrateurs.</div>', unsafe_allow_html=True)
    elif not all_sites_selected:
        st.markdown('<div class="info-subtle">ℹ️ Sélectionnez « Tous les sites » pour accéder à la simulation.</div>', unsafe_allow_html=True)
    elif prices_df.empty:
        st.markdown('<div class="info-subtle">⚠️ Simulation impossible sans données de prix.</div>', unsafe_allow_html=True)
    else:
        sim_df = filtered.groupby("datetime", as_index=False)["puissance_kw"].sum()

    with st.expander("⚙️ Paramètres de simulation", expanded=False):
        c1, c2, c3 = st.columns(3)
        with c1:
            base_volume = st.number_input("Volume base acheté (kW)", min_value=0.0, value=500.0, step=10.0)
            peak_volume = st.number_input("Volume peak acheté (kW)", min_value=0.0, value=200.0, step=10.0)
        with c2:
            peak_start      = st.slider("Heure début peak", 0, 23, 8)
            peak_end        = st.slider("Heure fin peak",   0, 23, 20)
            include_weekend = st.checkbox("Inclure weekend en peak", value=False)
        with c3:
            turpe_kwh = st.number_input("TURPE (EUR/kWh)", min_value=0.0, value=0.0, step=0.001, format="%.3f")
            tax_rate  = st.number_input("Taxes (taux, ex: 0.20)", min_value=0.0, value=0.0, step=0.01, format="%.2f")

    priority = ["mensuel", "trimestriel", "annuel"]
    sim_df = sim_df.sort_values("datetime").reset_index(drop=True)
    sim_df["price_base"] = price_for_datetimes(sim_df["datetime"], prices_df, "prix_base", priority)
    sim_df["price_peak"] = price_for_datetimes(sim_df["datetime"], prices_df, "prix_peak", priority)

    is_peak = sim_df["datetime"].dt.hour.between(peak_start, peak_end)
    if not include_weekend:
        is_peak = is_peak & (sim_df["datetime"].dt.weekday < 5)

    sim_df["is_peak"]           = is_peak
    sim_df["purchased_kw"]      = base_volume + np.where(is_peak, peak_volume, 0.0)
    sim_df["contract_cost_eur"] = (
        base_volume * sim_df["price_base"] / 1_000
        + np.where(is_peak, peak_volume * sim_df["price_peak"] / 1_000, 0.0)
    )
    sim_df["spot_price"]      = np.where(is_peak, sim_df["price_peak"], sim_df["price_base"])
    sim_df["spot_cost_eur"]   = (sim_df["puissance_kw"] - sim_df["purchased_kw"]) * sim_df["spot_price"] / 1_000
    sim_df["energy_cost_eur"] = sim_df["contract_cost_eur"] + sim_df["spot_cost_eur"]
    sim_df["turpe_eur"]       = sim_df["puissance_kw"] * turpe_kwh
    sim_df["subtotal_eur"]    = sim_df["energy_cost_eur"] + sim_df["turpe_eur"]
    sim_df["taxes_eur"]       = sim_df["subtotal_eur"] * tax_rate
    sim_df["total_eur"]       = sim_df["subtotal_eur"] + sim_df["taxes_eur"]

    total_kwh  = sim_df["puissance_kw"].sum()
    energy_eur = sim_df["energy_cost_eur"].sum()
    total_eur  = sim_df["total_eur"].sum()
    avg_price  = total_eur / (total_kwh / 1_000) if total_kwh > 0 else 0.0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Conso totale (kWh)",   f"{total_kwh:,.0f}")
    k2.metric("Coût énergie (EUR)",   f"{energy_eur:,.0f}")
    k3.metric("Coût total (EUR)",     f"{total_eur:,.0f}")
    k4.metric("Prix moyen (EUR/MWh)", f"{avg_price:.2f}")

    sc1, sc2 = st.columns(2)
    with sc1:
        fig_cost = px.line(sim_df, x="datetime", y="total_eur", title="Coût horaire total",
                           color_discrete_sequence=[_chart_palette()[0]])
        fig_cost.update_traces(line=dict(width=2.8))
        fig_cost.update_layout(yaxis_title="EUR", title=dict(font=dict(size=14, color=_title_color()), x=0))
        _plotly_layout(fig_cost, height=340, x_grid=True, y_grid=True)
        st.plotly_chart(fig_cost, use_container_width=True)
    with sc2:
        sim_df["total_cum_eur"] = sim_df["total_eur"].cumsum()
        fig_cum = px.line(sim_df, x="datetime", y="total_cum_eur", title="Coût cumulé",
                          color_discrete_sequence=[_chart_palette()[2]])
        fig_cum.update_traces(line=dict(width=2.8))
        fig_cum.update_layout(yaxis_title="EUR", title=dict(font=dict(size=14, color=_title_color()), x=0))
        _plotly_layout(fig_cum, height=340, x_grid=True, y_grid=True)
        st.plotly_chart(fig_cum, use_container_width=True)
