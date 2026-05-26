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
USERS_DB_FILE = BASE_DIR / "users_demo.db"

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
    }

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
    .section-block { margin-top: 2rem; }
    .section-heading {
        text-align: center;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0.01em;
        color: var(--text);
        padding: 0.2rem 0.2rem;
        margin: 0rem 0 0.2rem 0;
    }
    .section-heading h2 {
        font-size: 2rem;
        font-weight: 800;
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
        flex-direction: column;
        align-items: flex-start;
        gap: 0.15rem;
        padding: 0.4rem 0.9rem;
        background: var(--primary-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        font-size: 1.2rem;
        color: var(--text);
    }
    .user-badge .user-role {
        font-size: 0.89rem;
        color: var(--primary);
    }
    .user-badge-wrapper {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.4rem 0.9rem;
        background: var(--primary-bg);
        border: 1px solid var(--border);
        border-radius: 12px;
        margin-bottom: 0.55rem;
    }
    .user-badge-wrapper .user-info {
        flex: 1;
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
    }
    .user-badge-wrapper .logout-btn-wrapper {
        display: flex;
        align-items: center;
    }
    .user-badge-wrapper .logout-btn-wrapper button {
        padding: 0.3rem 0.6rem !important;
        font-size: 0.85rem !important;
        min-height: auto !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        align-items: stretch;
        gap: 0 !important;
        margin-bottom: 0.55rem;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:last-child .stButton > button {
        height: 100% !important;
        border-radius: 0 12px 12px 0 !important;
        border-left: none !important;
        min-height: 52px !important;
        font-size: 1.1rem !important;
        background: var(--primary-bg) !important;
        color: var(--text) !important;
    }
    section[data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:last-child .stButton > button:hover {
        background: var(--primary-bg) !important;
        color: var(--danger) !important;
        border-color: var(--danger) !important;
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
    """Charge l'historique depuis data/raw/sites (source unique des graphiques)."""
    raw_sites_dir = DATA_DIR / "raw" / "sites"
    if not raw_sites_dir.exists():
        return pd.DataFrame()

    csv_files = sorted(raw_sites_dir.glob("dataclean_prm_*.csv"))
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
def load_achats() -> pd.DataFrame:
    """Charge tous les fichiers CSV ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv depuis data/raw/achats/."""
    if not ACHATS_DIR.exists():
        return pd.DataFrame()

    frames = []
    for f in sorted(ACHATS_DIR.glob("ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv")):
        try:
            df = pd.read_csv(f, sep=";")
            df.columns = [c.strip() for c in df.columns]
            frames.append(df)
        except Exception:
            continue

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    for date_col in ["DEB_PERIODE", "FIN_PERIODE", "DATE_ACHAT"]:
        if date_col in out.columns:
            out[date_col] = pd.to_datetime(out[date_col], errors="coerce")

    for num_col in ["VOLUME_TOTAL_PERIODE", "COUT_TOTAL_PERIODE", "PRIX_MOYEN",
                    "PRIX_FIXATION", "FIXATION_PUISSANCE_ACHAT_MW"]:
        if num_col in out.columns:
            out[num_col] = pd.to_numeric(out[num_col], errors="coerce")

    # ── Normalisation des colonnes Enedis ─────────────────────────────────
    # PRIX_FIXATION → PRIX_MOYEN (alias)
    if "PRIX_MOYEN" not in out.columns and "PRIX_FIXATION" in out.columns:
        out["PRIX_MOYEN"] = out["PRIX_FIXATION"]

    # Calculer VOLUME_TOTAL_PERIODE depuis MW × heures si absent
    if "VOLUME_TOTAL_PERIODE" not in out.columns and "FIXATION_PUISSANCE_ACHAT_MW" in out.columns:
        if "DEB_PERIODE" in out.columns and "FIN_PERIODE" in out.columns:
            _heures = (
                (out["FIN_PERIODE"] - out["DEB_PERIODE"])
                .dt.total_seconds()
                .div(3600)
                .clip(lower=0)
            )
            out["VOLUME_TOTAL_PERIODE"] = out["FIXATION_PUISSANCE_ACHAT_MW"].fillna(0) * _heures

    # Calculer COUT_TOTAL_PERIODE si absent
    if "COUT_TOTAL_PERIODE" not in out.columns:
        _vol = out.get("VOLUME_TOTAL_PERIODE", pd.Series(dtype=float))
        _prix = out.get("PRIX_MOYEN", pd.Series(dtype=float))
        if not _vol.empty and not _prix.empty:
            out["COUT_TOTAL_PERIODE"] = _vol.fillna(0) * _prix.fillna(0)

    return out

def formate_mwh(val: float) -> str:
    return f"{val:,.0f} MWh".replace(",", " ")


def format_int_space(val: float) -> str:
    return f"{val:,.0f}".replace(",", " ")


def consumption_mwh_for_year(df: pd.DataFrame, year: int) -> float:
    """Consommation annuelle en MWh avec intervalle réel entre mesures."""
    if df.empty:
        return 0.0

    col_kw = next((c for c in ["puissance_kw", "puissance_moy_heure"] if c in df.columns), None)
    if col_kw is None or "datetime" not in df.columns:
        return 0.0

    year_start = pd.Timestamp(year=year, month=1, day=1)
    year_end = pd.Timestamp(year=year, month=12, day=31, hour=23, minute=59, second=59)
    mask = (df["datetime"] >= year_start) & (df["datetime"] <= year_end)
    group_col = next((c for c in ["prm", "site_label"] if c in df.columns), None)
    cols = ["datetime", col_kw] + ([group_col] if group_col else [])
    year_df = df.loc[mask, cols].copy()
    if year_df.empty:
        return 0.0

    if group_col:
        year_df = year_df.sort_values([group_col, "datetime"]).copy()
        delta_h = year_df.groupby(group_col)["datetime"].diff().dt.total_seconds().div(3600)
        median_h = delta_h.groupby(year_df[group_col]).transform("median")
        year_df["interval_h"] = delta_h.fillna(median_h).fillna(1.0)
    else:
        year_df = year_df.sort_values("datetime").copy()
        delta_h = year_df["datetime"].diff().dt.total_seconds().div(3600)
        year_df["interval_h"] = delta_h.fillna(delta_h.median()).fillna(1.0)

    year_df["interval_h"] = year_df["interval_h"].clip(lower=1 / 60, upper=24)
    year_df["energy_mwh"] = year_df[col_kw] * year_df["interval_h"] / 1000.0
    return float(year_df["energy_mwh"].sum())


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


def purchased_components_for_period(df: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp) -> tuple[float, float]:
    """
    Retourne (volume_mwh, prix_moyen_eur_mwh) des achats attribuables à une période,
    avec prorata sur les périodes chevauchantes.
    """
    if df.empty or "VOLUME_TOTAL_PERIODE" not in df.columns:
        return 0.0, 0.0

    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    if pd.isna(start) or pd.isna(end) or end < start:
        return 0.0, 0.0

    volume_mwh = 0.0
    cost_eur = 0.0

    has_period = "DEB_PERIODE" in df.columns and "FIN_PERIODE" in df.columns
    has_date_achat = "DATE_ACHAT" in df.columns

    if has_period:
        period_df = df.dropna(subset=["DEB_PERIODE", "FIN_PERIODE"]).copy()
        if not period_df.empty:
            overlap_mask = (period_df["DEB_PERIODE"] <= end) & (period_df["FIN_PERIODE"] >= start)
            period_df = period_df.loc[overlap_mask].copy()

            if not period_df.empty:
                start_clip = period_df["DEB_PERIODE"].clip(lower=start)
                end_clip = period_df["FIN_PERIODE"].clip(upper=end)
                overlap_days = (end_clip - start_clip).dt.total_seconds().div(86400).clip(lower=0)
                full_days = (period_df["FIN_PERIODE"] - period_df["DEB_PERIODE"]).dt.total_seconds().div(86400).clip(lower=1e-9)
                prorata = overlap_days / full_days

                period_vol = period_df["VOLUME_TOTAL_PERIODE"].fillna(0) * prorata
                if "COUT_TOTAL_PERIODE" in period_df.columns:
                    period_cost = period_df["COUT_TOTAL_PERIODE"].fillna(0) * prorata
                else:
                    period_cost = period_vol * period_df.get("PRIX_MOYEN", 0).fillna(0)

                volume_mwh += period_vol.sum()
                cost_eur += period_cost.sum()

        if has_date_achat:
            missing_period = df[df["DEB_PERIODE"].isna() | df["FIN_PERIODE"].isna()].copy()
            if not missing_period.empty:
                mask = (missing_period["DATE_ACHAT"] >= start) & (missing_period["DATE_ACHAT"] <= end)
                subset = missing_period.loc[mask].copy()
                if not subset.empty:
                    add_vol = subset["VOLUME_TOTAL_PERIODE"].fillna(0)
                    if "COUT_TOTAL_PERIODE" in subset.columns:
                        add_cost = subset["COUT_TOTAL_PERIODE"].fillna(0)
                    else:
                        add_cost = add_vol * subset.get("PRIX_MOYEN", 0).fillna(0)
                    volume_mwh += add_vol.sum()
                    cost_eur += add_cost.sum()

    elif has_date_achat:
        subset = df[(df["DATE_ACHAT"] >= start) & (df["DATE_ACHAT"] <= end)].copy()
        if not subset.empty:
            add_vol = subset["VOLUME_TOTAL_PERIODE"].fillna(0)
            if "COUT_TOTAL_PERIODE" in subset.columns:
                add_cost = subset["COUT_TOTAL_PERIODE"].fillna(0)
            else:
                add_cost = add_vol * subset.get("PRIX_MOYEN", 0).fillna(0)
            volume_mwh += add_vol.sum()
            cost_eur += add_cost.sum()

    volume_mwh = float(max(0.0, volume_mwh))
    avg_price = float(cost_eur / volume_mwh) if volume_mwh > 0 else 0.0
    return volume_mwh, avg_price


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
        separators=". ",
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


def fig_simulation_purchase_comparison(
    en_etat_achete_mwh: float,
    en_etat_restant_mwh: float,
    simule_achete_mwh: float,
    simule_nouvel_achat_mwh: float,
    simule_vendu_mwh: float,
    simule_restant_mwh: float,
    en_etat_cout_achete_eur: float,
    en_etat_cout_restant_eur: float,
    simule_cout_achete_eur: float,
    simule_cout_nouvel_achat_eur: float,
    simule_revenu_vente_eur: float,
    simule_cout_restant_eur: float,
) -> go.Figure:
    """Graphique comparatif professionnel : En l'état vs Simulé (barres empilées)."""
    c_orange = "#F59E0B"
    c_green = "#22C55E"
    c_gray = "#CBD5E1"
    c_axis = "#334155"
    c_bg = "#F6F7FB"

    categories = ["En l'état", "Simulé"]
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=categories,
        y=[en_etat_achete_mwh, simule_achete_mwh],
        name="Conso achetée (au prix moyen acheté)",
        marker_color=c_orange,
        width=0.52,
        text=[f"{format_int_space(en_etat_cout_achete_eur)} €", f"{format_int_space(simule_cout_achete_eur)} €"],
        textposition="inside",
        textfont=dict(color="#111827", size=12),
        hovertemplate="<b>%{x}</b><br>Conso achetée: %{y:,.0f} MWh<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=categories,
        y=[0.0, simule_nouvel_achat_mwh],
        name="Conso simulée (au prix simulé saisi)",
        marker_color=c_green,
        width=0.52,
        text=["", f"{format_int_space(simule_cout_nouvel_achat_eur)} €"],
        textposition="inside",
        textfont=dict(color="#0F172A", size=12),
        hovertemplate="<b>%{x}</b><br>Conso simulée: %{y:,.0f} MWh<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=categories,
        y=[en_etat_restant_mwh, simule_restant_mwh],
        name="Conso restante (au prix spot)",
        marker_color=c_gray,
        width=0.52,
        text=[f"{format_int_space(en_etat_cout_restant_eur)} €", f"{format_int_space(simule_cout_restant_eur)} €"],
        textposition="inside",
        textfont=dict(color="#1F2937", size=12),
        hovertemplate="<b>%{x}</b><br>Conso spot restante: %{y:,.0f} MWh<extra></extra>",
    ))

    total_en_etat_mwh = en_etat_achete_mwh + en_etat_restant_mwh
    total_simule_mwh = simule_achete_mwh + simule_nouvel_achat_mwh + simule_restant_mwh
    total_en_etat_eur = en_etat_cout_achete_eur + en_etat_cout_restant_eur
    total_simule_eur = (
        simule_cout_achete_eur
        + simule_cout_nouvel_achat_eur
        + simule_cout_restant_eur
        - simule_revenu_vente_eur
    )

    _y_pad = max(1.0, max(total_en_etat_mwh, total_simule_mwh) * 0.08)
    fig.add_annotation(
        x="En l'état",
        y=total_en_etat_mwh + _y_pad,
        text=f"<b>Total : {format_int_space(total_en_etat_eur)} €</b>",
        showarrow=False,
        font=dict(size=13, color="#0F172A"),
    )
    fig.add_annotation(
        x="Simulé",
        y=total_simule_mwh + _y_pad,
        text=f"<b>Total : {format_int_space(total_simule_eur)} €</b>",
        showarrow=False,
        font=dict(size=13, color="#0F172A"),
    )

    if simule_vendu_mwh > 0:
        fig.add_trace(go.Scatter(
            x=["Simulé"],
            y=[total_simule_mwh],
            mode="markers+text",
            name="Vente simulée",
            marker=dict(color="#8B5CF6", size=10, symbol="diamond"),
            text=[f"Vente : {format_int_space(simule_vendu_mwh)} MWh · Revenu : {format_int_space(simule_revenu_vente_eur)} €"],
            textposition="top center",
            textfont=dict(color="#6D28D9", size=12),
            hovertemplate="<b>Simulé</b><br>Volume vendu: %{customdata[0]:,.0f} MWh<br>Revenu: %{customdata[1]:,.0f} €<extra></extra>",
            customdata=[[simule_vendu_mwh, simule_revenu_vente_eur]],
        ))

    fig.update_layout(
        barmode="stack",
        bargap=0.42,
        barcornerradius=8,
        separators=". ",
        height=520,
        margin=dict(t=48, r=24, b=50, l=70),
        paper_bgcolor=c_bg,
        plot_bgcolor=c_bg,
        title=dict(text="Comparatif financier de couverture énergie", x=0, font=dict(size=14, color=_title_color())),
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color=c_axis),
        xaxis=dict(
            title="Scénarios comparés",
            title_font=dict(size=13, color="#1E293B"),
            tickfont=dict(size=13, color="#1E293B"),
            showline=True,
            linecolor="#94A3B8",
        ),
        yaxis=dict(
            title="Consommation énergétique (MWh)",
            title_font=dict(size=13, color="#1E293B"),
            tickfont=dict(size=12, color="#334155"),
            gridcolor="#E2E8F0",
            zeroline=False,
            rangemode="tozero",
        ),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.04,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.85)",
            font=dict(size=11, color="#1E293B"),
        ),
    )
    _plotly_layout(fig, height=520, x_grid=False, y_grid=True)
    _y_top = max(total_en_etat_mwh, total_simule_mwh) + (_y_pad * 1.8)
    fig.update_yaxes(range=[0, _y_top])
    return fig


