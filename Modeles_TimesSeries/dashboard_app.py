"""
Dashboard Streamlit - Prévisions consommation & prix énergie.

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
import io
import logging
import logging.handlers
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
import httpx
import os


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG APIs
# ══════════════════════════════════════════════════════════════════════════════

API_INFERENCE_URL = os.getenv("API_INFERENCE_URL", "http://localhost:8001")
API_DATACLEAN_URL = os.getenv("API_DATACLEAN_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-inference-key")

HIST_BATCH_CHUNK_SIZE = int(os.getenv("HIST_BATCH_CHUNK_SIZE", "4"))
HIST_BATCH_READ_TIMEOUT = float(os.getenv("HIST_BATCH_READ_TIMEOUT", "120"))


def _chunked(items: list[str], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG & CHEMINS
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR      = Path(__file__).resolve().parent
DATA_DIR      = BASE_DIR / "data"
PRED_DIR      = DATA_DIR / "predictions"
PROCESSED_DIR = DATA_DIR / "processed"
SITES_FILE    = DATA_DIR / "raw" / "sites" / "table_sites.csv"
PRICE_FILE    = DATA_DIR / "raw" / "prix"  / "prix_spot.csv"
ACHATS_DIR    = DATA_DIR / "raw" / "achats"
MLRUNS_DIR    = BASE_DIR / "mlruns"
USERS_DB_FILE = BASE_DIR / "users.db"

# ── Surveillance fraîcheur des données ────────────────────────────────────────
DATA_STALENESS_WARN_DAYS = 7    # alerte orange au-delà de 7 jours
DATA_STALENESS_CRIT_DAYS = 14   # alerte rouge au-delà de 14 jours

# ── Logger applicatif MLOps ───────────────────────────────────────────────────
_log_dir = BASE_DIR / "logs"
_log_dir.mkdir(exist_ok=True)
_mlops_logger = logging.getLogger("dashboard.mlops")
if not _mlops_logger.handlers:
    _fh = logging.handlers.RotatingFileHandler(
        _log_dir / "dashboard_mlops.log",
        maxBytes=500_000, backupCount=3, encoding="utf-8",
    )
    _fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    _mlops_logger.addHandler(_fh)
    _mlops_logger.setLevel(logging.INFO)
LOGO_FILE     = BASE_DIR / "data" / "logo 100x100.png"

# URL de l'API d'entraînement (à configurer selon l'environnement)
API_TRAIN_URL = "http://localhost:8001"

# Palette moderne indigo / teal
C_PRIMARY   = "#4F46E5"   # Indigo vif
C_SECONDARY = "#14B8A6"   # Teal
C_TEXT      = "#1E293B"   # Slate 800
C_MUTED     = "#64748B"   # Slate 500
C_ACCENT    = "#8B5CF6"   # Violet

PALETTE = ["#818CF8", "#FACC15", "#50C87A", "#F87171", "#2DD4BF", "#FB923C", "#C084FC", "#F472B6", "#38BDF8", "#E879F9"]
PALETTE_DARK = [
    "#818CF8",   # Indigo clair       (1)
    "#FACC15",   # Jaune vif          (2)
    "#50C87A",   # Vert menthe        (3) — mix indigo + jaune
    "#F87171",   # Rouge doux         (4)
    "#2DD4BF",   # Teal               (5)
    "#FB923C",   # Orange             (6)
    "#C084FC",   # Mauve              (7)
    "#F472B6",   # Rose               (8)
    "#38BDF8",   # Bleu ciel          (9)
    "#E879F9",   # Fuchsia            (10)
    "#4ADE80",   # Vert émeraude      (11)
    "#FF6B6B",   # Corail             (12)
    "#A3E635",   # Lime               (13)
    "#94A3B8",   # Gris bleuté        (14)
    "#FCD34D",   # Jaune doux         (15)
]
# ══════════════════════════════════════════════════════════════════════════════
# CSS PERSONNALISÉ
# ══════════════════════════════════════════════════════════════════════════════

def build_custom_css() -> str:
    colors = {
            "bg": "#0B1120",
            "surface": "#131C31",
            "surface_alt": "#0F172A",
            "surface_glass": "rgba(19, 28, 49, 0.75)",
            "border": "rgba(99, 102, 241, 0.12)",
            "border_hover": "rgba(99, 102, 241, 0.35)",
            "text": "#F1F5F9",
            "text_secondary": "#CBD5E1",
            "muted": "#94A3B8",
            "primary": "#818CF8",
            "primary_bg": "rgba(99, 102, 241, 0.12)",
            "primary_solid": "#4F46E5",
            "secondary": "#2DD4BF",
            "secondary_bg": "rgba(45, 212, 191, 0.10)",
            "accent": "#A78BFA",
            "sidebar": "#0D1526",
            "badge_bg": "rgba(99, 102, 241, 0.08)",
            "shadow": "0 4px 24px rgba(0, 0, 0, 0.25)",
            "shadow_hover": "0 8px 32px rgba(79, 70, 229, 0.15)",
            "gradient_1": "linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%)",
            "gradient_2": "linear-gradient(135deg, #0EA5E9 0%, #14B8A6 100%)",
            "gradient_3": "linear-gradient(135deg, #F59E0B 0%, #EF4444 100%)",
            "gradient_4": "linear-gradient(135deg, #8B5CF6 0%, #EC4899 100%)",
            "success": "#34D399",
            "danger": "#F87171",
        }

    return """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');

    :root {
        --bg: """ + colors["bg"] + """;
        --surface: """ + colors["surface"] + """;
        --surface-alt: """ + colors["surface_alt"] + """;
        --surface-glass: """ + colors["surface_glass"] + """;
        --border: """ + colors["border"] + """;
        --border-hover: """ + colors["border_hover"] + """;
        --text: """ + colors["text"] + """;
        --text-secondary: """ + colors["text_secondary"] + """;
        --muted: """ + colors["muted"] + """;
        --primary: """ + colors["primary"] + """;
        --primary-bg: """ + colors["primary_bg"] + """;
        --primary-solid: """ + colors["primary_solid"] + """;
        --secondary: """ + colors["secondary"] + """;
        --secondary-bg: """ + colors["secondary_bg"] + """;
        --accent: """ + colors["accent"] + """;
        --sidebar: """ + colors["sidebar"] + """;
        --badge-bg: """ + colors["badge_bg"] + """;
        --shadow-soft: """ + colors["shadow"] + """;
        --shadow-hover: """ + colors["shadow_hover"] + """;
        --gradient-1: """ + colors["gradient_1"] + """;
        --gradient-2: """ + colors["gradient_2"] + """;
        --gradient-3: """ + colors["gradient_3"] + """;
        --gradient-4: """ + colors["gradient_4"] + """;
        --success: """ + colors["success"] + """;
        --danger: """ + colors["danger"] + """;
    }

    /* ── Base ────────────────────────────────────── */
    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text);
        font-size: 15px;
        -webkit-font-smoothing: antialiased;
    }
    .stApp { background: var(--bg); }
    .main .block-container {
        padding-top: 6.6rem;
        padding-bottom: 2.5rem;
        max-width: 1440px;
    }

    /* ── Bandeau global en haut de fenêtre ───────── */
    .global-top-banner {
        top: 0;
        left: 0;
        right: 0;
        z-index: 999999 !important;
        pointer-events: none;
        margin-bottom: 1.4rem;
        background: var(--surface-glass);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border-bottom: 1px solid var(--border);
        box-shadow: var(--shadow-soft);
    }
    .global-top-banner * {
        pointer-events: none;
    }
    .global-top-banner-inner {
        display: flex;
        align-items: center;
        gap: 1rem;
        padding: 0.75rem 1.25rem;
    }
    .global-top-banner img {
        height: 48px;
        border-radius: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.12);
    }
    .global-top-banner h1 {
        margin: 0;
        font-size: 1.75rem;
        line-height: 1.15;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: var(--gradient-1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .global-top-banner .header-kicker {
        font-size: 2rem;
        font-weight: 700;
        letter-spacing: 0.15em;
        text-transform: uppercase;
        color: var(--secondary);
        margin-bottom: 0.15rem;
    }
    .global-top-banner .header-subtitle {
        font-size: 1.2rem;
        color: var(--muted);
        margin-top: 0.1rem;
    }

    /* ── KPI Cards ───────────────────────────────── */
    .kpi-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.25rem 1rem;
        text-align: center;
        box-shadow: var(--shadow-soft);
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 11.2rem;
        position: relative;
        overflow: hidden;
    }
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--gradient-1);
        border-radius: 16px 16px 0 0;
        opacity: 0;
        transition: opacity 0.2s ease;
    }
    .kpi-card:hover {
        transform: translateY(-3px);
        border-color: var(--border-hover);
        box-shadow: var(--shadow-hover);
    }
    .kpi-card:hover::before { opacity: 1; }
    .kpi-card .kpi-icon {
        font-size: 1.4rem;
        margin-bottom: 0.3rem;
        opacity: 0.8;
    }
    .kpi-card .kpi-value {
        font-size: clamp(1.05rem, 1.1vw, 1.6rem);
        font-weight: 700;
        background: var(--gradient-1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin: 0.25rem 0 0.1rem;
        line-height: 1.2;
        min-height: 2.4em;
        display: flex;
        align-items: center;
        justify-content: center;
        text-align: center;
        width: 100%;
        overflow-wrap: anywhere;
    }
    .kpi-card .kpi-label {
        font-size: 1rem;
        color: var(--muted);
        text-transform: uppercase;
        letter-spacing: 0.1em;
        font-weight: 600;
    }
    .kpi-card .kpi-sub {
        font-size: 0.78rem;
        color: var(--muted);
        margin-top: 0.15rem;
        min-height: 1em;
    }

    /* Variantes de KPI card par gradient */
    .kpi-card.kpi-teal .kpi-value {
        background: var(--gradient-2);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .kpi-card.kpi-teal:hover::before,
    .kpi-card.kpi-teal::before { background: var(--gradient-2); }

    .kpi-card.kpi-amber .kpi-value {
        background: var(--gradient-3);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .kpi-card.kpi-amber:hover::before,
    .kpi-card.kpi-amber::before { background: var(--gradient-3); }

    .kpi-card.kpi-violet .kpi-value {
        background: var(--gradient-4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .kpi-card.kpi-violet:hover::before,
    .kpi-card.kpi-violet::before { background: var(--gradient-4); }

    .date-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.35rem;
        border-radius: 999px;
        padding: 0.4rem 1rem;
        font-size: 0.82rem;
        font-weight: 500;
        border: 1px solid var(--border);
        background: var(--badge-bg);
        color: var(--text);
        backdrop-filter: blur(8px);
    }

    /* ── Sections ────────────────────────────────── */
    .admin-section {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1.2rem 1.2rem;
        margin-top: 0.9rem;
        box-shadow: var(--shadow-soft);
    }

    .section-title {
        font-size: 1.1rem;
        font-weight: 700;
        color: var(--text);
        border-bottom: 2px solid var(--border);
        padding-bottom: 0.5rem;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }

    .info-subtle {
        background: var(--primary-bg);
        border: 1px solid var(--border);
        border-left: 3px solid var(--secondary);
        border-radius: 12px;
        padding: 0.75rem 1rem;
        font-size: 0.9rem;
        color: var(--text);
        backdrop-filter: blur(8px);
    }

    /* ── Sidebar ─────────────────────────────────── */
    section[data-testid="stSidebar"] {
        background: var(--sidebar) !important;
        border-right: 1px solid var(--border);
    }
    section[data-testid="stSidebar"] > div:first-child {
        padding-top: 6.2rem;
    }
    [data-testid="collapsedControl"] {
        z-index: 1000001 !important;
    }
    section[data-testid="stSidebar"] .stSelectbox label,
    section[data-testid="stSidebar"] .stDateInput label,
    section[data-testid="stSidebar"] .stCheckbox label,
    section[data-testid="stSidebar"] .stMarkdown,
    section[data-testid="stSidebar"] p {
        color: var(--text) !important;
    }
    section[data-testid="stSidebar"] hr {
        background: var(--secondary) !important;
        opacity: 0.85;
    }
    .sidebar-filters-title {
        text-align: center;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0.01em;
        color: var(--text);
        padding: 0.45rem 0.65rem;
        margin: 0rem 0 0.75rem 0;

    }
    .sidebar-field-label {
        font-size: 1rem;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
        color: var(--text-secondary);
        margin: 0.5rem 0 1rem 0;

    /* ── Inputs ──────────────────────────────────── */
    .stTextInput > div > div > input,
    .stDateInput input,
    .stSelectbox > div > div,
    .stNumberInput input,
    textarea {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: 12px !important;
        color: var(--text) !important;
        transition: border-color 0.2s ease !important;
    }
    .stTextInput > div > div > input:focus,
    .stDateInput input:focus,
    .stNumberInput input:focus,
    textarea:focus {
        border-color: var(--primary) !important;
        box-shadow: 0 0 0 3px var(--primary-bg) !important;
    }

    /* ── Buttons ─────────────────────────────────── */
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        background: var(--surface) !important;
        color: var(--text) !important;
        font-weight: 500 !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
        border-color: var(--primary) !important;
        color: var(--primary) !important;
        transform: translateY(-1px);
        box-shadow: var(--shadow-hover) !important;
    }
    .stButton > button[kind="primary"], .stFormSubmitButton > button[kind="primary"] {
        background: var(--gradient-1) !important;
        border: none !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 0.92rem !important;
        padding: 0.6rem 1.4rem !important;
        border-radius: 12px !important;
        letter-spacing: 0.02em !important;
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        box-shadow: 0 2px 8px rgba(79, 70, 229, 0.25) !important;
    }
    .stButton > button[kind="primary"]:hover, .stFormSubmitButton > button[kind="primary"]:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 20px rgba(79, 70, 229, 0.35) !important;
    }
    .stButton > button[kind="primary"]:disabled {
        background: var(--surface-alt) !important;
        border: 1px solid var(--border) !important;
        color: var(--muted) !important;
        cursor: not-allowed !important;
        transform: none !important;
        box-shadow: none !important;
    }

    /* ── Metrics ─────────────────────────────────── */
    div[data-testid="stMetric"] {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 0.7rem 0.9rem;
        box-shadow: var(--shadow-soft);
        transition: all 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: var(--border-hover);
        box-shadow: var(--shadow-hover);
    }

    /* ── Charts ──────────────────────────────────── */
    div[data-testid="stPlotlyChart"] {
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 0.4rem;
        background: var(--surface);
        box-shadow: var(--shadow-soft);
        transition: all 0.2s ease;
    }
    div[data-testid="stPlotlyChart"]:hover {
        box-shadow: var(--shadow-hover);
    }

    /* ── Dividers ────────────────────────────────── */
    hr {
        border: 0;
        height: 1px;
        background: var(--border);
        margin: 1rem 0;
    }

    /* ── Section blocks ──────────────────────────── */
    .section-block { margin-top: 2.5rem; }
    .section-heading {
        display: flex;
        align-items: center;
        gap: 0.8rem;
        padding: 0.8rem 1rem;
        margin-bottom: 1.2rem;
        background: var(--primary-bg);
        border-radius: 12px;
        border: 1px solid var(--border);
    }
    .section-heading h2 {
        font-size: 1.2rem;
        font-weight: 700;
        margin: 0;
        color: var(--text);
        letter-spacing: -0.01em;
    }
    .section-heading .section-desc {
        font-size: 0.85rem;
        color: var(--muted);
    }

    /* ── Retrain banner ──────────────────────────── */
    .retrain-banner {
        display: flex;
        align-items: flex-start;
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 16px;
        padding: 1rem 1.2rem;
        margin-bottom: 1rem;
        box-shadow: var(--shadow-soft);
    }

    /* ── Delta KPI ───────────────────────────────── */
    .kpi-delta-up   { font-size: 0.88rem; font-weight: 600; color: var(--danger); margin-top: 0.2rem; }
    .kpi-delta-down { font-size: 0.88rem; font-weight: 600; color: var(--success); margin-top: 0.2rem; }

    /* ── Login page ──────────────────────────────── */
    .login-container {
        max-width: 400px;
        margin: 6vh auto;
        padding: 2.5rem 2rem;
        background: var(--surface-glass);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid var(--border);
        border-radius: 24px;
        box-shadow: var(--shadow-soft);
        text-align: center;
    }
    .login-logo {
        width: 100px;
        height: 100px;
        margin: 0 auto 1rem;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--gradient-1);
        border-radius: 18px;
        font-size: 2rem;
        box-shadow: 0 4px 16px rgba(79, 70, 229, 0.3);
    }
    .login-title {
        font-size: 3rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: var(--gradient-1);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        background-clip: text;
        margin-bottom: 0.25rem;
    }
    .login-subtitle {
        font-size: 2rem;
        color: var(--muted);
        margin-bottom: 1rem;
    }

    /* ── User badge (header) ─────────────────────── */
    .user-badge {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0.9rem;
        background: var(--primary-bg);
        border: 1px solid var(--border);
        border-radius: 999px;
        font-size: 0.82rem;
        font-weight: 500;
        color: var(--text);
    }
    .user-badge .user-role {
        font-size: 0.68rem;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        color: var(--primary);
        font-weight: 700;
    }

    /* ── Dataframes ──────────────────────────────── */
    .stDataFrame {
        border-radius: 12px !important;
        overflow: hidden;
    }

    /* ── Tabs ────────────────────────────────────── */
    .stTabs [data-baseweb="tab-list"] {
        background: var(--surface);
        border-radius: 12px;
        padding: 0.25rem;
        border: 1px solid var(--border);
        gap: 0.25rem;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px;
        padding: 0.5rem 1rem;
        font-weight: 500;
        font-size: 0.85rem;
        color: var(--muted);
    }
    .stTabs [aria-selected="true"] {
        background: var(--primary-bg) !important;
        color: var(--primary) !important;
        font-weight: 600;
    }

    /* ── Progress bar ────────────────────────────── */
    .stProgress > div > div > div > div {
        background: var(--gradient-1) !important;
    }

    /* ── Expander ────────────────────────────────── */
    .streamlit-expanderHeader {
        background: var(--surface) !important;
        border-radius: 12px !important;
        border: 1px solid var(--border) !important;
        font-weight: 600 !important;
    }
</style>
"""


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _extract_prm_from_name(filename: str) -> str | None:
    match = re.search(r"(\d{8,})", filename)
    return match.group(1) if match else None


def _set_data_source(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Attache la source des données au DataFrame."""
    df.attrs["data_source"] = source
    return df


def _get_data_source(df: pd.DataFrame, default: str = "Inconnue") -> str:
    """Retourne la source des données attachée au DataFrame."""
    return str(df.attrs.get("data_source", default))


def show_data_sources_indicator(sources: dict[str, str]) -> None:
    """Affiche un indicateur visuel des sources de données."""
    st.markdown("### Source des données")
    cols = st.columns(len(sources))
    for col, (label, source) in zip(cols, sources.items()):
        with col:
            st.markdown(
                f"""
                <div class="kpi-card" style="height:auto; min-height:7.6rem; padding:0.9rem 0.8rem;">
                    <div class="kpi-label" style="font-size:0.78rem;">{label}</div>
                    <div class="kpi-value" style="font-size:0.95rem; min-height:auto;">{source}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_sites() -> pd.DataFrame:
    """Charge les sites depuis l'API inference (/models/list) avec fallback CSV."""
    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{API_INFERENCE_URL}/models/list")

        if response.status_code == 200:
            data = response.json()
            models = data.get("models", [])

            if models:
                df = pd.DataFrame([{"prm": m["prm"]} for m in models])
                df["prm"] = df["prm"].astype(str)

                sites_csv_df = _load_sites_csv()
                if not sites_csv_df.empty:
                    df = df.merge(sites_csv_df[["prm", "ville", "id_site"]], on="prm", how="left")

                if "ville" in df.columns:
                    # Déduplication : si plusieurs sites ont la même ville, ajouter un numéro
                    _ville_count = df["ville"].fillna("Inconnu").astype(str).value_counts()
                    _ville_seen: dict = {}
                    labels = []
                    for _, row in df.iterrows():
                        v = str(row["ville"]) if pd.notna(row.get("ville")) else "Inconnu"
                        if _ville_count.get(v, 1) > 1:
                            _ville_seen[v] = _ville_seen.get(v, 0) + 1
                            labels.append(f"{v} #{_ville_seen[v]}")
                        else:
                            labels.append(v)
                    df["site_label"] = labels
                else:
                    df["ville"] = "Inconnu"
                    df["id_site"] = ""
                    df["site_label"] = "Site " + df["prm"]
                return _set_data_source(df, "API Inference")

    except Exception:
        pass

    return _load_sites_csv()


def _load_sites_csv() -> pd.DataFrame:
    """Fallback : charge les sites depuis le CSV local."""
    if not SITES_FILE.exists():
        return _set_data_source(
            pd.DataFrame(columns=["prm", "ville", "id_site", "site_label"]),
            "CSV local",
        )
    try:
        df = pd.read_csv(SITES_FILE)
        df["prm"] = df["prm"].astype(str)
        if "ville"   not in df.columns: df["ville"]   = "Site inconnu"
        if "id_site" not in df.columns: df["id_site"] = ""
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
        return _set_data_source(df, "CSV local")
    except Exception as e:
        st.error(f"Erreur lecture sites : {e}")
        return _set_data_source(
            pd.DataFrame(columns=["prm", "ville", "id_site", "site_label"]),
            "CSV local",
        )


@st.cache_data(ttl=60)
def load_predictions() -> pd.DataFrame:
    """Charge les prédictions depuis l'API inference avec fallback CSV."""
    try:
        sites_df = load_sites()
        if sites_df.empty:
            return _load_predictions_csv()

        frames = []
        for _, row in sites_df.iterrows():
            prm = str(row["prm"])
            try:
                with httpx.Client(timeout=120.0) as client:
                    pred_response = client.get(
                        f"{API_INFERENCE_URL}/predictions/prm/{prm}/latest",
                        headers={"X-API-Key": API_KEY}
                    )

                if pred_response.status_code == 200:
                    pred_data = pred_response.json()
                    series = pred_data.get("series", [])

                    if series:
                        df = pd.DataFrame(series)
                        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
                        df["prm"] = prm

                        if "puissance_kw" not in df.columns:
                            if "puissance_moy_heure_pred" in df.columns:
                                df["puissance_kw"] = df["puissance_moy_heure_pred"] / 1_000
                            elif "puissance_kw_pred" in df.columns:
                                df["puissance_kw"] = df["puissance_kw_pred"]

                        df = df[["prm", "datetime", "puissance_kw"]].copy()
                        frames.append(df)
            except Exception:
                continue

        if frames:
            out = pd.concat(frames, ignore_index=True)
            out["prm"] = out["prm"].astype(str)
            out["data_type"] = "Prévision"
            sites_map = load_sites()[["prm", "site_label"]]
            out = out.merge(sites_map, on="prm", how="left")
            out["site_label"] = out["site_label"].fillna("Site " + out["prm"].str[-4:])
            return _set_data_source(out, "API Inference")

    except Exception:
        pass

    return _load_predictions_csv()


def _load_predictions_csv() -> pd.DataFrame:
    """Fallback : charge les prédictions depuis les CSV locaux."""
    if not PRED_DIR.exists():
        return _set_data_source(pd.DataFrame(), "CSV local")
    csv_files = sorted(PRED_DIR.glob("*.csv"))
    if not csv_files:
        return _set_data_source(pd.DataFrame(), "CSV local")

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
        return _set_data_source(pd.DataFrame(), "CSV local")
    out = pd.concat(frames, ignore_index=True)
    out["prm"] = out["prm"].astype(str)
    out["data_type"] = "Prévision"
    sites_map = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_map, on="prm", how="left")
    out["site_label"] = out["site_label"].fillna("Site " + out["prm"].str[-4:])
    return _set_data_source(out, "CSV local")


@st.cache_data
def load_historical_data() -> pd.DataFrame:
    """Charge l'historique depuis l'API dataclean (batch) avec fallback CSV."""
    try:
        sites_df = load_sites()
        if sites_df.empty:
            return _load_historical_data_csv()

        prms = sites_df["prm"].astype(str).tolist()
        frames: list[pd.DataFrame] = []

        timeout = httpx.Timeout(connect=10.0, read=HIST_BATCH_READ_TIMEOUT, write=30.0, pool=10.0)

        with httpx.Client(timeout=timeout) as client:
            for prms_chunk in _chunked(prms, HIST_BATCH_CHUNK_SIZE):
                try:
                    resp = client.get(
                        f"{API_DATACLEAN_URL}/dataclean/allbyprm-json-batch",
                        params=[("prms", p) for p in prms_chunk],
                    )
                    if resp.status_code != 200:
                        continue
                    rows = resp.json().get("rows", [])
                    if rows:
                        frames.append(pd.DataFrame(rows))
                except Exception:
                    continue

        if not frames:
            return _load_historical_data_csv()

        out = pd.concat(frames, ignore_index=True)

        if "datetime" not in out.columns:
            return _load_historical_data_csv()
        out["datetime"] = pd.to_datetime(out["datetime"], errors="coerce")

        if "puissance_moy_heure" in out.columns:
            out["puissance_kw"] = out["puissance_moy_heure"] / 1_000
        elif "puissance" in out.columns:
            out["puissance_kw"] = out["puissance"] / 1_000
        elif "puissance_kw" not in out.columns:
            return _load_historical_data_csv()

        if "prm" not in out.columns:
            return _load_historical_data_csv()

        out = out[["prm", "datetime", "puissance_kw"]].copy()
        out["prm"] = out["prm"].astype(str)
        out["data_type"] = "Historique"
        sites_map = load_sites()[["prm", "site_label"]]
        out = out.merge(sites_map, on="prm", how="left")
        out["site_label"] = out["site_label"].fillna("Site " + out["prm"].str[-4:])
        return _set_data_source(out, "API Dataclean")

    except Exception:
        return _load_historical_data_csv()


def _load_historical_data_csv() -> pd.DataFrame:
    """Fallback : charge l'historique depuis data/raw/sites."""
    raw_sites_dir = DATA_DIR / "raw" / "sites"
    if not raw_sites_dir.exists():
        return _set_data_source(pd.DataFrame(), "CSV local")

    csv_files = sorted(raw_sites_dir.glob("dataclean_prm_*.csv"))
    if not csv_files:
        return _set_data_source(pd.DataFrame(), "CSV local")

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
            if prm is None:
                continue
            df["prm"] = prm

        if "puissance_kw" in df.columns:
            df["puissance_kw"] = pd.to_numeric(df["puissance_kw"], errors="coerce")
        elif "puissance_moy_heure" in df.columns:
            df["puissance_kw"] = pd.to_numeric(df["puissance_moy_heure"], errors="coerce") / 1_000
        elif "puissance" in df.columns:
            df["puissance_kw"] = pd.to_numeric(df["puissance"], errors="coerce") / 1_000
        else:
            continue

        frames.append(df[["prm", "datetime", "puissance_kw"]].copy())

    if not frames:
        return _set_data_source(pd.DataFrame(), "CSV local")

    out = pd.concat(frames, ignore_index=True)
    out["prm"] = out["prm"].astype(str)
    out["data_type"] = "Historique"
    sites_map = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_map, on="prm", how="left")
    out["site_label"] = out["site_label"].fillna("Site " + out["prm"].str[-4:])
    return _set_data_source(out, "CSV local")


@st.cache_data
def load_prices() -> pd.DataFrame:
    """Charge les prix depuis l'API Dataclean avec fallback CSV local."""

    def _normalize_prices_df(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        df = df.copy()
        df.columns = [str(c).strip() for c in df.columns]
        lower_map = {c.lower(): c for c in df.columns}

        rename_map = {}
        if "date_deb" not in df.columns and "date_debut" in lower_map:
            rename_map[lower_map["date_debut"]] = "date_deb"
        if "date_fin" not in df.columns and "date_fin" not in lower_map and "date_fin_periode" in lower_map:
            rename_map[lower_map["date_fin_periode"]] = "date_fin"
        if "prix_base" not in df.columns:
            for candidate in ("base", "prixbase", "price_base"):
                if candidate in lower_map:
                    rename_map[lower_map[candidate]] = "prix_base"
                    break
        if "prix_peak" not in df.columns:
            for candidate in ("peak", "prixpeak", "price_peak"):
                if candidate in lower_map:
                    rename_map[lower_map[candidate]] = "prix_peak"
                    break

        if rename_map:
            df = df.rename(columns=rename_map)

        for col in ("date_deb", "date_fin"):
            if col in df.columns:
                df[col] = pd.to_datetime(df[col], errors="coerce")

        if "prix_base" in df.columns:
            df["prix_base"] = pd.to_numeric(df["prix_base"], errors="coerce")
        else:
            df["prix_base"] = pd.Series(dtype=float)

        if "prix_peak" in df.columns:
            df["prix_peak"] = pd.to_numeric(df["prix_peak"], errors="coerce")
        else:
            df["prix_peak"] = pd.Series(dtype=float)

        if "type" not in df.columns:
            df["type"] = "mensuel"

        expected_cols = ["date_deb", "date_fin", "prix_base", "prix_peak", "type"]
        for col in expected_cols:
            if col not in df.columns:
                df[col] = np.nan

        return df[expected_cols].copy()

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.get(f"{API_DATACLEAN_URL}/dataclean/prixspot")

        if response.status_code == 200 and response.text.strip():
            csv_buffer = io.StringIO(response.text)
            api_df = pd.read_csv(csv_buffer, sep=None, engine="python")
            api_df = _normalize_prices_df(api_df)
            return _set_data_source(api_df, "API Dataclean")
    except Exception:
        pass

    if not PRICE_FILE.exists():
        return _set_data_source(pd.DataFrame(), "CSV local")

    try:
        df = pd.read_csv(PRICE_FILE)
        df = _normalize_prices_df(df)
        return _set_data_source(df, "CSV local")
    except Exception as e:
        st.error(f"Erreur lecture prix : {e}")
        return _set_data_source(pd.DataFrame(), "CSV local")


@st.cache_data
def load_achats() -> pd.DataFrame:
    """Charge tous les fichiers CSV ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv depuis data/raw/achats/."""
    if not ACHATS_DIR.exists():
        return _set_data_source(pd.DataFrame(), "CSV local")

    frames = []
    for f in sorted(ACHATS_DIR.glob("ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv")):
        try:
            df = pd.read_csv(f, sep=";")
            df.columns = [c.strip() for c in df.columns]
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return _set_data_source(pd.DataFrame(), "CSV local")

    out = pd.concat(frames, ignore_index=True)
    for date_col in ["DEB_PERIODE", "FIN_PERIODE", "DATE_ACHAT"]:
        if date_col in out.columns:
            out[date_col] = pd.to_datetime(out[date_col], errors="coerce")

    for num_col in ["VOLUME_TOTAL_PERIODE", "COUT_TOTAL_PERIODE", "PRIX_MOYEN"]:
        if num_col in out.columns:
            out[num_col] = pd.to_numeric(out[num_col], errors="coerce")

    return _set_data_source(out, "CSV local")


def purchased_volume_mwh_for_year(df: pd.DataFrame, year: int) -> float:
    """Calcule le volume acheté (MWh) attribuable à une année, avec prorata sur les périodes chevauchantes."""
    if df.empty or "VOLUME_TOTAL_PERIODE" not in df.columns:
        return 0.0

    total_mwh = 0.0
    year_start = pd.Timestamp(year=year, month=1, day=1)
    year_end = pd.Timestamp(year=year, month=12, day=31, hour=23, minute=59, second=59)

    if "DEB_PERIODE" in df.columns and "FIN_PERIODE" in df.columns:
        period_df = df.dropna(subset=["DEB_PERIODE", "FIN_PERIODE"]).copy()
        if not period_df.empty:
            overlap = (period_df["DEB_PERIODE"] <= year_end) & (period_df["FIN_PERIODE"] >= year_start)
            period_df = period_df.loc[overlap].copy()

            if not period_df.empty:
                start_clip = period_df["DEB_PERIODE"].clip(lower=year_start)
                end_clip = period_df["FIN_PERIODE"].clip(upper=year_end)
                overlap_days = (end_clip - start_clip).dt.total_seconds().div(86400).clip(lower=0)
                full_days = (period_df["FIN_PERIODE"] - period_df["DEB_PERIODE"]).dt.total_seconds().div(86400).clip(lower=1e-9)
                prorata = overlap_days / full_days
                total_mwh += (period_df["VOLUME_TOTAL_PERIODE"].fillna(0) * prorata).sum()

        missing_period = df[df["DEB_PERIODE"].isna() | df["FIN_PERIODE"].isna()].copy()
        if not missing_period.empty and "DATE_ACHAT" in missing_period.columns:
            total_mwh += missing_period[missing_period["DATE_ACHAT"].dt.year == year]["VOLUME_TOTAL_PERIODE"].fillna(0).sum()
    elif "DATE_ACHAT" in df.columns:
        total_mwh += df[df["DATE_ACHAT"].dt.year == year]["VOLUME_TOTAL_PERIODE"].fillna(0).sum()

    return float(total_mwh)


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


def check_negative_predictions(preds: pd.DataFrame) -> list[dict]:
    alerts: list[dict] = []
    if preds.empty or "puissance_kw" not in preds.columns:
        return alerts

    neg_df = preds[preds["puissance_kw"] < 0]
    if neg_df.empty:
        _mlops_logger.info(f"PRÉVISIONS NÉGATIVES | Aucune valeur négative sur {len(preds)} lignes")
        return alerts

    for site_label, group in neg_df.groupby("site_label"):
        nb        = len(group)
        min_val   = group["puissance_kw"].min()
        first_date = group["datetime"].min().strftime("%d/%m/%Y %H:%M")

        # ← Modifie le message ici ↓
        msg = (
            f"{site_label} - {nb} prévision(s) négative(s) "
            f"| min : {min_val:.2f} kW | première : {first_date}"
        )
        alerts.append({"level": "critique", "site": site_label, "message": msg})
        _mlops_logger.warning(f"CRITIQUE PRÉVISION NÉGATIVE | {msg}")

    return alerts


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


def _chart_palette() -> list[str]:
    return PALETTE_DARK


def _title_color() -> str:
    return "#F3F6FB"


def _plotly_layout(
    fig: go.Figure,
    *,
    height: int,
    x_grid: bool = True,
    y_grid: bool = True,
    show_legend: bool = True,
) -> None:
    plot_bg = "rgba(0,0,0,0)"
    paper_bg = "rgba(0,0,0,0)"
    grid_col = "rgba(99,102,241,0.08)"
    font_col = "#F1F5F9"
    muted_col = "#94A3B8"
    hover_bg = "#131C31"
    hover_border = "rgba(99,102,241,0.2)"

    fig.update_layout(
        height=height,
        margin=dict(t=50, b=20, l=16, r=16),
        hovermode="x unified",
        plot_bgcolor=plot_bg,
        paper_bgcolor=paper_bg,
        font=dict(color=font_col, family="Inter, -apple-system, sans-serif", size=12),
        title_font=dict(color=font_col, size=14, family="Inter"),
        legend=dict(
            orientation="h", y=-0.18,
            font=dict(size=11, color=muted_col),
            bgcolor="rgba(0,0,0,0)",
        ),
        hoverlabel=dict(
            bgcolor=hover_bg,
            bordercolor=hover_border,
            font=dict(color=font_col, size=12),
        ),
        showlegend=show_legend,
    )
    fig.update_xaxes(
        showgrid=x_grid,
        gridcolor=grid_col,
        zeroline=False,
        linecolor="rgba(0,0,0,0)",
        tickfont=dict(color=muted_col, size=11),
        title=None,
    )
    fig.update_yaxes(
        showgrid=y_grid,
        gridcolor=grid_col,
        zeroline=False,
        linecolor="rgba(0,0,0,0)",
        tickfont=dict(color=muted_col, size=11),
        title=None,
    )


def fig_consumption_curve(df: pd.DataFrame, aggregate: bool = False) -> go.Figure:
    plot_df = df.copy()
    if aggregate:
        palette = _chart_palette()
        if "data_type" in plot_df.columns:
            hist = (
                plot_df[plot_df["data_type"] == "Historique"]
                .groupby("datetime", as_index=False)["puissance_kw"]
                .sum()
                .rename(columns={"puissance_kw": "hist_kw"})
            )
            pred = (
                plot_df[plot_df["data_type"] == "Prévision"]
                .groupby("datetime", as_index=False)["puissance_kw"]
                .sum()
                .rename(columns={"puissance_kw": "pred_kw"})
            )

            merged = hist.merge(pred, on="datetime", how="outer").sort_values("datetime")
            overlap = merged.dropna(subset=["hist_kw", "pred_kw"]).copy()
            overlap["overlap_kw"] = overlap["hist_kw"] + overlap["pred_kw"]

            fig = go.Figure()
            if not hist.empty:
                fig.add_trace(go.Scatter(
                    x=hist["datetime"],
                    y=hist["hist_kw"],
                    mode="lines",
                    name="Total - Historique",
                    line=dict(color=palette[0], width=2.2),
                    hovertemplate="Historique<br>%{x|%d/%m/%Y %H:%M}<br>%{y:,.2f} kW<extra></extra>",
                ))
            if not pred.empty:
                fig.add_trace(go.Scatter(
                    x=pred["datetime"],
                    y=pred["pred_kw"],
                    mode="lines",
                    name="Total - Prévision",
                    line=dict(color=palette[1], width=2.2),
                    hovertemplate="Prévision<br>%{x|%d/%m/%Y %H:%M}<br>%{y:,.2f} kW<extra></extra>",
                ))
            if not overlap.empty:
                fig.add_trace(go.Scatter(
                    x=overlap["datetime"],
                    y=overlap["overlap_kw"],
                    mode="lines",
                    name="Total - Chevauchement",
                    line=dict(color=palette[2], width=2.6),
                    hovertemplate="Chevauchement (Hist+Prév)<br>%{x|%d/%m/%Y %H:%M}<br>%{y:,.2f} kW<extra></extra>",
                ))

            fig.update_layout(title=dict(text="Consommation totale - tous sites", font=dict(size=14, color=_title_color()), x=0))
            _plotly_layout(fig, height=520, x_grid=True, y_grid=True)
            return fig

        plot_df = plot_df.groupby(["datetime"], as_index=False)["puissance_kw"].sum()
        plot_df["legend"] = "Total"
        title = "Consommation totale - tous sites"
    else:
        plot_df["legend"] = (
            plot_df["site_label"] + " - " + plot_df["data_type"]
            if "data_type" in plot_df.columns else plot_df["site_label"]
        )
        title = "Consommation dans le temps"

    fig = px.line(
        plot_df, x="datetime", y="puissance_kw", color="legend",
        title=title, color_discrete_sequence=_chart_palette(),
        labels={"puissance_kw": "Puissance (kW)", "datetime": "Date", "legend": ""},
    )
    fig.update_traces(line=dict(width=2.2), opacity=0.9)
    fig.update_layout(title=dict(font=dict(size=14, color=_title_color()), x=0))
    _plotly_layout(fig, height=520, x_grid=True, y_grid=True)
    return fig


def fig_yearly_bar(df: pd.DataFrame) -> go.Figure:
    """Histogramme comparatif annuel par site."""
    plot_df = df.copy()
    if plot_df.empty:
        return go.Figure()

    # Conversion puissance -> énergie pour comparer correctement des pas temporels différents
    # (historique souvent en 5 min, prévisions souvent en 1 h)
    plot_df = plot_df.sort_values(["site_label", "datetime"]).copy()
    _delta_h = (
        plot_df.groupby("site_label")["datetime"]
        .diff()
        .dt.total_seconds()
        .div(3600)
    )
    _median_h = _delta_h.groupby(plot_df["site_label"]).transform("median")
    plot_df["interval_h"] = _delta_h.fillna(_median_h).fillna(1.0)
    plot_df["interval_h"] = plot_df["interval_h"].clip(lower=1 / 60, upper=24)
    plot_df["energy_kwh"] = plot_df["puissance_kw"] * plot_df["interval_h"]

    plot_df["year"] = plot_df["datetime"].dt.year.astype(str)
    yearly = (
        plot_df.groupby(["year", "site_label"], as_index=False)["energy_kwh"]
        .sum()
        .rename(columns={"energy_kwh": "Consommation (kWh)"})
    )
    fig = px.bar(
        yearly, x="year", y="Consommation (kWh)", color="site_label",
        barmode="group", title="Comparaison annuelle par site",
        color_discrete_sequence=_chart_palette(),
        labels={"year": "Année", "site_label": "Site"},
    )
    fig.update_layout(title=dict(font=dict(size=14, color=_title_color()), x=0), bargap=0.28, bargroupgap=0.1)
    _plotly_layout(fig, height=480, x_grid=False, y_grid=True)
    return fig


def fig_annual_total_bar(df: pd.DataFrame) -> go.Figure:
    """Barres de consommation totale (tous sites) par année, avec delta en annotation."""
    plot_df = df.copy()
    if plot_df.empty:
        return go.Figure()

    # Conversion puissance -> énergie pour éviter un biais d'échelle entre pas 5 min et pas horaire
    _grp = "prm" if "prm" in plot_df.columns else "site_label"
    plot_df = plot_df.sort_values([_grp, "datetime"]).copy()
    _delta_h = (
        plot_df.groupby(_grp)["datetime"]
        .diff()
        .dt.total_seconds()
        .div(3600)
    )
    _median_h = _delta_h.groupby(plot_df[_grp]).transform("median")
    plot_df["interval_h"] = _delta_h.fillna(_median_h).fillna(1.0)
    plot_df["interval_h"] = plot_df["interval_h"].clip(lower=1 / 60, upper=24)
    plot_df["energy_kwh"] = plot_df["puissance_kw"] * plot_df["interval_h"]

    plot_df["year"] = plot_df["datetime"].dt.year
    yearly = (
        plot_df.groupby("year", as_index=False)["energy_kwh"]
        .sum()
        .sort_values("year")
    )
    yearly["conso_mwh"] = yearly["energy_kwh"] / 1_000
    # Calcul delta % vs année précédente
    yearly["delta_pct"] = yearly["conso_mwh"].pct_change() * 100

    pal = _chart_palette()
    # Couleurs selon la nature de l'année (historique / prévision / mixte)
    C_HIST = "#818CF8"  # indigo clair - historique
    C_PRED = "#FACC15"  # jaune vif   - prévision
    C_MIX  = "#50C87A"  # vert menthe - mixte

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
            color = "#F87171" if row["delta_pct"] > 0 else "#34D399"
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
        bargap=0.4,
    )
    _plotly_layout(fig, height=480, x_grid=False, y_grid=True)
    return fig


def fig_pie(df: pd.DataFrame) -> go.Figure:
    totals = df.groupby("site_label", as_index=False)["puissance_kw"].sum()
    fig = px.pie(
        totals, names="site_label", values="puissance_kw",
        title="Répartition par site (kWh)",
        color_discrete_sequence=_chart_palette(), hole=0.38,
    )
    fig.update_traces(textposition="inside", textinfo="percent", textfont=dict(color="#FFFFFF", size=12))
    fig.update_layout(title=dict(font=dict(size=14, color=_title_color()), x=0))
    _plotly_layout(fig, height=380, x_grid=False, y_grid=False)
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
        title="Évolution prix futur - Base vs Peak",
        color_discrete_sequence=[_chart_palette()[0], _chart_palette()[3]],
        labels={"month": "Mois", "prix": "Prix (EUR/MWh)", "type_prix": ""},
    )
    fig.update_traces(line=dict(width=2.5), marker=dict(size=6, line=dict(width=1.5, color="#0B1120")))
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
                ("admin",   hash_password("passadmin"),   "admin"),
                ("lecteur", hash_password("passlecteur"), "lecteur"),
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
    #         st.error(f"Erreur API entraînement : {resp.status_code} - {resp.text}")
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
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

