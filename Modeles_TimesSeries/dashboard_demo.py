"""
Dashboard Streamlit — VERSION DÉMO (lecture depuis CSV locaux).

Structure attendue :
    data/
    ├── predictions/          *.csv  (colonnes : datetime, prm, puissance_kw  OU  puissance_kw_pred  OU  puissance_moy_heure_pred)
    ├── processed/            data_processed_*.csv  (colonnes : datetime, prm, puissance_moy_heure)
    └── raw/
        ├── prix/             prix_spot.csv  (colonnes : date_deb, date_fin, prix_base, prix_peak, type)
        └── sites/            table_sites.csv  (colonnes : prm, ville, [id_site])

Métriques modèle : lues depuis mlruns/ (MLflow) si présent, sinon non affichées.
Authentification : SQLite local (admin/admin123, lecteur/lecteur123).
"""

from __future__ import annotations

import hashlib
import hmac
import re
import sqlite3
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st


# ══════════════════════════════════════════════════════════════════════════════
# CHEMINS
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR      = Path(__file__).resolve().parent
DATA_DIR      = BASE_DIR / "data"
PRED_DIR      = DATA_DIR / "predictions"
PROCESSED_DIR = DATA_DIR / "processed"
SITES_FILE    = DATA_DIR / "raw" / "sites" / "table_sites.csv"
PRICE_FILE    = DATA_DIR / "raw" / "prix"  / "prix_spot.csv"
MLRUNS_DIR    = BASE_DIR / "mlruns"
USERS_DB_FILE = BASE_DIR / "users_demo.db"


# ══════════════════════════════════════════════════════════════════════════════
# UTILITAIRES
# ══════════════════════════════════════════════════════════════════════════════

def _extract_prm_from_name(filename: str) -> str | None:
    """Extrait un PRM (suite de 8+ chiffres) depuis un nom de fichier."""
    match = re.search(r"(\d{8,})", filename)
    return match.group(1) if match else None


# ══════════════════════════════════════════════════════════════════════════════
# CHARGEMENT DES DONNÉES
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_sites() -> pd.DataFrame:
    """Charge la table des sites depuis data/raw/sites/table_sites.csv."""
    if not SITES_FILE.exists():
        st.warning(f"Fichier sites introuvable : {SITES_FILE}")
        return pd.DataFrame(columns=["prm", "ville", "id_site", "site_label"])

    try:
        df = pd.read_csv(SITES_FILE)
        df["prm"] = df["prm"].astype(str)

        if "ville" not in df.columns:
            df["ville"] = "Inconnu"
        if "id_site" not in df.columns:
            df["id_site"] = ""

        df["site_label"] = df["ville"].astype(str) + " (" + df["prm"] + ")"
        return df
    except Exception as e:
        st.error(f"Erreur lecture sites : {e}")
        return pd.DataFrame(columns=["prm", "ville", "id_site", "site_label"])


@st.cache_data
def load_predictions() -> pd.DataFrame:
    """
    Charge les prévisions depuis data/predictions/*.csv.

    Colonnes acceptées pour la puissance (par ordre de priorité) :
        puissance_kw  |  puissance_kw_pred  |  puissance_moy_heure_pred (W → kW)
    """
    if not PRED_DIR.exists():
        st.warning(f"Dossier predictions introuvable : {PRED_DIR}")
        return pd.DataFrame()

    csv_files = sorted(PRED_DIR.glob("*.csv"))
    if not csv_files:
        st.warning(f"Aucun CSV dans {PRED_DIR}")
        return pd.DataFrame()

    frames = []
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            st.warning(f"Impossible de lire {filepath.name} : {e}")
            continue

        if "datetime" not in df.columns:
            st.warning(f"{filepath.name} : colonne 'datetime' manquante, fichier ignoré.")
            continue

        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"])

        # PRM : depuis la colonne ou depuis le nom de fichier
        if "prm" not in df.columns:
            prm = _extract_prm_from_name(filepath.name)
            if prm is None:
                st.warning(f"{filepath.name} : impossible d'extraire le PRM, fichier ignoré.")
                continue
            df["prm"] = prm

        # Normalisation de la puissance en kW
        if "puissance_kw" not in df.columns:
            if "puissance_kw_pred" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance_kw_pred"], errors="coerce")
            elif "puissance_moy_heure_pred" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance_moy_heure_pred"], errors="coerce") / 1_000
            else:
                st.warning(f"{filepath.name} : aucune colonne de puissance reconnue, fichier ignoré.")
                continue
        else:
            df["puissance_kw"] = pd.to_numeric(df["puissance_kw"], errors="coerce")

        frames.append(df[["prm", "datetime", "puissance_kw"]].copy())

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["prm"]       = out["prm"].astype(str)
    out["data_type"] = "Prévision"

    sites_map = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_map, on="prm", how="left")
    out["site_label"] = out["site_label"].fillna("PRM " + out["prm"])
    return out