def fig_current_state_yearly_bar(state_yearly_df: pd.DataFrame, current_year: int) -> go.Figure:
    """Barres empilées de l'état actuel par année (acheté vs restant spot)."""
    c_orange = "#F59E0B"
    c_gray = "#CBD5E1"
    c_axis = "#334155"
    c_bg = "#F6F7FB"

    fig = go.Figure()

    if state_yearly_df.empty:
        fig.update_layout(
            title=dict(
                text=f"État actuel par année (à partir de {current_year})",
                font=dict(size=14, color=_title_color()),
                x=0,
            ),
            height=520,
        )
        _plotly_layout(fig, height=520, x_grid=False, y_grid=True)
        return fig

    x_years = state_yearly_df["year"].astype(str).tolist()

    fig.add_trace(go.Bar(
        x=x_years,
        y=state_yearly_df["achete_mwh"],
        name="MWh achetés",
        marker_color=c_orange,
        width=0.52,
        text=[f"{format_int_space(v)} €" for v in state_yearly_df["cout_achete_eur"]],
        textposition="inside",
        textfont=dict(color="#111827", size=11),
        hovertemplate="<b>%{x}</b><br>MWh achetés: %{y:,.0f}<extra></extra>",
    ))

    fig.add_trace(go.Bar(
        x=x_years,
        y=state_yearly_df["restant_mwh"],
        name="MWh restants (prix spot)",
        marker_color=c_gray,
        width=0.52,
        text=[f"{format_int_space(v)} €" for v in state_yearly_df["cout_restant_eur"]],
        textposition="inside",
        textfont=dict(color="#1F2937", size=11),
        hovertemplate="<b>%{x}</b><br>MWh restants spot: %{y:,.0f}<extra></extra>",
    ))

    for _, row in state_yearly_df.iterrows():
        total_mwh = float(row["achete_mwh"] + row["restant_mwh"])
        total_eur = float(row["cout_achete_eur"] + row["cout_restant_eur"])
        y_pad = max(1.0, total_mwh * 0.06)
        fig.add_annotation(
            x=str(int(row["year"])),
            y=total_mwh + y_pad,
            text=f"<b>{format_int_space(total_eur)} €</b>",
            showarrow=False,
            font=dict(size=11, color="#0F172A"),
        )

    fig.update_layout(
        barmode="stack",
        bargap=0.42,
        barcornerradius=8,
        separators=". ",
        height=520,
        margin=dict(t=48, r=24, b=50, l=70),
        paper_bgcolor=c_bg,
        plot_bgcolor=c_bg,
        title=dict(
            text=f"État actuel par année (à partir de {current_year})",
            font=dict(size=14, color=_title_color()),
            x=0,
        ),
        font=dict(family="Inter, -apple-system, sans-serif", size=12, color=c_axis),
        xaxis=dict(
            title="Année",
            title_font=dict(size=13, color="#1E293B"),
            tickfont=dict(size=13, color="#1E293B"),
            showline=True,
            linecolor="#94A3B8",
        ),
        yaxis=dict(
            title="Consommation énergétique (MWh)",
            title_font=dict(size=13, color="#1E293B"),
            tickfont=dict(size=12, color="#334155"),
            gridcolor="#E2E8F0",
            zeroline=False,
            rangemode="tozero",
        ),
        legend=dict(
            orientation="h",
            x=0.0,
            y=1.04,
            xanchor="left",
            yanchor="bottom",
            bgcolor="rgba(255,255,255,0.85)",
            font=dict(size=11, color="#1E293B"),
        ),
    )
    _plotly_layout(fig, height=520, x_grid=False, y_grid=True)
    return fig