st.markdown(build_custom_css(), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE DE LOGIN
# ══════════════════════════════════════════════════════════════════════════════

if not st.session_state.authenticated:
    col_l, col_c, col_r = st.columns([1, 1.2, 1])
    with col_c:
        # Logo avec design moderne
        if LOGO_FILE.exists():
            st.image(str(LOGO_FILE), width=80)
        else:
            st.markdown(
                '<div class="login-logo">⚡</div>',
                unsafe_allow_html=True,
            )

        st.markdown(
            '<div class="login-title">Tableau de bord \u00e9nergie</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="login-subtitle">'
            "Pr\u00e9visions \u00b7 Prix \u00b7 Suivi mod\u00e8les IA</div>",
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            username_input = st.text_input("Identifiant", placeholder="identifiant")
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

# show_data_sources_indicator(
#     {
#         "Sites": _get_data_source(sites_df),
#         "Prix": _get_data_source(prices_df),
#         "Prévisions": _get_data_source(preds_df),
#         "Historique": _get_data_source(hist_df),
#     }
# )

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

# ── HEADER (bandeau global plein écran) ─────────────────────────────────────
logo_html = ""
if LOGO_FILE.exists():
    import base64
    logo_b64 = base64.b64encode(LOGO_FILE.read_bytes()).decode()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" />'
else:
    logo_html = '<div style="font-size:2.2rem;line-height:1">⚡</div>'

st.markdown(f"""
    <div class="global-top-banner">
      <div class="global-top-banner-inner">
        {logo_html}
        <div style="flex:1">
            <div class="header-kicker">Tableau de bord énergie</div>
            <div class="header-subtitle">Prévisions de consommation · Prix futur · Suivi des modèles</div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)

# Dates globales
global_min_hist = hist_df["datetime"].min() if not hist_df.empty else preds_df["datetime"].min()
global_max_pred = preds_df["datetime"].max()
global_max      = max(global_max_pred, hist_df["datetime"].max() if not hist_df.empty else global_max_pred)

# Dernière date historique
last_hist_date = hist_df["datetime"].max() if not hist_df.empty else None

# ── Vérification fraîcheur des données ───────────────────────────────────────
_now = pd.Timestamp.now()

def _check_freshness(label: str, last_date: pd.Timestamp | None) -> None:
    """Affiche une alerte Streamlit et journalise si la date est trop ancienne."""
    if last_date is None or pd.isna(last_date):
        st.warning(f"⚠️ **{label}** : aucune donnée disponible.", icon="⚠️")
        _mlops_logger.warning("DONNÉES MANQUANTES - %s : aucune date trouvée", label)
        return
    _age_days = (_now - last_date).days
    if _age_days >= DATA_STALENESS_CRIT_DAYS:
        st.error(
            f"**{label}** : dernière mesure le **{last_date.strftime('%d/%m/%Y %H:%M')}** "
            f"- {_age_days} jours d'écart. Les données ne sont pas à jour.",
            icon="🔴",
        )
        _mlops_logger.warning(
            "CRITIQUE - %s | dernière date=%s | âge=%d jours >= seuil critique %d j",
            label, last_date.strftime("%Y-%m-%d %H:%M"), _age_days, DATA_STALENESS_CRIT_DAYS,
        )
    elif _age_days >= DATA_STALENESS_WARN_DAYS:
        st.warning(
            f"**{label}** : dernière mesure le **{last_date.strftime('%d/%m/%Y %H:%M')}** "
            f"- {_age_days} jours d'écart. Vérifiez l'alimentation des données.",
            icon="⚠️",
        )
        _mlops_logger.warning(
            "WARNING - %s | dernière date=%s | âge=%d jours >= seuil alerte %d j",
            label, last_date.strftime("%Y-%m-%d %H:%M"), _age_days, DATA_STALENESS_WARN_DAYS,
        )
    else:
        _mlops_logger.info(
            "OK - %s | dernière date=%s | âge=%d jours",
            label, last_date.strftime("%Y-%m-%d %H:%M"), _age_days,
        )

_check_freshness("Données historiques", last_hist_date)
_check_freshness("Prévisions", global_max_pred if not preds_df.empty else None)

# ── Alerte prévisions négatives ───────────────────────────────────────────────
for _na in check_negative_predictions(preds_df):
    st.error(f"**Prévision négative détectée** - {_na['message']}", icon="🔴")


# ── SIDEBAR ───────────────────────────────────────────────────────────────────
with st.sidebar:
    # Badge + logout dans un seul bloc HTML
    st.markdown(
        f'''<div style="
            display:flex;
            align-items:center;
            justify-content:space-between;
            background:var(--primary-bg);
            border:1px solid var(--border);
            border-radius:12px;
            padding:0.5rem 0.75rem;
            margin-bottom:0.55rem;
            gap:0.5rem;
        ">
            <div style="display:flex;flex-direction:column;gap:0.1rem;flex:1">
                <span style="font-size:0.95rem;font-weight:600;color:var(--text)">{current_username}</span>
                <span style="font-size:0.82rem;color:var(--primary)">({current_role})</span>
            </div>
        </div>''',
        unsafe_allow_html=True,
    )

    # Bouton Streamlit réel, stylé pour matcher le bloc au-dessus
    if st.button(
        "⏻",
        use_container_width=True,
        key="logout_sidebar",
        type="tertiary",
    ):
        for k in _defaults:
            st.session_state[k] = _defaults[k]
        st.rerun()


    st.markdown("---")
    st.markdown('<div class="sidebar-filters-title">Filtres</div>', unsafe_allow_html=True)

    # Site
    st.markdown('<div class="sidebar-field-label">Site</div>', unsafe_allow_html=True)
    site_options = sorted(preds_df["site_label"].unique())
    selected_site_filter = st.selectbox(
        "Site",
        ["Tous les sites"] + site_options,
        index=0,
        label_visibility="collapsed",
    )
    if selected_site_filter == "Tous les sites":
        selected_sites     = site_options
        all_sites_selected = True
    else:
        selected_sites     = [selected_site_filter]
        all_sites_selected = False

    # Historique
    show_historical = st.checkbox("Afficher l'historique", value=True)

    st.markdown('<div class="sidebar-field-label">Période</div>', unsafe_allow_html=True)

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

    # Années complètes (multi-sélection)
    _all_years = list(range(int(global_min_hist.year), int(global_max.year) + 1))
    selected_years = st.multiselect(
        "Années complètes",
        options=_all_years,
        default=_all_years,
        help="Sélectionnez une ou plusieurs années complètes.",
    )
    if selected_years:
        _years_txt = ", ".join(str(y) for y in sorted(selected_years))
        st.caption(f"Années sélectionnées : **{_years_txt}**")
    else:
        st.caption("Années sélectionnées : **aucune**")

    # Gestion utilisateurs (admin)
    if current_role == "admin":
        st.markdown("---")
        with st.expander("Gestion des utilisateurs"):
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
        & (df["datetime"].dt.year.isin(selected_years))
    )

if not selected_years:
    st.warning("Sélectionnez au moins une année complète dans les filtres.")
    st.stop()

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
_VOL_ACHETE_MWH = purchased_volume_mwh_for_year(load_achats(), _this_year)

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

_last_hist_str  = last_hist_date.strftime("%d %b %Y  %H:%M") if last_hist_date else "-"
_nb_sites_total = len(site_options)

kc1, kc2, kc3, kc4 = st.columns(4, gap="medium")
if multi_site:
    with kc1:
        st.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">Conso totale {_this_year}</div>
            <div class="kpi-value">{_conso_this_yr/1000:,.0f} MWh</div>
            {_d_html}
        </div>""", unsafe_allow_html=True)
    with kc2:
        st.markdown(f"""
        <div class="kpi-card kpi-teal">
            <div class="kpi-label">Derni\u00e8re mesure</div>
            <div class="kpi-value">{_last_hist_str}</div>
        </div>""", unsafe_allow_html=True)
    with kc3:
        st.markdown(f"""
        <div class="kpi-card kpi-amber">
            <div class="kpi-label">Puissance achet\u00e9e {_this_year}</div>
            <div class="kpi-value">{_VOL_ACHETE_MWH:,.0f} MWh</div>
        </div>""", unsafe_allow_html=True)
    with kc4:
        st.markdown(f"""
        <div class="kpi-card kpi-violet">
            <div class="kpi-label">Sites</div>
            <div class="kpi-value">{_nb_sites_total}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:1.8rem'></div>", unsafe_allow_html=True)


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
            f"<div style='font-size:2rem;font-weight:700;text-transform:uppercase;"
            f"letter-spacing:0.12em;color:var(--secondary);margin-bottom:0.2rem'>"
            f"{chosen_train_site}</div>"
            f"<div style='font-size:0.88rem;color:var(--muted)'>"
            f"D\u00e9clenchez un r\u00e9-entra\u00eenement pour mettre \u00e0 jour les pr\u00e9dictions. "
            f"<b>Dur\u00e9e : quelques minutes.</b></div>",
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
        with st.expander("📊 Comparaison des métriques - Ancien vs Nouveau modèle", expanded=True):
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

                        _improve_txt = "Amélioration" if improved else "Dégradation"
                        st.markdown(
                            f"<div style='background:var(--primary-bg);padding:1rem;border-radius:12px;border:1px solid var(--border);'>"
                            f"<div style='font-size:0.75rem;color:var(--muted);margin-bottom:0.5rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:600'>{label}</div>"
                            f"<div style='display:flex;gap:0.5rem;align-items:baseline;margin-bottom:0.5rem'>"
                            f"<span style='font-size:0.92rem;color:var(--text)'>Ancien: <b>{old_val:.4f}</b></span>"
                            f"<span style='font-size:0.85rem;color:var(--muted)'>&rarr;</span>"
                            f"<span style='font-size:0.92rem;color:var(--text)'>Nouveau: <b>{new_val:.4f}</b></span>"
                            f"</div>"
                            f"<div style='font-size:0.85rem'>{color} {arrow} {abs(change_pct):.1f}% {_improve_txt}</div>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div style='background:var(--primary-bg);padding:1rem;border-radius:12px;border:1px solid var(--border);'>"
                            f"<div style='font-size:0.75rem;color:var(--muted);margin-bottom:0.5rem;text-transform:uppercase;letter-spacing:0.08em;font-weight:600'>{label}</div>"
                            "<div style='color:var(--muted);font-size:0.85rem'>Données indisponibles</div>"
                            "</div>",
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
# SECTION 2 - PRIX SPOT
# ══════════════════════════════════════════════════════════════════════════════

if multi_site:
    st.markdown("""
    <div class="section-block">
        <div class="section-heading">
            <h2>💶 Prix futur</h2>
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
        monthly_prices = monthly_prices.loc[
            monthly_prices["month"].dt.year.isin(selected_years)
        ].copy()
        if not monthly_prices.empty:
            st.plotly_chart(fig_price_curve(monthly_prices), use_container_width=True)
        else:
            st.markdown('<div class="info-subtle">Aucun prix sur la plage sélectionnée.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 - SIMULATION ACHAT (refonte complète, calcul horaire)
# ══════════════════════════════════════════════════════════════════════════════

# Import du moteur de simulation
import sys as _sys
_sys.path.insert(0, str(BASE_DIR))
from src.simulation_engine import (
    SimulatedPurchase,
    expand_portfolio_hourly,
    expand_purchase_hourly,
    build_hourly_index,
    run_simulation,
)

# Typologies d'achats prédéfinies (raccourcis)
_PRODUCT_TYPES = {
    "BaseLoad":  {"hour_start": 0,  "hour_end": 24, "days": "all",      "desc": "24h/24, 7j/7"},
    "Peakload":  {"hour_start": 8,  "hour_end": 20, "days": "business", "desc": "8h–20h, jours ouvrés"},
    "OffPeak":   {"hour_start": 0,  "hour_end": 24, "days": "all",      "desc": "Heures hors Peakload"},
    "Bloc custom": {"hour_start": 0, "hour_end": 24, "days": "all",     "desc": "Plage libre"},
}

if multi_site:
    st.markdown("""
<div class="section-block">
    <div class="section-heading">
        <h2>🧮 Simulation achat à terme</h2>
        <span class="section-desc">Testez l'impact d'un ou plusieurs achats envisagés sur votre coût d'approvisionnement</span>
    </div>
</div>""", unsafe_allow_html=True)

    if current_role != "admin":
        st.markdown('<div class="info-subtle">🔒 Réservé aux administrateurs.</div>', unsafe_allow_html=True)
    elif not all_sites_selected:
        st.markdown('<div class="info-subtle">ℹ️ Sélectionnez « Tous les sites » pour accéder à la simulation.</div>', unsafe_allow_html=True)
    elif prices_df.empty:
        st.markdown('<div class="info-subtle">⚠️ Simulation impossible sans données de prix.</div>', unsafe_allow_html=True)
    else:
        # ══════════════════════════════════════════════════════════════
        # 1. SÉLECTION DE LA PÉRIODE
        # ══════════════════════════════════════════════════════════════
        st.markdown("### 📅 Période de simulation")

        # Années disponibles dans les données
        _all_data = pd.concat([
            filtered_total[["datetime"]],
            preds_df[["datetime"]],
        ], ignore_index=True)
        _available_years = sorted(_all_data["datetime"].dt.year.unique())

        _period_col1, _period_col2 = st.columns([1, 2])
        with _period_col1:
            _period_mode = st.radio(
                "Mode période",
                ["Année entière", "Plage personnalisée"],
                horizontal=True,
                key="sim_period_mode",
            )
        with _period_col2:
            if _period_mode == "Année entière":
                _sim_year = st.selectbox(
                    "Année", options=_available_years,
                    index=min(len(_available_years)-1, 2),
                    key="sim_year_select",
                )
                _sim_start = pd.Timestamp(f"{_sim_year}-01-01")
                _sim_end = pd.Timestamp(f"{_sim_year}-12-31 23:00:00")
            else:
                _pc1, _pc2 = st.columns(2)
                with _pc1:
                    _sim_start = pd.Timestamp(st.date_input(
                        "Début", value=pd.Timestamp("2027-01-01"),
                        key="sim_date_start",
                    ))
                with _pc2:
                    _sim_end = pd.Timestamp(st.date_input(
                        "Fin", value=pd.Timestamp("2027-12-31"),
                        key="sim_date_end",
                    )) + pd.Timedelta(hours=23)

        _sim_period_label = (
            f"{_sim_start.strftime('%d/%m/%Y')} → {_sim_end.strftime('%d/%m/%Y')}"
        )
        st.caption(f"Période : **{_sim_period_label}**")

        # ══════════════════════════════════════════════════════════════
        # 2. SAISIE DES ACHATS SIMULÉS (dynamique)
        # ══════════════════════════════════════════════════════════════
        st.markdown("### ⚙️ Achats à terme envisagés")

        # Gestion du nombre de lignes d'achats dans session_state
        if "sim_purchase_count" not in st.session_state:
            st.session_state.sim_purchase_count = 1

        _add_col, _reset_col, _ = st.columns([1, 1, 3])
        with _add_col:
            if st.button("➕ Ajouter un achat", key="sim_add_purchase"):
                st.session_state.sim_purchase_count += 1
                st.rerun()
        with _reset_col:
            if st.button("🗑️ Réinitialiser", key="sim_reset_purchases"):
                st.session_state.sim_purchase_count = 1
                st.rerun()

        # Collecte des achats simulés
        _sim_purchases: list[SimulatedPurchase] = []
        _n_purchases = st.session_state.sim_purchase_count

        for i in range(_n_purchases):
            with st.container():
                st.markdown(f"**Achat #{i+1}**")
                _c1, _c2, _c3, _c4, _c5 = st.columns([1.5, 1, 1, 1, 1.5])

                with _c1:
                    _product = st.selectbox(
                        "Produit", options=list(_PRODUCT_TYPES.keys()),
                        key=f"sim_product_{i}",
                        help=", ".join(
                            f"{k}: {v['desc']}" for k, v in _PRODUCT_TYPES.items()
                        ),
                    )
                with _c2:
                    _direction = st.radio(
                        "Sens", ["Achat", "Vente"],
                        horizontal=True, key=f"sim_dir_{i}",
                    )
                with _c3:
                    _volume = st.number_input(
                        "Volume (MW)", min_value=0.0, value=1.0,
                        step=0.5, format="%.1f", key=f"sim_vol_{i}",
                    )
                with _c4:
                    _price = st.number_input(
                        "Prix (€/MWh)", min_value=0.0, value=52.5,
                        step=0.5, format="%.2f", key=f"sim_prix_{i}",
                    )
                with _c5:
                    _ptype = _PRODUCT_TYPES[_product]
                    if _product == "Bloc custom":
                        _hc1, _hc2 = st.columns(2)
                        with _hc1:
                            _h_start = st.number_input(
                                "Heure début", 0, 23, 0, key=f"sim_hstart_{i}")
                        with _hc2:
                            _h_end = st.number_input(
                                "Heure fin", 1, 24, 24, key=f"sim_hend_{i}")
                        _days = st.selectbox(
                            "Jours", ["all", "business", "weekend"],
                            format_func=lambda x: {
                                "all": "Tous les jours",
                                "business": "Jours ouvrés",
                                "weekend": "Week-end"
                            }[x],
                            key=f"sim_days_{i}",
                        )
                    elif _product == "OffPeak":
                        # OffPeak = tout sauf peak (géré dans le moteur comme inversion)
                        _h_start = 0
                        _h_end = 24
                        _days = "all"
                        st.caption("Heures hors Peakload")
                    else:
                        _h_start = _ptype["hour_start"]
                        _h_end = _ptype["hour_end"]
                        _days = _ptype["days"]
                        st.caption(_ptype["desc"])

                if _volume > 0:
                    if _product == "OffPeak":
                        # OffPeak = deux blocs : nuit tous jours + journée we
                        # Nuit : 0h–8h et 20h–24h tous les jours
                        _sim_purchases.append(SimulatedPurchase(
                            label=f"OffPeak #{i+1} (nuit)",
                            direction=_direction,
                            volume_mw=_volume,
                            price_eur_mwh=_price,
                            hour_start=0, hour_end=8,
                            days="all",
                        ))
                        _sim_purchases.append(SimulatedPurchase(
                            label=f"OffPeak #{i+1} (soir)",
                            direction=_direction,
                            volume_mw=_volume,
                            price_eur_mwh=_price,
                            hour_start=20, hour_end=24,
                            days="all",
                        ))
                        _sim_purchases.append(SimulatedPurchase(
                            label=f"OffPeak #{i+1} (we jour)",
                            direction=_direction,
                            volume_mw=_volume,
                            price_eur_mwh=_price,
                            hour_start=8, hour_end=20,
                            days="weekend",
                        ))
                    else:
                        _sim_purchases.append(SimulatedPurchase(
                            label=f"{_product} #{i+1}",
                            direction=_direction,
                            volume_mw=_volume,
                            price_eur_mwh=_price,
                            hour_start=_h_start,
                            hour_end=_h_end,
                            days=_days,
                        ))

            if i < _n_purchases - 1:
                st.markdown("---")

        # ══════════════════════════════════════════════════════════════
        # 3. MODE DE SIMULATION
        # ══════════════════════════════════════════════════════════════
        _mode_col1, _mode_col2 = st.columns([1, 3])
        with _mode_col1:
            _sim_mode = st.radio(
                "Mode",
                ["Impact cumulé", "Impact individuel"],
                key="sim_mode",
                help=(
                    "**Cumulé** : tous les achats saisis sont ajoutés ensemble. "
                    "**Individuel** : chaque achat est simulé séparément."
                ),
            )
        _mode_key = "cumulated" if _sim_mode == "Impact cumulé" else "individual"

        # ══════════════════════════════════════════════════════════════
        # 4. PRÉPARATION DES DONNÉES & EXÉCUTION
        # ══════════════════════════════════════════════════════════════
        if not _sim_purchases:
            st.info("Saisissez au moins un achat avec un volume > 0 MW pour lancer la simulation.")
        else:
            # Construction de l'index horaire
            _hourly_idx = build_hourly_index(_sim_start, _sim_end)

            # ── Consommation horaire (historique + prédictions) ─────
            _conso_all = pd.concat([
                hist_df[hist_df["site_label"].isin(selected_sites)],
                preds_df[preds_df["site_label"].isin(selected_sites)],
            ], ignore_index=True)
            # Dédupliquer : privilégier historique
            _conso_all = _conso_all.sort_values("data_type", ascending=True)  # Historique avant Prévision
            _conso_all = _conso_all.drop_duplicates(subset=["datetime"], keep="first")
            _conso_hourly = (
                _conso_all
                .groupby("datetime", as_index=False)["puissance_kw"].sum()
                .set_index("datetime")
                .reindex(_hourly_idx, fill_value=0.0)
            )
            _conso_hourly["conso_mwh"] = _conso_hourly["puissance_kw"] / 1000.0

            # ── Prix spot horaire (prédictions Prophet) ────────────
            _priority = ["mensuel", "trimestriel", "annuel"]
            _spot_df = pd.DataFrame({"datetime": _hourly_idx})
            _spot_df["prix_spot"] = price_for_datetimes(
                _spot_df["datetime"], prices_df, "prix_base", _priority
            ).values
            _spot_df = _spot_df.set_index("datetime")
            _spot_prices = _spot_df["prix_spot"].fillna(0.0)

            # ── Portefeuille existant expansé en horaire ───────────
            _achats_df = load_achats()
            _achats_period = pd.DataFrame()
            if not _achats_df.empty:
                _achats_period = _achats_df[
                    (_achats_df["DEB_PERIODE"] <= _sim_end) &
                    (_achats_df["FIN_PERIODE"] >= _sim_start)
                ].copy()

            _portfolio_hourly = expand_portfolio_hourly(_achats_period, _hourly_idx)

            # ── Exécution de la simulation ─────────────────────────
            _result = run_simulation(
                consumption_hourly=_conso_hourly,
                spot_prices_hourly=_spot_prices,
                portfolio_hourly=_portfolio_hourly,
                simulated_purchases=_sim_purchases,
                hourly_index=_hourly_idx,
                mode=_mode_key,
            )

            _kpi_a = _result.kpi_a
            _kpi_b = _result.kpi_b
            _delta_prix = _kpi_b["prix_moyen_mwh"] - _kpi_a["prix_moyen_mwh"]
            _delta_cout = _kpi_b["cout_total_eur"] - _kpi_a["cout_total_eur"]

            # ══════════════════════════════════════════════════════════
            # 5. VERDICT VISUEL
            # ══════════════════════════════════════════════════════════
            _seuil_marginal = 0.5  # €/MWh

            if _delta_prix < -_seuil_marginal:
                _verdict_color = "#10B981"
                _verdict_icon = "🟢"
                _verdict_text = "Achat favorable"
                _verdict_detail = (
                    f"Prix annuel réduit de **{abs(_delta_prix):.2f} €/MWh**, "
                    f"économie totale de **{abs(_delta_cout):,.0f} €**"
                )
            elif _delta_prix > _seuil_marginal:
                _verdict_color = "#EF4444"
                _verdict_icon = "🔴"
                _verdict_text = "Achat défavorable"
                _verdict_detail = (
                    f"Prix annuel augmenté de **{abs(_delta_prix):.2f} €/MWh**, "
                    f"surcoût de **{abs(_delta_cout):,.0f} €**"
                )
            else:
                _verdict_color = "#F59E0B"
                _verdict_icon = "🟡"
                _verdict_text = "Impact marginal"
                _verdict_detail = (
                    f"Écart de **{abs(_delta_prix):.2f} €/MWh** - "
                    f"différence non significative (< {_seuil_marginal} €/MWh)"
                )

            st.markdown(f"""
<div style="
    background: var(--surface);
    border: 1px solid var(--border);
    border-left: 4px solid {_verdict_color};
    border-radius: 16px;
    padding: 1.2rem 1.5rem;
    margin: 1rem 0;
    font-size: 0.95rem;
    box-shadow: var(--shadow-soft);
    backdrop-filter: blur(8px);
">
    <span style="font-size:1.3rem">{_verdict_icon}</span>
    <strong style="font-size:1.1rem; color:{_verdict_color}; margin-left:0.3rem">{_verdict_text}</strong><br/>
    <span style="color:var(--muted); font-size:0.88rem">{_verdict_detail}</span>
</div>
""", unsafe_allow_html=True)

            # ══════════════════════════════════════════════════════════
            # 6. KPIs COMPARATIFS - Bloc 1 (vue globale)
            # ══════════════════════════════════════════════════════════
            st.markdown("### 📊 KPIs - Vue globale")

            _k1, _k2, _k3 = st.columns(3)
            _k1.metric(
                "Prix moyen all-in (€/MWh)",
                f"{_kpi_b['prix_moyen_mwh']:.2f}",
                delta=f"{_delta_prix:+.2f} €/MWh",
                delta_color="inverse",
                help="Coût total / Consommation totale sur la période",
            )
            _k2.metric(
                "Coût total énergie (€)",
                f"{_kpi_b['cout_total_eur'] / 1e6:,.3f} M€",
                delta=f"{_delta_cout / 1e6:+,.3f} M€",
                delta_color="inverse",
                help="Somme de tous les coûts horaires sur la période",
            )
            _econo_label = "Économie" if _delta_cout < 0 else "Surcoût"
            _k3.metric(
                f"{_econo_label} généré (€)",
                f"{abs(_delta_cout):,.0f} €",
                delta=f"{'📉 favorable' if _delta_cout < 0 else '📈 défavorable'}",
                delta_color="normal" if _delta_cout < 0 else "inverse",
            )

            # ── Tableau Scénario A vs B ────────────────────────────
            st.markdown("#### Scénario A (référence) vs Scénario B (simulé)")
            _comp_tab = pd.DataFrame({
                "KPI": [
                    "Prix moyen all-in (€/MWh)",
                    "Coût total énergie (€)",
                ],
                "Scénario A (référence)": [
                    f"{_kpi_a['prix_moyen_mwh']:.2f}",
                    f"{_kpi_a['cout_total_eur']:,.0f}",
                ],
                "Scénario B (simulé)": [
                    f"{_kpi_b['prix_moyen_mwh']:.2f}",
                    f"{_kpi_b['cout_total_eur']:,.0f}",
                ],
                "Écart": [
                    f"{_delta_prix:+.2f}",
                    f"{_delta_cout:+,.0f}",
                ],
            })
            st.dataframe(_comp_tab, use_container_width=True, hide_index=True)

            # ══════════════════════════════════════════════════════════
            # 7. KPIs - Bloc 2 (exposition)
            # ══════════════════════════════════════════════════════════
            st.markdown("### 🔍 Détail de l'exposition")

            _e1, _e2, _e3 = st.columns(3)
            _e1.metric(
                "Volume couvert à terme (MWh)",
                f"{_kpi_b['vol_forward_mwh']:,.0f}",
                delta=f"{_kpi_b['vol_forward_mwh'] - _kpi_a['vol_forward_mwh']:+,.0f}",
                delta_color="normal",
            )
            _pct_spot_b = _kpi_b["pct_spot"]
            _e2.metric(
                "Volume au spot (MWh / %)",
                f"{_kpi_b['vol_spot_mwh']:,.0f} ({_pct_spot_b:.1f}%)",
                delta=f"{_kpi_b['vol_spot_mwh'] - _kpi_a['vol_spot_mwh']:+,.0f}",
                delta_color="inverse",
            )
            _e3.metric(
                "Prix moy. portefeuille terme (€/MWh)",
                f"{_kpi_b['prix_moyen_forward_mwh']:.2f}",
                delta=f"{_kpi_b['prix_moyen_forward_mwh'] - _kpi_a['prix_moyen_forward_mwh']:+.2f}",
                delta_color="inverse",
            )

            # Tableau exposition détaillé
            _expo_tab = pd.DataFrame({
                "Indicateur": [
                    "Consommation totale (MWh)",
                    "Volume couvert à terme (MWh)",
                    "Volume régularisé spot (MWh)",
                    "Couverture terme (%)",
                    "Exposition spot (%)",
                    "Prix moy. terme (€/MWh)",
                    "Coût terme (€)",
                    "Coût spot (€)",
                    "Coût total (€)",
                ],
                "Scénario A": [
                    f"{_kpi_a['conso_total_mwh']:,.0f}",
                    f"{_kpi_a['vol_forward_mwh']:,.0f}",
                    f"{_kpi_a['vol_spot_mwh']:,.0f}",
                    f"{_kpi_a['pct_forward']:.1f}%",
                    f"{_kpi_a['pct_spot']:.1f}%",
                    f"{_kpi_a['prix_moyen_forward_mwh']:.2f}",
                    f"{_kpi_a['cout_forward_eur']:,.0f}",
                    f"{_kpi_a['cout_spot_eur']:,.0f}",
                    f"{_kpi_a['cout_total_eur']:,.0f}",
                ],
                "Scénario B": [
                    f"{_kpi_b['conso_total_mwh']:,.0f}",
                    f"{_kpi_b['vol_forward_mwh']:,.0f}",
                    f"{_kpi_b['vol_spot_mwh']:,.0f}",
                    f"{_kpi_b['pct_forward']:.1f}%",
                    f"{_kpi_b['pct_spot']:.1f}%",
                    f"{_kpi_b['prix_moyen_forward_mwh']:.2f}",
                    f"{_kpi_b['cout_forward_eur']:,.0f}",
                    f"{_kpi_b['cout_spot_eur']:,.0f}",
                    f"{_kpi_b['cout_total_eur']:,.0f}",
                ],
            })
            st.dataframe(_expo_tab, use_container_width=True, hide_index=True)

            # ══════════════════════════════════════════════════════════
            # 8. GRAPHIQUE 1 - Coût cumulé A vs B (jour par jour)
            # ══════════════════════════════════════════════════════════
            st.markdown("### 📈 Coût cumulé - Scénario A vs B")

            _daily_a = _result.daily_a.copy()
            _daily_b = _result.daily_b.copy()
            _daily_a["cum_cost"] = _daily_a["cost_total_eur"].cumsum()
            _daily_b["cum_cost"] = _daily_b["cost_total_eur"].cumsum()

            fig_cum = go.Figure()
            fig_cum.add_trace(go.Scatter(
                x=_daily_a["date"], y=_daily_a["cum_cost"] / 1e6,
                mode="lines", name="Sc\u00e9nario A (r\u00e9f\u00e9rence)",
                line=dict(color=_chart_palette()[0], width=2.2),
                fill=None,
            ))
            fig_cum.add_trace(go.Scatter(
                x=_daily_b["date"], y=_daily_b["cum_cost"] / 1e6,
                mode="lines", name="Sc\u00e9nario B (simul\u00e9)",
                line=dict(color="#2DD4BF", width=2.2),
                fill="tonexty",
                fillcolor="rgba(45, 212, 191, 0.08)",
            ))
            fig_cum.update_layout(
                title=dict(
                    text="Coût cumulé jour par jour (M€)",
                    font=dict(size=14, color=_title_color()),
                    x=0,
                ),
                yaxis_title="M€",
            )
            _plotly_layout(fig_cum, height=440, x_grid=False, y_grid=True)
            st.plotly_chart(fig_cum, use_container_width=True)

            # ══════════════════════════════════════════════════════════
            # 9. GRAPHIQUE 2 - Histogramme des écarts quotidiens
            # ══════════════════════════════════════════════════════════
            st.markdown("### 📊 Écarts quotidiens - B meilleur / moins bon que A")

            _daily_diff = pd.DataFrame({
                "date": _daily_a["date"],
                "ecart_eur": _daily_b["cost_total_eur"].values - _daily_a["cost_total_eur"].values,
            })
            _daily_diff["couleur"] = np.where(
                _daily_diff["ecart_eur"] <= 0, "B meilleur (économie)", "B moins bon (surcoût)"
            )

            fig_ecart = go.Figure()
            _mask_pos = _daily_diff["ecart_eur"] > 0
            _mask_neg = _daily_diff["ecart_eur"] <= 0
            fig_ecart.add_trace(go.Bar(
                x=_daily_diff.loc[_mask_neg, "date"],
                y=_daily_diff.loc[_mask_neg, "ecart_eur"],
                name="B meilleur (\u00e9conomie)",
                marker_color="#34D399",
                marker_line=dict(width=0),
            ))
            fig_ecart.add_trace(go.Bar(
                x=_daily_diff.loc[_mask_pos, "date"],
                y=_daily_diff.loc[_mask_pos, "ecart_eur"],
                name="B moins bon (surco\u00fbt)",
                marker_color="#F87171",
                marker_line=dict(width=0),
            ))
            # Ligne zéro
            fig_ecart.add_hline(y=0, line_width=1, line_color=_title_color(), opacity=0.3)
            fig_ecart.update_layout(
                title=dict(
                    text="Écart de coût quotidien B − A (€)",
                    font=dict(size=14, color=_title_color()),
                    x=0,
                ),
                yaxis_title="€",
                barmode="relative",
            )
            _plotly_layout(fig_ecart, height=380, x_grid=False, y_grid=True)
            st.plotly_chart(fig_ecart, use_container_width=True)

            # ══════════════════════════════════════════════════════════
            # 10. RÉCAPITULATIF DES ACHATS SIMULÉS
            # ══════════════════════════════════════════════════════════
            st.markdown("### 📋 Récapitulatif des achats simulés")

            if _mode_key == "individual" and _result.individual_impacts:
                _recap_rows = []
                for imp in _result.individual_impacts:
                    p = imp["purchase"]
                    _recap_rows.append({
                        "Produit": p.label,
                        "Sens": p.direction,
                        "Volume (MW)": f"{p.volume_mw:.1f}",
                        "Prix (€/MWh)": f"{p.price_eur_mwh:.2f}",
                        "Plage": f"{p.hour_start}h–{p.hour_end}h",
                        "Jours": {"all": "Tous", "business": "Ouvrés", "weekend": "WE"}[p.days],
                        "Volume simulé (MWh)": f"{imp['vol_sim_mwh']:,.0f}",
                        "Δ Prix (€/MWh)": f"{imp['delta_prix_mwh']:+.2f}",
                        "Δ Coût (€)": f"{imp['delta_cout_total']:+,.0f}",
                    })
                st.dataframe(
                    pd.DataFrame(_recap_rows),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                # Mode cumulé : un seul récap des achats saisis
                _recap_rows = []
                for p in _sim_purchases:
                    _exp = expand_purchase_hourly(p, _hourly_idx)
                    _recap_rows.append({
                        "Produit": p.label,
                        "Sens": p.direction,
                        "Volume (MW)": f"{p.volume_mw:.1f}",
                        "Prix (€/MWh)": f"{p.price_eur_mwh:.2f}",
                        "Plage": f"{p.hour_start}h–{p.hour_end}h",
                        "Jours": {"all": "Tous", "business": "Ouvrés", "weekend": "WE"}[p.days],
                        "Volume total (MWh)": f"{abs(_exp['vol_sim_mwh'].sum()):,.0f}",
                    })
                st.dataframe(
                    pd.DataFrame(_recap_rows),
                    use_container_width=True,
                    hide_index=True,
                )

            # ══════════════════════════════════════════════════════════
            # 11. PORTEFEUILLE EXISTANT (référence)
            # ══════════════════════════════════════════════════════════
            with st.expander("📂 Portefeuille d'achats existants", expanded=False):
                if _achats_period.empty:
                    st.markdown(
                        '<div class="info-subtle">Aucun achat trouvé sur la période. '
                        'Déposez un fichier ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv dans data/raw/achats/.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    _cols_show = [
                        c for c in [
                            "TYPE_ACHAT", "CONTREPARTIE",
                            "FIXATION_PUISSANCE_ACHAT_MW", "PRIX_FIXATION",
                            "VOLUME_TOTAL_PERIODE", "COUT_TOTAL_PERIODE",
                            "DEB_PERIODE", "FIN_PERIODE",
                        ] if c in _achats_period.columns
                    ]
                    st.dataframe(
                        _achats_period[_cols_show].rename(columns={
                            "TYPE_ACHAT": "Type",
                            "CONTREPARTIE": "Contrepartie",
                            "FIXATION_PUISSANCE_ACHAT_MW": "MW",
                            "PRIX_FIXATION": "Prix (€/MWh)",
                            "VOLUME_TOTAL_PERIODE": "Volume (MWh)",
                            "COUT_TOTAL_PERIODE": "Coût (€)",
                            "DEB_PERIODE": "Début",
                            "FIN_PERIODE": "Fin",
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )

            # ── Export optionnel des données horaires ──────────────
            with st.expander("📥 Export données horaires (optionnel)", expanded=False):
                _export_df = _result.scenario_b.copy()
                _export_df["scenario"] = "B"
                _export_a = _result.scenario_a.copy()
                _export_a["scenario"] = "A"
                _export_full = pd.concat([_export_a, _export_df], ignore_index=False)
                st.download_button(
                    label="📥 Télécharger les données horaires (CSV)",
                    data=_export_full.to_csv(),
                    file_name="simulation_horaire_export.csv",
                    mime="text/csv",
                )