@st.cache_data
def load_historical_data() -> pd.DataFrame:
    """
    Charge l'historique depuis data/processed/data_processed_*.csv.

    Colonnes acceptées pour la puissance (par ordre de priorité) :
        puissance_kw  |  puissance_moy_heure (W → kW)  |  puissance (W → kW)
    """
    if not PROCESSED_DIR.exists():
        st.warning(f"Dossier processed introuvable : {PROCESSED_DIR}")
        return pd.DataFrame()

    csv_files = sorted(PROCESSED_DIR.glob("data_processed_*.csv"))
    if not csv_files:
        csv_files = sorted(PROCESSED_DIR.glob("*.csv"))

    if not csv_files:
        st.warning(f"Aucun CSV dans {PROCESSED_DIR}")
        return pd.DataFrame()

    frames = []
    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath)
        except Exception as e:
            st.warning(f"Impossible de lire {filepath.name} : {e}")
            continue

        if "datetime" not in df.columns:
            st.warning(f"{filepath.name} : colonne 'datetime' manquante, fichier ignoré.")
            continue

        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
        df = df.dropna(subset=["datetime"])

        # PRM
        if "prm" not in df.columns:
            prm = _extract_prm_from_name(filepath.name)
            if prm is None:
                st.warning(f"{filepath.name} : impossible d'extraire le PRM, fichier ignoré.")
                continue
            df["prm"] = prm

        # Normalisation puissance en kW
        if "puissance_kw" not in df.columns:
            if "puissance_moy_heure" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance_moy_heure"], errors="coerce") / 1_000
            elif "puissance" in df.columns:
                df["puissance_kw"] = pd.to_numeric(df["puissance"], errors="coerce") / 1_000
            else:
                st.warning(f"{filepath.name} : aucune colonne de puissance reconnue, fichier ignoré.")
                continue
        else:
            df["puissance_kw"] = pd.to_numeric(df["puissance_kw"], errors="coerce")

        frames.append(df[["prm", "datetime", "puissance_kw"]].copy())

    if not frames:
        return pd.DataFrame()

    out = pd.concat(frames, ignore_index=True)
    out["prm"]       = out["prm"].astype(str)
    out["data_type"] = "Historique"

    sites_map = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_map, on="prm", how="left")
    out["site_label"] = out["site_label"].fillna("PRM " + out["prm"])
    return out


@st.cache_data
def load_prices() -> pd.DataFrame:
    """Charge les prix spot depuis data/raw/prix/prix_spot.csv."""
    if not PRICE_FILE.exists():
        st.warning(f"Fichier prix introuvable : {PRICE_FILE}")
        return pd.DataFrame()

    try:
        df = pd.read_csv(PRICE_FILE)
    except Exception as e:
        st.error(f"Erreur lecture prix : {e}")
        return pd.DataFrame()

    for col in ("date_deb", "date_fin"):
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    df["prix_base"] = pd.to_numeric(df.get("prix_base"), errors="coerce")
    df["prix_peak"] = pd.to_numeric(df.get("prix_peak"), errors="coerce")

    if "type" not in df.columns:
        df["type"] = "mensuel"

    return df


# ══════════════════════════════════════════════════════════════════════════════
# MÉTRIQUES MLFLOW
# ══════════════════════════════════════════════════════════════════════════════

@st.cache_data
def load_mlflow_metrics(prm: str) -> dict | None:
    """Cherche dans mlruns/ le run correspondant au PRM et retourne ses métriques."""
    if not MLRUNS_DIR.exists():
        return None

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
            if prm_file.read_text().strip() != prm:
                continue

            metrics: dict = {}
            for metric in metric_names:
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
        in_range    = merged["datetime"] <= merged["date_fin"]
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
    plot_df = df.copy()
    if aggregate:
        group_cols = ["datetime", "data_type"] if "data_type" in plot_df.columns else ["datetime"]
        plot_df = plot_df.groupby(group_cols, as_index=False)["puissance_kw"].sum()
        plot_df["legend"] = (
            "Total - " + plot_df["data_type"] if "data_type" in plot_df.columns else "Total"
        )
        title = "Courbes de consommation totale — tous sites (kW)"
    else:
        plot_df["legend"] = (
            plot_df["site_label"] + " - " + plot_df["data_type"]
            if "data_type" in plot_df.columns
            else plot_df["site_label"]
        )
        title = "Courbes de consommation (kW)"

    fig = px.line(
        plot_df, x="datetime", y="puissance_kw", color="legend",
        title=title,
        labels={"puissance_kw": "Puissance (kW)", "datetime": "Date", "legend": "Série"},
    )
    fig.update_layout(height=min(max(400, 300 + len(plot_df) * 0.01), 800))
    return fig