def fig_simulation_predicted_consumption(hourly_pred: pd.DataFrame, sim_type: str) -> go.Figure:
    if hourly_pred.empty:
        return go.Figure()

    total_mwh = float(hourly_pred["energy_mwh"].sum())
    start_ts = pd.to_datetime(hourly_pred["datetime"]).min()
    end_ts = pd.to_datetime(hourly_pred["datetime"]).max()

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=["Période simulée"],
        y=[total_mwh],
        name="Conso prédite totale",
        marker_color=_chart_palette()[1],
        width=0.5,
        text=[f"{format_int_space(total_mwh)} MWh"],
        textposition="outside",
        hovertemplate="<b>Période simulée</b><br>Conso prédite totale: %{y:,.2f} MWh<extra></extra>",
    ))

    period_label = f"{start_ts:%d/%m/%Y} → {end_ts:%d/%m/%Y}"
    fig.update_layout(
        title=dict(
            text=f"Consommation prédite totale ({sim_type}) · {period_label}",
            font=dict(size=14, color=_title_color()),
            x=0,
        ),
        margin=dict(t=70, b=20, l=16, r=16),
    )
    _plotly_layout(fig, height=320, x_grid=False, y_grid=True, show_legend=False)
    fig.update_yaxes(title="MWh")
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
            "Prévisions \u00b7 Prix \u00b7 Suivi mod\u00e8les IA</div>",
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
            label, last_hist_date.strftime("%Y-%m-%d %H:%M"), _age_days, DATA_STALENESS_WARN_DAYS,
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

# Consommation année en cours et N-1 depuis all_years_total (MWh, calcul énergétique cohérent)
_conso_this_yr = consumption_mwh_for_year(all_years_total, _this_year)
_conso_last_yr = consumption_mwh_for_year(all_years_total, _last_year)
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
            <div class="kpi-value">{format_int_space(_conso_this_yr)} MWh</div>
            {_d_html}
        </div>""", unsafe_allow_html=True)
    with kc2:
        st.markdown(f"""
        <div class="kpi-card kpi-amber">
            <div class="kpi-label">Puissance achet\u00e9e {_this_year}</div>
            <div class="kpi-value">{format_int_space(_VOL_ACHETE_MWH)} MWh</div>
        </div>""", unsafe_allow_html=True)
    with kc3:
        st.markdown(f"""
        <div class="kpi-card kpi-teal">
            <div class="kpi-label">Derni\u00e8re mesure</div>
            <div class="kpi-value">{_last_hist_str}</div>
        </div>""", unsafe_allow_html=True)
    with kc4:
        st.markdown(f"""
        <div class="kpi-card kpi-violet">
            <div class="kpi-label">Sites</div>
            <div class="kpi-value">{_nb_sites_total}</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='margin-bottom:1.8rem'></div>", unsafe_allow_html=True)


# Identifiants du site sélectionné (utilisés pour la section « À propos du modèle »)
chosen_prm        = preds_df.loc[preds_df["site_label"] == selected_sites[0], "prm"].iloc[0] if not multi_site else None
chosen_train_site = selected_sites[0] if not multi_site else None


# Répartition par site EN PREMIER, puis courbe, puis totaux annuels, puis barres par site
if multi_site:
    _pc1, _pc2, _pc3 = st.columns([1, 2, 1])
    with _pc2:
        st.plotly_chart(fig_pie(filtered), use_container_width=True,
            key="chart_pie_1",
        )
    st.plotly_chart(fig_consumption_curve(filtered, aggregate=True), use_container_width=True,
            key="chart_consumption_curve_1",
        )
    st.plotly_chart(fig_annual_total_bar(all_years_total), use_container_width=True,
            key="chart_annual_total_bar_1",
        )
    st.plotly_chart(fig_yearly_bar(all_years_total), use_container_width=True,
            key="chart_yearly_bar_1",
        )
else:
    st.plotly_chart(fig_consumption_curve(filtered, aggregate=False), use_container_width=True,
            key="chart_consumption_curve_2",
        )
    st.plotly_chart(fig_annual_total_bar(all_years_total), use_container_width=True,
            key="chart_annual_total_bar_2",
        )


# ══════════════════════════════════════════════════════════════════════════════
# SECTION « À PROPOS DU MODÈLE » — visible uniquement si un site (PRM) est sélectionné.
# Chaque site industriel possède son propre modèle entraîné sur ses données historiques.
# Le réentraînement est réservé aux administrateurs.
# ══════════════════════════════════════════════════════════════════════════════