def build_yearly_consumption_histogram(df: pd.DataFrame) -> px.bar:
    plot_df = df.copy()
    plot_df["year_str"] = plot_df["datetime"].dt.year.astype(str)
    yearly = plot_df.groupby(["year_str", "site_label"], as_index=False)["puissance_kw"].sum()
    yearly = yearly.rename(columns={"puissance_kw": "Consommation (kWh)"})
    fig = px.bar(
        yearly, x="year_str", y="Consommation (kWh)", color="site_label",
        barmode="group", title="Consommations annuelles par site",
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
# APPLICATION
# ══════════════════════════════════════════════════════════════════════════════

st.set_page_config(layout="wide", page_title="Conso Energ Dashboard — Démo CSV")

init_users_db()

# ── Session state ─────────────────────────────────────────────────────────────
for key, default in [("authenticated", False), ("username", ""), ("role", "")]:
    if key not in st.session_state:
        st.session_state[key] = default

# ── Login ─────────────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    st.title("Identification")
    st.caption("Connectez-vous pour accéder au dashboard")
    st.info("Comptes de test : admin / admin123  et  lecteur / lecteur123")

    with st.form("login_form", clear_on_submit=False):
        username_input = st.text_input("Nom d'utilisateur")
        password_input = st.text_input("Mot de passe", type="password")
        submitted = st.form_submit_button("Se connecter")

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

current_username = st.session_state.username
current_role     = st.session_state.role

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.success(f"Connecté : {current_username} ({current_role})")
if st.sidebar.button("Se déconnecter"):
    for k in ("authenticated", "username", "role"):
        st.session_state[k] = False if k == "authenticated" else ""
    st.rerun()

if current_role == "admin":
    with st.sidebar.expander("Gestion des utilisateurs", expanded=False):
        with st.form("create_user_form", clear_on_submit=True):
            new_username = st.text_input("Nouveau nom d'utilisateur")
            new_password = st.text_input("Nouveau mot de passe", type="password")
            new_role     = st.selectbox("Rôle", ["admin", "lecteur"])
            if st.form_submit_button("Créer l'utilisateur"):
                ok, msg = create_user(new_username, new_password, new_role)
                (st.success if ok else st.error)(msg)

# ── Chargement ────────────────────────────────────────────────────────────────
st.title("Dashboard prévisions conso et prix")

progress = st.progress(0,  text="Chargement (0/4) : sites...")
sites_df  = load_sites()
progress.progress(25, text="Chargement (1/4) : prix...")
prices_df = load_prices()
progress.progress(50, text="Chargement (2/4) : prédictions...")
preds_df  = load_predictions()
progress.progress(75, text="Chargement (3/4) : historique...")
hist_df   = load_historical_data()
progress.progress(100, text="Chargement terminé.")
progress.empty()

# ── Vérifications minimales ───────────────────────────────────────────────────
if preds_df.empty:
    st.warning(
        f"Aucune prédiction chargée. Vérifiez que `{PRED_DIR}` contient des fichiers CSV "
        "avec les colonnes `datetime` et `puissance_kw` (ou `puissance_kw_pred` ou `puissance_moy_heure_pred`)."
    )
    st.stop()

if "puissance_kw" not in preds_df.columns:
    st.error("Colonne puissance_kw manquante dans les prédictions.")
    st.stop()

# Garantir site_label sur tous les DataFrames
for df_ in (preds_df, hist_df):
    if df_.empty:
        continue
    if "site_label" not in df_.columns:
        df_["site_label"] = "PRM " + df_["prm"].astype(str)
    else:
        df_["site_label"] = df_["site_label"].fillna("PRM " + df_["prm"].astype(str))

# ── Filtres sidebar ───────────────────────────────────────────────────────────
min_date_pred = preds_df["datetime"].min()
max_date_pred = preds_df["datetime"].max()

st.sidebar.header("Filtres")
site_options = sorted(preds_df["site_label"].unique())

selected_site_filter = st.sidebar.selectbox(
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

show_historical = st.sidebar.checkbox("Afficher l'historique", value=False)

global_min = (
    hist_df["datetime"].min()
    if (show_historical and not hist_df.empty)
    else min_date_pred
)
start_date = st.sidebar.date_input("Date début", value=global_min.date())
end_date   = st.sidebar.date_input("Date fin",   value=max_date_pred.date())

# ── Filtrage ──────────────────────────────────────────────────────────────────
def _date_mask(df: pd.DataFrame) -> pd.Series:
    return (
        df["site_label"].isin(selected_sites)
        & (df["datetime"] >= pd.to_datetime(start_date))
        & (df["datetime"] <= pd.to_datetime(end_date))
    )

filtered = preds_df.loc[_date_mask(preds_df)].copy()

if show_historical and not hist_df.empty:
    filtered_hist = hist_df.loc[_date_mask(hist_df)].copy()
    if not filtered_hist.empty:
        filtered = pd.concat([filtered, filtered_hist], ignore_index=True)

if filtered.empty:
    st.warning("Aucune donnée après filtrage.")
    st.stop()

# ── Contenu principal ─────────────────────────────────────────────────────────
multi_site = len(selected_sites) > 1

if multi_site:
    st.subheader("Répartition de la consommation par site")
    st.plotly_chart(build_consumption_pie(filtered), use_container_width=True)

elif len(selected_sites) == 1:
    st.subheader("Qualité du modèle")
    single_prm     = preds_df.loc[preds_df["site_label"] == selected_sites[0], "prm"].iloc[0]
    mlflow_metrics = load_mlflow_metrics(single_prm)

    if mlflow_metrics:
        mae  = mlflow_metrics.get("val_mae")
        rmse = mlflow_metrics.get("val_rmse")
        mape = mlflow_metrics.get("val_mape")
        r2   = mlflow_metrics.get("val_r2")

        m_cols = st.columns(4)
        m_cols[0].metric("MAE (W)",  f"{mae:,.0f}"   if mae  is not None else "N/A",
            help="Erreur absolue moyenne (W). Plus basse = meilleur.")
        m_cols[1].metric("RMSE (W)", f"{rmse:,.0f}"  if rmse is not None else "N/A",
            help="Erreur quadratique moyenne (W). Pénalise les grands écarts.")
        m_cols[2].metric("MAPE (%)", f"{mape:.1f} %" if mape is not None else "N/A",
            help="Erreur relative moyenne. < 20 % = bon.")
        m_cols[3].metric("R²",       f"{r2:.3f}"     if r2   is not None else "N/A",
            help="Part de variance expliquée. > 0.80 = bon, 1.0 = parfait.")

        with st.expander("ℹ️ Comment interpréter ces métriques ?"):
            st.markdown("""
| Métrique | Description | Idéal |
|---|---|---|
| **MAE** | Erreur absolue moyenne (W). Écart typique entre prédiction et réalité. | La plus basse possible |
| **RMSE** | Erreur quadratique moyenne (W). Amplifie les grandes erreurs. | La plus basse possible |
| **MAPE** | Erreur relative (%). Indépendante de l'échelle. | < 20 % |
| **R²** | Part de la variance expliquée par le modèle. 1 = parfait. | > 0.80 |
""")
    else:
        st.info("Aucune métrique MLflow trouvée pour ce site (dossier `mlruns/` absent ou run non trouvé).")

st.subheader("Consommation dans le temps")
st.plotly_chart(build_consumption_curve(filtered, aggregate=multi_site), use_container_width=True)
st.plotly_chart(build_yearly_consumption_histogram(filtered), use_container_width=True)

# ── Prix ──────────────────────────────────────────────────────────────────────
if prices_df.empty:
    st.warning("Aucune donnée de prix disponible.")
else:
    price_priority = ["mensuel", "trimestriel", "annuel"]
    monthly_prices = build_monthly_price_series(
        prices_df,
        pd.to_datetime(start_date),
        pd.to_datetime(end_date),
        price_priority,
    )

    st.subheader("Prix futur dans le temps")

    if not monthly_prices.empty:
        monthly_long = monthly_prices.melt(
            id_vars="month",
            value_vars=["prix_base", "prix_peak"],
            var_name="type_prix",
            value_name="prix",
        )
        monthly_long["type_prix"] = monthly_long["type_prix"].map(
            {"prix_base": "Base", "prix_peak": "Peak"}
        )
        fig_prices = px.line(
            monthly_long.dropna(subset=["prix"]),
            x="month", y="prix", color="type_prix", markers=True,
            title="Évolution prix spot base vs peak",
            labels={"month": "Mois", "prix": "Prix (EUR/MWh)", "type_prix": "Type"},
        )
        fig_prices.update_layout(height=max(300, 250 + len(monthly_prices) * 15))
        st.plotly_chart(fig_prices, use_container_width=True)
    else:
        st.info("Aucun prix disponible sur la plage de dates sélectionnée.")

st.divider()

# ── Simulation achat base/peak ────────────────────────────────────────────────
if current_role != "admin":
    st.info("Mode lecteur : la simulation achat base/peak est réservée aux administrateurs.")
elif not all_sites_selected:
    st.info("La simulation est disponible uniquement avec le filtre 'Tous les sites'.")
elif prices_df.empty:
    st.warning("Simulation impossible sans données de prix.")
else:
    st.subheader("Simulation achat base/peak")

    sim_df = filtered.groupby("datetime", as_index=False)["puissance_kw"].sum()
    if sim_df.empty:
        st.info("Aucune donnée disponible pour la simulation tous sites.")
        st.stop()

    with st.expander("Paramètres de simulation", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            base_volume     = st.number_input("Volume base acheté (kW)", min_value=0.0, value=500.0, step=10.0)
            peak_volume     = st.number_input("Volume peak acheté (kW)", min_value=0.0, value=200.0, step=10.0)
            peak_start      = st.slider("Heure début peak", min_value=0, max_value=23, value=8)
            peak_end        = st.slider("Heure fin peak",   min_value=0, max_value=23, value=20)
        with col2:
            include_weekend = st.checkbox("Inclure weekend en peak", value=False)
            turpe_kwh       = st.number_input("TURPE (EUR/kWh)",         min_value=0.0, value=0.0, step=0.001, format="%.3f")
            tax_rate        = st.number_input("Taxes (taux, ex: 0.20)", min_value=0.0, value=0.0, step=0.01,  format="%.2f")

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
    sim_df["spot_price"]    = np.where(is_peak, sim_df["price_peak"], sim_df["price_base"])
    sim_df["spot_cost_eur"] = (
        (sim_df["puissance_kw"] - sim_df["purchased_kw"]) * sim_df["spot_price"] / 1_000
    )
    sim_df["energy_cost_eur"] = sim_df["contract_cost_eur"] + sim_df["spot_cost_eur"]
    sim_df["turpe_eur"]       = sim_df["puissance_kw"] * turpe_kwh
    sim_df["subtotal_eur"]    = sim_df["energy_cost_eur"] + sim_df["turpe_eur"]
    sim_df["taxes_eur"]       = sim_df["subtotal_eur"] * tax_rate
    sim_df["total_eur"]       = sim_df["subtotal_eur"] + sim_df["taxes_eur"]

    total_kwh  = sim_df["puissance_kw"].sum()
    energy_eur = sim_df["energy_cost_eur"].sum()
    total_eur  = sim_df["total_eur"].sum()
    avg_price  = total_eur / (total_kwh / 1_000) if total_kwh > 0 else 0.0

    kpis = st.columns(4)
    kpis[0].metric("Conso totale (kWh)",   f"{total_kwh:,.0f}")
    kpis[1].metric("Coût énergie (EUR)",   f"{energy_eur:,.0f}")
    kpis[2].metric("Coût total (EUR)",     f"{total_eur:,.0f}")
    kpis[3].metric("Prix moyen (EUR/MWh)", f"{avg_price:.2f}")

    cost_cols = st.columns(2)
    with cost_cols[0]:
        fig_cost = px.line(sim_df, x="datetime", y="total_eur", title="Coût horaire total")
        fig_cost.update_layout(height=min(max(400, 300 + len(sim_df) * 0.01), 800))
        st.plotly_chart(fig_cost, use_container_width=True)

    with cost_cols[1]:
        sim_df["total_cum_eur"] = sim_df["total_eur"].cumsum()
        fig_cum = px.line(sim_df, x="datetime", y="total_cum_eur", title="Coût cumulé")
        fig_cum.update_layout(height=min(max(400, 300 + len(sim_df) * 0.01), 800))
        st.plotly_chart(fig_cum, use_container_width=True)