if not multi_site and chosen_prm:
    st.markdown("---")
    st.markdown("""
    <div class=\"section-block\">
        <div class=\"section-heading\">
            <h2>\U0001f9e0 À propos du modèle</h2>
            <span class=\"section-desc\">
                Métriques de performance du modèle de prédiction associé à ce site (PRM).<br>
                Chaque site industriel possède son propre modèle entraîné sur ses données historiques.
            </span>
        </div>
    </div>""", unsafe_allow_html=True)

    # ── Métriques actuelles ────────────────────────────────────────────────
    _current_metrics = load_mlflow_metrics(chosen_prm)

    _metrics_labels = {
        "val_rmse": ("RMSE",     "Erreur quadratique moyenne",   "↓ plus bas = mieux"),
        "val_mae":  ("MAE",      "Erreur absolue moyenne",       "↓ plus bas = mieux"),
        "val_mape": ("MAPE",     "Erreur en pourcentage",        "↓ plus bas = mieux"),
        "val_r2":   ("R² Score", "Coefficient de détermination", "↑ plus haut = mieux"),
    }

    if _current_metrics:
        _m_cols = st.columns(4)
        for _mi, (mkey, (mlabel, mdesc, mhint)) in enumerate(_metrics_labels.items()):
            with _m_cols[_mi]:
                mval = _current_metrics.get(mkey)
                _mval_str   = f"{mval:.4f}" if mval is not None else "—"
                _mval_color = "var(--text)" if mval is not None else "var(--muted)"
                st.markdown(
                    f"<div style='background:var(--primary-bg);padding:1rem 1.2rem;"
                    f"border-radius:12px;border:1px solid var(--border);height:100%'>"
                    f"<div style='font-size:0.72rem;color:var(--muted);text-transform:uppercase;"
                    f"letter-spacing:0.08em;font-weight:600;margin-bottom:0.4rem'>{mlabel}</div>"
                    f"<div style='font-size:1.45rem;font-weight:700;color:{_mval_color};"
                    f"margin-bottom:0.2rem'>{_mval_str}</div>"
                    f"<div style='font-size:0.75rem;color:var(--muted)'>{mdesc}</div>"
                    f"<div style='font-size:0.72rem;color:#94A3B8;margin-top:0.3rem'>{mhint}</div>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
    else:
        st.markdown(
            "<div class='info-subtle'>⚠️ Aucune métrique MLflow disponible pour ce site. "
            "Lancez un premier entraînement pour générer les métriques.</div>",
            unsafe_allow_html=True,
        )

    # ── Réentraînement (administrateurs uniquement) ───────────────────────
    st.markdown("<div style='margin-top:1.5rem'></div>", unsafe_allow_html=True)

    if current_role == "admin":
        _already_trained = (
            st.session_state.training_new_metrics is not None
            and st.session_state.training_prm == chosen_prm
            and not st.session_state.training_accepted
        )

        with st.expander("🔄 Réentraîner le modèle", expanded=False):
            st.markdown(
                f"<div style='font-size:0.92rem;color:var(--muted);margin-bottom:1rem'>"
                f"Vous êtes connecté en tant qu'<b>administrateur</b>. "
                f"Le réentraînement met à jour le modèle de prédiction du site "
                f"<b>{chosen_train_site}</b> à partir de ses données historiques les plus récentes."
                f"<br><b>⚠️ Cette opération peut nécessiter plusieurs minutes de calcul.</b>"
                f"</div>",
                unsafe_allow_html=True,
            )

            _launch = st.button(
                "🔄 Lancer le réentraînement" if not _already_trained else "✅ Réentraînement terminé",
                use_container_width=True,
                type="primary",
                disabled=_already_trained,
                key="btn_retrain_model_section",
            )

            if _launch:
                st.session_state.training_prm         = chosen_prm
                st.session_state.training_old_metrics = load_mlflow_metrics(chosen_prm)
                st.session_state.training_new_metrics = None
                st.session_state.training_accepted    = False
                st.warning(
                    "⏳ Entraînement lancé. Cette opération peut prendre **5 à 30 minutes** "
                    "selon la taille des données. Veuillez ne pas fermer la page.",
                    icon="⚠️",
                )
                with st.spinner(f"Entraînement en cours pour {chosen_train_site}… Merci de patienter."):
                    new_metrics = simulate_training(chosen_prm, st.session_state.training_old_metrics)
                st.session_state.training_new_metrics = new_metrics
                st.rerun()

            # ── Comparaison ancien / nouveau modèle ───────────────────────
            if (
                st.session_state.training_new_metrics is not None
                and st.session_state.training_prm == chosen_prm
                and not st.session_state.training_accepted
            ):
                st.markdown("<div style='margin-top:1rem'></div>", unsafe_allow_html=True)
                st.markdown(
                    "<div style='font-weight:600;font-size:1rem;margin-bottom:0.8rem'>"
                    "📊 Comparaison des métriques — Modèle actuel vs Nouveau modèle"
                    "</div>",
                    unsafe_allow_html=True,
                )
                old_m = st.session_state.training_old_metrics
                new_m = st.session_state.training_new_metrics

                _cmp_cols = st.columns(4)
                for _ci, (mkey, (mlabel, _mdesc, _mhint)) in enumerate(_metrics_labels.items()):
                    with _cmp_cols[_ci]:
                        old_val = old_m.get(mkey) if old_m else None
                        new_val = new_m.get(mkey) if new_m else None
                        if new_val is not None:
                            if old_val is not None:
                                if mkey == "val_r2":
                                    change_pct = ((new_val - old_val) / abs(old_val) * 100) if old_val != 0 else 0
                                    improved = new_val > old_val
                                else:
                                    change_pct = ((old_val - new_val) / old_val * 100) if old_val != 0 else 0
                                    improved = new_val < old_val
                                badge_color = "#22C55E" if improved else "#EF4444"
                                badge_icon  = "🟢" if improved else "🔴"
                                arrow       = "↓" if mkey != "val_r2" else "↑"
                                improve_txt = "Amélioration" if improved else "Dégradation"
                                st.markdown(
                                    f"<div style='background:var(--primary-bg);padding:1rem;border-radius:12px;"
                                    f"border:2px solid {badge_color}33;'>"
                                    f"<div style='font-size:0.72rem;color:var(--muted);text-transform:uppercase;"
                                    f"letter-spacing:0.08em;font-weight:600;margin-bottom:0.5rem'>{mlabel}</div>"
                                    f"<div style='font-size:0.85rem;color:var(--muted);margin-bottom:0.2rem'>"
                                    f"Actuel : <b style='color:var(--text)'>{old_val:.4f}</b></div>"
                                    f"<div style='font-size:0.85rem;color:var(--muted);margin-bottom:0.5rem'>"
                                    f"Nouveau : <b style='color:var(--text)'>{new_val:.4f}</b></div>"
                                    f"<div style='font-size:0.82rem'>{badge_icon} {arrow} {abs(change_pct):.1f}% {improve_txt}</div>"
                                    f"</div>",
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.markdown(
                                    f"<div style='background:var(--primary-bg);padding:1rem;border-radius:12px;"
                                    f"border:1px solid var(--border);'>"
                                    f"<div style='font-size:0.72rem;color:var(--muted);text-transform:uppercase;"
                                    f"letter-spacing:0.08em;font-weight:600;margin-bottom:0.5rem'>{mlabel}</div>"
                                    f"<div style='font-size:1.1rem;font-weight:700'>{new_val:.4f}</div>"
                                    f"<div style='font-size:0.75rem;color:var(--muted);margin-top:0.3rem'>Premier entraînement</div>"
                                    f"</div>",
                                    unsafe_allow_html=True,
                                )
                        else:
                            st.markdown(
                                f"<div style='background:var(--primary-bg);padding:1rem;border-radius:12px;"
                                f"border:1px solid var(--border);'>"
                                f"<div style='font-size:0.72rem;color:var(--muted);text-transform:uppercase;"
                                f"letter-spacing:0.08em;font-weight:600;margin-bottom:0.5rem'>{mlabel}</div>"
                                f"<div style='color:var(--muted);font-size:0.85rem'>Non disponible</div>"
                                f"</div>",
                                unsafe_allow_html=True,
                            )

                st.divider()
                _accept_col, _reject_col = st.columns(2)
                with _accept_col:
                    if st.button("✅ Enregistrer le nouveau modèle", use_container_width=True, type="primary"):
                        st.session_state.training_accepted = True
                        _mlops_logger.info(f"MODÈLE ACCEPTÉ | PRM={chosen_prm} | métriques={new_m}")
                        st.success("✅ Nouveau modèle enregistré et activé pour ce site !")
                        st.rerun()
                with _reject_col:
                    if st.button("🔒 Conserver le modèle actuel", use_container_width=True):
                        st.session_state.training_new_metrics = None
                        st.session_state.training_old_metrics = None
                        _mlops_logger.info(f"MODÈLE CONSERVÉ (rejeté) | PRM={chosen_prm}")
                        st.info("Modèle actuel conservé. Aucune modification appliquée.")
                        st.rerun()
    else:
        # Utilisateur non-admin : mention informative
        st.markdown(
            "<div class='info-subtle' style='margin-top:0.5rem'>🔒 Le réentraînement du modèle est "
            "réservé aux <b>administrateurs</b> afin de garantir la stabilité du système de prédiction.</div>",
            unsafe_allow_html=True,
        )



# SECTION 2 - PRIX SPOT
# ══════════════════════════════════════════════════════════════════════════════

if multi_site:
    st.markdown("---")
    st.markdown("""
    <div class="section-block">
        <div class="section-heading">
            <h2>Prix futur</h2>
            <span class="section-desc">Évolution mensuelle Base et Peak sur la période sélectionnée</span>
        </div>
    </div>""", unsafe_allow_html=True)

    if prices_df.empty:
        st.markdown('<div class="info-subtle">⚠️ Aucune donnée de prix disponible.</div>', unsafe_allow_html=True)
    else:
        price_priority = ["horaire", "mensuel", "trimestriel", "annuel"]
        monthly_prices = build_monthly_price_series(
            prices_df, pd.to_datetime(start_date), pd.to_datetime(end_date), price_priority
        )
        monthly_prices = monthly_prices.loc[
            monthly_prices["month"].dt.year.isin(selected_years)
        ].copy()
        if not monthly_prices.empty:
            st.plotly_chart(fig_price_curve(monthly_prices), use_container_width=True,
            key="chart_price_curve_1",
        )
        else:
            st.markdown('<div class="info-subtle">Aucun prix sur la plage sélectionnée.</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 - SIMULATION ACHAT ÉNERGIE (interface métier simplifiée)
# ══════════════════════════════════════════════════════════════════════════════

# ── Helpers simulation simplifiée ─────────────────────────────────────────────

def _sim_spot_moyen(prices_df, start, end):
    """Prix spot moyen (€/MWh Base) sur la période — préfère les lignes horaires."""
    if prices_df.empty:
        return 0.0
    # Priorité : horaire > mensuel > trimestriel > annuel
    for _type in ["horaire", "mensuel", "trimestriel", "annuel"]:
        mask = (
            (prices_df["type"] == _type) &
            (prices_df["date_deb"] <= end) &
            (prices_df["date_fin"] >= start)
        )
        subset = prices_df.loc[mask]
        if not subset.empty:
            return float(subset["prix_base"].mean())
    return 55.0


def _sim_conso_horaire(filtered_total, start, end):
    """
    Retourne un DataFrame horaire avec colonnes [datetime, energy_mwh]
    calculé depuis filtered_total sur la période [start, end].
    """
    if filtered_total.empty:
        return pd.DataFrame(columns=["datetime", "energy_mwh"])
    col_kw = next((c for c in ["puissance_kw", "puissance_moy_heure"] if c in filtered_total.columns), None)
    if col_kw is None:
        return pd.DataFrame(columns=["datetime", "energy_mwh"])
    mask = (filtered_total["datetime"] >= start) & (filtered_total["datetime"] <= end)
    group_col = next((c for c in ["prm", "site_label"] if c in filtered_total.columns), None)
    cols = ["datetime", col_kw] + ([group_col] if group_col else [])
    df = filtered_total.loc[mask, cols].copy()
    if df.empty:
        return pd.DataFrame(columns=["datetime", "energy_mwh"])

    # Intervalle réel entre mesures (en heures), calculé par site/PRM
    if group_col:
        df = df.sort_values([group_col, "datetime"]).copy()
        _delta_h = (
            df.groupby(group_col)["datetime"]
            .diff()
            .dt.total_seconds()
            .div(3600)
        )
        _median_h = _delta_h.groupby(df[group_col]).transform("median")
        df["interval_h"] = _delta_h.fillna(_median_h).fillna(1.0)
    else:
        df = df.sort_values("datetime").copy()
        _delta_h = df["datetime"].diff().dt.total_seconds().div(3600)
        _median_h = _delta_h.median()
        df["interval_h"] = _delta_h.fillna(_median_h).fillna(1.0)

    df["interval_h"] = df["interval_h"].clip(lower=1/60, upper=24)
    df["energy_mwh"] = df[col_kw] * df["interval_h"] / 1000.0
    # Arrondi à l'heure pour le join prix
    df["datetime_h"] = df["datetime"].dt.floor("h")
    hourly = df.groupby("datetime_h", as_index=False)["energy_mwh"].sum()
    return hourly.rename(columns={"datetime_h": "datetime"})


def _sim_prix_horaire(prices_df, hourly_df, price_col="prix_base"):
    """
    Joint le prix spot précis à chaque heure de hourly_df.
    Priorité : horaire > mensuel > trimestriel > annuel.
    """
    if prices_df.empty or hourly_df.empty:
        hourly_df = hourly_df.copy()
        hourly_df["prix_spot"] = 55.0
        return hourly_df
    priority = ["horaire", "mensuel", "trimestriel", "annuel"]
    prix_series = price_for_datetimes(
        hourly_df["datetime"].reset_index(drop=True),
        prices_df, price_col, priority
    )
    hourly_df = hourly_df.copy()
    hourly_df["prix_spot"] = prix_series.values
    hourly_df["prix_spot"] = hourly_df["prix_spot"].fillna(55.0)
    return hourly_df


def _sim_is_peak_slot(datetimes: pd.Series) -> pd.Series:
    """Créneau Peak : lundi à vendredi, de 08:00 (inclus) à 20:00 (exclu)."""
    _dt = pd.to_datetime(datetimes)
    return (_dt.dt.weekday < 5) & (_dt.dt.hour >= 8) & (_dt.dt.hour < 20)


def _sim_prix_horaire_selon_type(prices_df, hourly_df, sim_type: str):
    """
    Applique le prix horaire selon le type d'achat simulé.
    - Base : prix_base sur toutes les heures
    - Peak : prix_peak en créneau Peak, sinon prix_base
    """
    if hourly_df.empty:
        hourly_df = hourly_df.copy()
        hourly_df["prix_spot"] = 55.0
        hourly_df["is_peak_slot"] = False
        return hourly_df

    if sim_type != "Peak":
        out = _sim_prix_horaire(prices_df, hourly_df, price_col="prix_base")
        out["is_peak_slot"] = False
        return out

    _base = _sim_prix_horaire(prices_df, hourly_df, price_col="prix_base")
    _peak = _sim_prix_horaire(prices_df, hourly_df, price_col="prix_peak")
    _mask_peak = _sim_is_peak_slot(hourly_df["datetime"])

    out = hourly_df.copy()
    out["is_peak_slot"] = _mask_peak.values
    out["prix_spot"] = np.where(_mask_peak.values, _peak["prix_spot"].values, _base["prix_spot"].values)
    return out


def _sim_conso_mwh(filtered_total, start, end):
    """Consommation totale (MWh) sur la période — conservé pour compatibilité."""
    h = _sim_conso_horaire(filtered_total, start, end)
    return float(h["energy_mwh"].sum()) if not h.empty else 0.0


if multi_site:
    # ── En-tête de section ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("""
<div class="section-block">
    <div class="section-heading">
        <h2>Simulation achat énergie</h2>
        <span class="section-desc">Estimez rapidement l'impact d'un achat sur votre coût d'approvisionnement</span>
    </div>
</div>""", unsafe_allow_html=True)

    if current_role != "admin":
        st.markdown('<div class="info-subtle">🔒 Réservé aux administrateurs.</div>', unsafe_allow_html=True)
    elif not all_sites_selected:
        st.markdown('<div class="info-subtle">ℹ️ Sélectionnez « Tous les sites » pour accéder à la simulation.</div>', unsafe_allow_html=True)
    else:
        _sim_source_df = all_years_total.copy() if not all_years_total.empty else filtered_total.copy()

        # ── CSS cards premium ───────────────────────────────────────────────
        st.markdown("""
<style>
.sim-card {
        text-align: left;
        font-size: 2rem;
        font-weight: 800;
        letter-spacing: 0.01em;
        color: var(--text);
        padding: 0.45rem 0.65rem;
    }
.sim-card h4 {
    margin: 0 0 .8rem;
    font-size: 1rem;
    color: var(--muted, #64748b);
    letter-spacing: .04em;
    text-transform: uppercase;
    font-weight: 600;
}
.kpi-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 1rem;
    margin: 1rem 0;
    width: 100%;
}
.kpi-grid .kpi-card {
    width: 100%;
    min-width: 0;
    height: 100%;
}
@media (max-width: 1200px) {
    .kpi-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
    }
}
@media (max-width: 768px) {
    .kpi-grid {
        grid-template-columns: 1fr;
    }
}
.kpi-box {
    flex: 1;
    min-width: 160px;
    background: var(--surface, #fff);
    border: 1px solid var(--border, #e5e7eb);
    border-radius: 14px;
    padding: 1rem 1.2rem;
    text-align: center;
    box-shadow: 0 1px 4px rgba(0,0,0,.05);
}
.kpi-box .kpi-label {
    font-size: .78rem;
    color: var(--muted, #64748b);
    margin-bottom: .3rem;
    text-transform: uppercase;
    letter-spacing: .05em;
}
.kpi-box .kpi-value { font-size: 1.5rem; font-weight: 700; color: var(--text, #1e293b); }
.kpi-box .kpi-sub { font-size: .82rem; color: var(--muted, #64748b); margin-top: .2rem; }
.verdict-card {
    border-radius: 14px;
    padding: 1.2rem 1.5rem;
    margin: 1rem 0;
    display: flex;
    align-items: center;
    gap: .8rem;
}
.verdict-text { font-size: 1.1rem; font-weight: 700; }
.verdict-detail { font-size: .88rem; opacity: .85; }
</style>
""", unsafe_allow_html=True)

        # ── Bloc 1 : Achats existants ───────────────────────────────────────
        _achats_df = load_achats()
        st.markdown('<div class="sim-card"><h4>Achats existants</h4>', unsafe_allow_html=True)
        if _achats_df.empty:
            st.caption("Aucun achat trouvé. Déposez un fichier ENEDIS_SUIVI_ACHAT_ENERGIE_*.csv dans data/raw/achats/.")
        else:
            _cols_map = {
                "TYPE_ACHAT": "Type achat",
                "FIXATION_PUISSANCE_ACHAT_MW": "MW",
                "PRIX_FIXATION": "Prix (€/MWh)",
                "DEB_PERIODE": "Début",
                "FIN_PERIODE": "Fin",
            }
            _disp_cols = {k: v for k, v in _cols_map.items() if k in _achats_df.columns}
            st.dataframe(
                _achats_df[list(_disp_cols)].rename(columns=_disp_cols).reset_index(drop=True),
                use_container_width=True,
                hide_index=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Graphique annuel état actuel (avant simulation) ───────────────

        # Extraire les années disponibles des données
        _available_years = sorted(_sim_source_df['datetime'].dt.year.unique().tolist()) if not _sim_source_df.empty else [2027]

        _current_year = pd.Timestamp.now().year
        _years_from_now = sorted([int(y) for y in _available_years if int(y) >= _current_year])
        if not _years_from_now:
            _years_from_now = [_current_year]

        _state_rows = []
        for _yr in _years_from_now:
            _y_start = pd.Timestamp(f"{_yr}-01-01")
            _y_end = pd.Timestamp(f"{_yr}-12-31 23:59:59")

            if _yr == _current_year:
                _year_hist = _all_hist[
                    (_all_hist["datetime"] >= _y_start) & (_all_hist["datetime"] <= _y_end)
                ].copy() if not _all_hist.empty else pd.DataFrame()
                _year_pred = _all_pred[
                    (_all_pred["datetime"] >= _y_start) & (_all_pred["datetime"] <= _y_end)
                ].copy() if not _all_pred.empty else pd.DataFrame()

                if not _year_hist.empty and not _year_pred.empty:
                    _hist_dtimes = set(_year_hist["datetime"].dt.floor("h"))
                    _year_pred_compl = _year_pred[~_year_pred["datetime"].dt.floor("h").isin(_hist_dtimes)]
                    _year_source = pd.concat([_year_hist, _year_pred_compl], ignore_index=True)
                elif not _year_hist.empty:
                    _year_source = _year_hist
                else:
                    _year_source = _year_pred
            else:
                _year_source = _all_pred if not _all_pred.empty else _sim_source_df

            _hourly_year = _sim_conso_horaire(_year_source, _y_start, _y_end)
            if _hourly_year.empty and not _sim_source_df.empty:
                _hourly_year = _sim_conso_horaire(_sim_source_df, _y_start, _y_end)

            _hourly_year = _sim_prix_horaire(prices_df, _hourly_year, price_col="prix_base")

            _year_conso_mwh = float(_hourly_year["energy_mwh"].sum()) if not _hourly_year.empty else 0.0
            _year_spot_moy = (
                float((_hourly_year["energy_mwh"] * _hourly_year["prix_spot"]).sum() / _year_conso_mwh)
                if (not _hourly_year.empty and _year_conso_mwh > 0)
                else 55.0
            )

            _year_achete_mwh, _year_prix_achete = purchased_components_for_period(_achats_df, _y_start, _y_end)
            _year_prix_achete = _year_prix_achete if _year_prix_achete > 0 else _year_spot_moy
            _year_achete_mwh = float(min(_year_achete_mwh, _year_conso_mwh))
            _year_restant_mwh = float(max(0.0, _year_conso_mwh - _year_achete_mwh))

            _year_cout_achete = float(_year_achete_mwh * _year_prix_achete)
            if not _hourly_year.empty and _year_conso_mwh > 0:
                _ratio_achete_year = float(min(max(_year_achete_mwh / _year_conso_mwh, 0.0), 1.0))
                _mwh_restant_year_h = _hourly_year["energy_mwh"] * (1.0 - _ratio_achete_year)
                _year_cout_restant = float((_mwh_restant_year_h * _hourly_year["prix_spot"]).sum())
            else:
                _year_cout_restant = float(_year_restant_mwh * _year_spot_moy)

            _state_rows.append({
                "year": _yr,
                "achete_mwh": _year_achete_mwh,
                "restant_mwh": _year_restant_mwh,
                "cout_achete_eur": _year_cout_achete,
                "cout_restant_eur": _year_cout_restant,
            })

        _state_yearly_df = pd.DataFrame(_state_rows).sort_values("year").reset_index(drop=True)

        st.plotly_chart(
            fig_current_state_yearly_bar(_state_yearly_df, _current_year),
            use_container_width=True,
            key="chart_current_state_yearly_bar_1",
        )

        # ── Bloc 2 : Période simulée ────────────────────────────────────────
        st.markdown('<div class="sim-card"><h4>Période simulée</h4>', unsafe_allow_html=True)


        # Choix du type de période
        _col_type_period = st.columns(2)
        with _col_type_period[0]:
            _period_type = st.radio(
                "Type de période",
                ["Année complète", "Période personnalisée"],
                horizontal=True,
                key="sim_period_type"
            )

        if _period_type == "Année complète":
            # Mode année complète
            with _col_type_period[1]:
                _selected_year = st.selectbox(
                    "Année",
                    options=_available_years,
                    index=len(_available_years) - 1,
                    key="sim_s_year"
                )
            _sim_start = pd.Timestamp(f"{_selected_year}-01-01")
            _sim_end = pd.Timestamp(f"{_selected_year}-12-31 23:59:59")
        else:
            # Mode période personnalisée avec slider par mois
            _min_date = pd.Timestamp(_sim_source_df['datetime'].min()) if not _sim_source_df.empty else pd.Timestamp("2025-01-01")
            _max_date = pd.Timestamp(_sim_source_df['datetime'].max()) if not _sim_source_df.empty else pd.Timestamp("2027-12-31")

            # Convertir en nombre de mois depuis une référence
            _ref_date = pd.Timestamp("2020-01-01")
            _min_months = (_min_date.year - _ref_date.year) * 12 + (_min_date.month - _ref_date.month)
            _max_months = (_max_date.year - _ref_date.year) * 12 + (_max_date.month - _ref_date.month)
            _default_start = _min_months
            _default_end = _max_months

            # Créer un dictionnaire pour afficher les labels mois/année
            _month_labels = {}
            for m in range(_min_months, _max_months + 1):
                _year = _ref_date.year + m // 12
                _month = (_ref_date.month + m % 12 - 1) % 12 + 1
                _month_labels[m] = pd.Timestamp(f"{_year}-{_month:02d}-01").strftime("%b %Y")

            _selected_range = st.select_slider(
                "Période (mois)",
                options=list(range(_min_months, _max_months + 1)),
                value=(_default_start, _default_end),
                format_func=lambda x: _month_labels.get(x, str(x)),
                key="sim_period_slider"
            )
            # Convertir les mois en dates
            _start_months = _selected_range[0]
            _end_months = _selected_range[1]
            _start_year = _ref_date.year + _start_months // 12
            _start_month = (_ref_date.month + _start_months % 12 - 1) % 12 + 1
            _end_year = _ref_date.year + _end_months // 12
            _end_month = (_ref_date.month + _end_months % 12 - 1) % 12 + 1

            _sim_start = pd.Timestamp(f"{_start_year}-{_start_month:02d}-01")
            _sim_end = (pd.Timestamp(f"{_end_year}-{_end_month:02d}-01") + pd.DateOffset(months=1)) - pd.Timedelta(seconds=1)

            # Afficher la plage sélectionnée
            _range_display = f"{_sim_start.strftime('%B %Y')} → {_sim_end.strftime('%B %Y')}"
            st.caption(f"Période : {_range_display}")

        st.markdown('</div>', unsafe_allow_html=True)


        # ── Bloc 3 : Paramètres de simulation ──────────────────────────────
        st.markdown('<div class="sim-card"><h4>Simulation</h4>', unsafe_allow_html=True)
        _fc1, _fc2, _fc3, _fc4 = st.columns([1, 1, 1, 1])
        with _fc1:
            _sim_type = st.selectbox("Type achat", ["Base", "Peak"], key="sim_s_type")
        with _fc2:
            _sim_sens = st.radio("Sens", ["Achat", "Vente"], horizontal=True, key="sim_s_sens")
        with _fc3:
            _sim_vol = st.number_input(
                "Volume (MW)", min_value=0.0, value=1.0, step=0.5, format="%.1f", key="sim_s_vol"
            )
        with _fc4:
            _sim_prix = st.number_input(
                "Prix (€/MWh)", min_value=0.0, value=52.5, step=0.5, format="%.2f", key="sim_s_prix"
            )
        st.markdown('</div>', unsafe_allow_html=True)

        # ── Bouton unique ───────────────────────────────────────────────────
        _btn = st.button("▶ Faire simulation", type="primary", key="sim_s_run")

        if _btn:
            _n_jours  = max(1, (_sim_end - _sim_start).days + 1)
            # ════════════════════════════════════════════════════════════
            # GRAPHIQUE COMPARATIF  «En l'état» vs «Simulé»
            # Source de vérité :
            #   conso totale  = prévisions LSTM sur la période
            #   vol acheté    = CSV Enedis (MW × heures)
            #   prix acheté   = moyenne pondérée des prix fixes CSV
            #   restant spot  = conso prédite − vol acheté
            # ════════════════════════════════════════════════════════════

            # 1. Consommation PRÉDITE — source exclusive : preds_df (LSTM)
            #    On ne mélange PAS l'historique : pour une année future comme
            #    2027, le total de la barre doit refléter exactement ce que
            #    le modèle prédit, indépendamment des données réelles passées.
            _hourly_pred = _sim_conso_horaire(_all_pred, _sim_start, _sim_end)
            _hourly_pred_spot = _sim_prix_horaire_selon_type(prices_df, _hourly_pred, _sim_type)
            _hourly_pred_plot = _hourly_pred.copy()
            if _hourly_pred_plot.empty:
                _hourly_fallback = _sim_conso_horaire(_sim_source_df, _sim_start, _sim_end)
                _hourly_pred_plot = _hourly_fallback.copy()
            if _hourly_pred_spot.empty:
                _hourly_pred_spot = _sim_prix_horaire_selon_type(prices_df, _hourly_pred_plot, _sim_type)

            if _sim_type == "Peak" and not _hourly_pred_spot.empty and "is_peak_slot" in _hourly_pred_spot.columns:
                _n_heures = int(_hourly_pred_spot["is_peak_slot"].sum())
            else:
                _n_heures = len(_hourly_pred_spot)
            _conso_predite_mwh = (
                float(_hourly_pred_spot["energy_mwh"].sum())
                if not _hourly_pred_spot.empty
                else 0.0
            )
            if not _hourly_pred_spot.empty and _conso_predite_mwh > 0:
                _spot_moy = float(
                    (_hourly_pred_spot["energy_mwh"] * _hourly_pred_spot["prix_spot"]).sum()
                    / _conso_predite_mwh
                )
            elif not _hourly_pred_spot.empty:
                _spot_moy = float(_hourly_pred_spot["prix_spot"].mean())
            else:
                _spot_moy = 55.0

            # KPI Conso prédite : sur année en cours, compléter avec historique réel
            _conso_kpi_mwh = _conso_predite_mwh
            if _sim_start.year <= _current_year <= _sim_end.year:
                _hourly_hist = _sim_conso_horaire(_all_hist, _sim_start, _sim_end)

                if not _hourly_hist.empty:
                    _hist_hours = set(_hourly_hist["datetime"])
                    _pred_wo_hist = _hourly_pred_spot.loc[
                        ~_hourly_pred_spot["datetime"].isin(_hist_hours)
                    ].copy() if not _hourly_pred_spot.empty else pd.DataFrame()
                    _conso_kpi_mwh = float(_hourly_hist["energy_mwh"].sum())
                    if not _pred_wo_hist.empty:
                        _conso_kpi_mwh += float(_pred_wo_hist["energy_mwh"].sum())

            # 2. Achats déjà effectués sur la période (depuis CSV Enedis)
            _vol_achete_mwh, _prix_moy_achete = purchased_components_for_period(
                _achats_df, _sim_start, _sim_end
            )
            # Fallback : si le CSV ne donne pas de coût, utiliser le spot moyen
            _prix_moy_achete = _prix_moy_achete if _prix_moy_achete > 0 else _spot_moy
            # Plafonner le volume acheté à la consommation prédite
            _vol_achete_mwh = min(_vol_achete_mwh, _conso_predite_mwh)

            # 3. Situation «En l'état»
            #    orange = déjà acheté   |   gris = restant au spot
            _en_etat_achete_mwh   = _vol_achete_mwh
            _en_etat_restant_mwh  = max(0.0, _conso_predite_mwh - _en_etat_achete_mwh)
            _en_etat_cout_achete  = _en_etat_achete_mwh  * _prix_moy_achete
            if not _hourly_pred_spot.empty and _conso_predite_mwh > 0:
                _ratio_achete = _en_etat_achete_mwh / _conso_predite_mwh
                _ratio_achete = float(min(max(_ratio_achete, 0.0), 1.0))
                _mwh_restant_en_etat_h = _hourly_pred_spot["energy_mwh"] * (1.0 - _ratio_achete)
                _en_etat_cout_restant = float((_mwh_restant_en_etat_h * _hourly_pred_spot["prix_spot"]).sum())
            else:
                _en_etat_cout_restant = _en_etat_restant_mwh * _spot_moy

            # 4. Situation «Simulée»
            #    Volume simulé = MW saisis × nombre d'heures de la période.
            _vol_simule_mwh = _sim_vol * _n_heures   # MW → MWh
            _simule_nouvel_mwh = 0.0
            _simule_vendu_mwh = 0.0

            if _sim_sens == "Achat":
                # Achat additionnel plafonné au restant non couvert.
                _simule_nouvel_mwh = min(_vol_simule_mwh, _en_etat_restant_mwh)
                _simule_achete_mwh = _en_etat_achete_mwh
            else:
                # Vente plafonnée au volume déjà acheté.
                _simule_vendu_mwh = min(_vol_simule_mwh, _en_etat_achete_mwh)
                _simule_achete_mwh = max(0.0, _en_etat_achete_mwh - _simule_vendu_mwh)

            _simule_restant_mwh = max(0.0, _conso_predite_mwh - _simule_achete_mwh - _simule_nouvel_mwh)
            _simule_cout_achete = _simule_achete_mwh * _prix_moy_achete
            _simule_cout_nouvel = _simule_nouvel_mwh * _sim_prix
            _simule_revenu_vente = _simule_vendu_mwh * _sim_prix

            if not _hourly_pred_spot.empty and _conso_predite_mwh > 0:
                _ratio_couvert_simule = (_simule_achete_mwh + _simule_nouvel_mwh) / _conso_predite_mwh
                _ratio_couvert_simule = float(min(max(_ratio_couvert_simule, 0.0), 1.0))
                _mwh_spot_simule_h = _hourly_pred_spot["energy_mwh"] * (1.0 - _ratio_couvert_simule)
                _simule_cout_restant = float((_mwh_spot_simule_h * _hourly_pred_spot["prix_spot"]).sum())
            else:
                _simule_cout_restant = _simule_restant_mwh * _spot_moy

            # 5. Graphique
            st.markdown("---")

                        # 6. Récapitulatif textuel
            _total_en_etat = _en_etat_cout_achete + _en_etat_cout_restant
            _total_simule  = _simule_cout_achete + _simule_cout_nouvel + _simule_cout_restant - _simule_revenu_vente
            _gain_sim      = _total_en_etat - _total_simule
            _gain_color = "#10B981" if _gain_sim > 0 else "#EF4444"
            _gain_label = "économie" if _gain_sim > 0 else "surcoût"

            # ── KPI cards (3 KPI) alignées avec le graphique ─────────────
            _periode_lbl = f"{_sim_start.strftime('%d/%m/%Y')} → {_sim_end.strftime('%d/%m/%Y')}"
            _ecart_cout = _total_simule - _total_en_etat
            _ecart_pct = (_ecart_cout / _total_en_etat * 100.0) if _total_en_etat > 0 else 0.0
            _kpi_ecart_color = (
                "#10B981" if _ecart_cout < -500 else
                "#EF4444" if _ecart_cout > 500 else
                "#F59E0B"
            )
            _ecart_symbol = "▼" if _ecart_cout < -500 else ("▲" if _ecart_cout > 500 else "■")
            _conso_sub = "Historique + prévisions (année en cours)" if _sim_start.year <= _current_year <= _sim_end.year else "Prévisions sur la période"

            st.markdown(f"""
<div class="kpi-grid">
    <div class="kpi-card kpi-gray">
        <div class="kpi-label">Période</div>
        <div class="kpi-value" style="font-size:1.05rem">{_periode_lbl}</div>
        <div class="kpi-sub">&nbsp;</div>
    </div>
    <div class="kpi-card kpi-blue">
        <div class="kpi-label">Conso prédite</div>
        <div class="kpi-value">{format_int_space(_conso_kpi_mwh)} MWh</div>
        <div class="kpi-sub">{_conso_sub}</div>
    </div>
    <div class="kpi-card kpi-amber">
        <div class="kpi-label">Coûts</div>
        <div class="kpi-value" style="font-size:1.15rem">Avant : {_total_en_etat/1e3:,.1f} k€</div>
        <div class="kpi-value" style="font-size:1.15rem">Après : {_total_simule/1e3:,.1f} k€</div>
        <div class="kpi-sub"><span style="color:{_kpi_ecart_color}; font-weight:600">{_ecart_symbol} {_ecart_cout/1e3:+,.1f} k€ ({_ecart_pct:+.1f}%)</span></div>
    </div>
</div>
""", unsafe_allow_html=True)

            st.plotly_chart(
                fig_simulation_purchase_comparison(
                    en_etat_achete_mwh           = _en_etat_achete_mwh,
                    en_etat_restant_mwh          = _en_etat_restant_mwh,
                    simule_achete_mwh            = _simule_achete_mwh,
                    simule_nouvel_achat_mwh      = _simule_nouvel_mwh,
                    simule_vendu_mwh             = _simule_vendu_mwh,
                    simule_restant_mwh           = _simule_restant_mwh,
                    en_etat_cout_achete_eur      = _en_etat_cout_achete,
                    en_etat_cout_restant_eur     = _en_etat_cout_restant,
                    simule_cout_achete_eur       = _simule_cout_achete,
                    simule_cout_nouvel_achat_eur = _simule_cout_nouvel,
                    simule_revenu_vente_eur      = _simule_revenu_vente,
                    simule_cout_restant_eur      = _simule_cout_restant,
                ),
                use_container_width=True,
            key="chart_simulation_purchase_comparison_1",
        )

            _operation_label = "Achat simulé" if _sim_sens == "Achat" else "Vente simulée"
            _operation_volume = _simule_nouvel_mwh if _sim_sens == "Achat" else _simule_vendu_mwh
            st.markdown(
                f"<div style='text-align:center; font-size:.9rem; color:{_gain_color}; margin-top:-.5rem;'>"
                f"{'▼' if _gain_sim > 0 else '▲'} "
                f"<b>{abs(_gain_sim)/1e3:,.1f} k€ de {_gain_label}</b> "
                f"par rapport à la situation en l'état&nbsp;·&nbsp;"
                f"Conso prédite : <b>{format_int_space(_conso_kpi_mwh)} MWh</b>&nbsp;·&nbsp;"
                f"Déjà acheté : <b>{format_int_space(_vol_achete_mwh)} MWh</b> @ <b>{_prix_moy_achete:.2f} €/MWh</b>&nbsp;·&nbsp;"
                f"{_operation_label} : <b>{format_int_space(_operation_volume)} MWh</b> @ <b>{_sim_prix:.2f} €/MWh</b>&nbsp;·&nbsp;"
                f"Spot futur : <b>{_spot_moy:.2f} €/MWh</b>"
                f"</div>",
                unsafe_allow_html=True,
            )