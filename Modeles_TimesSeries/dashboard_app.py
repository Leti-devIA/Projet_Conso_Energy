"""
Dashboard Streamlit du projet Prophet (version pédagogique).

Objectif : permettre à un étudiant de visualiser simplement :
- l'historique et les prévisions,
- la qualité du modèle (métriques MLflow),
- un scénario de coût énergie (base/peak).
"""

from __future__ import annotations

from pathlib import Path
import hashlib
import hmac
import re
import sqlite3
import os

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st
import httpx


# ── Configuration API ──────────────────────────────────────────────────────────
API_INFERENCE_URL = os.getenv("API_INFERENCE_URL", "http://localhost:8001")
API_DATACLEAN_URL = os.getenv("API_DATACLEAN_URL", "http://localhost:8000")
API_KEY = os.getenv("API_KEY", "dev-inference-key")  # Clé par défaut pour dev


# ── Chemins projet ─────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
PRED_DIR = DATA_DIR / "predictions"
PROCESSED_DIR = DATA_DIR / "processed"
SITES_FILE = DATA_DIR / "raw" / "sites" / "table_sites.csv"
PRICE_FILE = DATA_DIR / "raw" / "prix" / "prix_spot.csv"
USERS_DB_FILE = BASE_DIR / "users.db"

# ── Constantes de conversion ──────────────────────────────────────────────────
W_TO_KWH = 1 / 1_000          # W (sur 1 h) → kWh
W_TO_MWH = 1 / 1_000_000      # W (sur 1 h) → MWh


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
                # Extrait les PRMs de la liste des modèles
                df = pd.DataFrame([{"prm": m["prm"]} for m in models])
                df["prm"] = df["prm"].astype(str)

                # Tente de récupérer les détails depuis la table sites locale
                sites_csv_df = _load_sites_csv()
                if not sites_csv_df.empty:
                    # Merge avec les infos locales (ville, id_site)
                    df = df.merge(sites_csv_df[["prm", "ville", "id_site"]], on="prm", how="left")

                # Créer site_label (soit "ville (prm)" soit juste "prm")
                if "ville" in df.columns:
                    df["site_label"] = df["ville"].fillna("Inconnu").astype(str) + " (" + df["prm"] + ")"
                else:
                    df["ville"] = "Inconnu"
                    df["id_site"] = ""
                    df["site_label"] = "Site " + df["prm"]
                return df

        st.warning(f"⚠️ API /models/list indisponible ({response.status_code}), fallback CSV...")

    except Exception as e:
        st.warning(f"⚠️ Erreur charge sites API: {str(e)}, fallback CSV...")

    return _load_sites_csv()


def _load_sites_csv() -> pd.DataFrame:
    """Fallback : charge les sites depuis le CSV local."""
    if not SITES_FILE.exists():
        return pd.DataFrame(columns=["prm", "ville", "id_site"])

    try:
        df = pd.read_csv(SITES_FILE)
        df["prm"] = df["prm"].astype(str)
        df["site_label"] = df["ville"].astype(str) + " (" + df["prm"] + ")"
        return df
    except Exception as e:
        st.warning(f"⚠️ Erreur charge CSV sites: {str(e)}")
        return pd.DataFrame(columns=["prm", "ville", "id_site"])


def _extract_prm_from_name(filename: str) -> str | None:
    match = re.search(r"(\d{8,})", filename)
    return match.group(1) if match else None


@st.cache_data
def load_predictions() -> pd.DataFrame:
    """Charge les prédictions uniquement depuis l'API/Fabric.

    Le dashboard ne déclenche plus de POST /predict.
    Les prédictions doivent être générées et stockées côté Fabric (ex: Notebook Fabric).
    """
    try:
        # Récupère d'abord la liste des sites pour savoir quels PRMs charger
        sites_df = load_sites()
        if sites_df.empty:
            return pd.DataFrame()

        frames = []
        failed_prms: list[tuple[str, int]] = []

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

                        # Normaliser le nom de la colonne puissance
                        if "puissance_kw" not in df.columns:
                            if "puissance_moy_heure_pred" in df.columns:
                                df["puissance_kw"] = df["puissance_moy_heure_pred"] / 1_000
                            elif "puissance_kw_pred" in df.columns:
                                df["puissance_kw"] = df["puissance_kw_pred"]

                        df = df[["prm", "datetime", "puissance_kw"]].copy()
                        frames.append(df)
                else:
                    failed_prms.append((prm, pred_response.status_code))

            except Exception as e:
                failed_prms.append((prm, -1))
                continue

        if failed_prms:
            code_counts: dict[str, int] = {}
            for _, status_code in failed_prms:
                code_key = "exception" if status_code == -1 else str(status_code)
                code_counts[code_key] = code_counts.get(code_key, 0) + 1
            summary = ", ".join([f"{count}x {code}" for code, count in sorted(code_counts.items())])
            st.info(f"ℹ️ PRM sans prédictions Fabric: {len(failed_prms)} ({summary})")

        if not frames:
            st.warning("Aucune prédiction disponible dans Fabric. Lance le notebook Fabric pour alimenter ia_predictions.")
            return pd.DataFrame()

        out = pd.concat(frames, ignore_index=True)
        out["prm"] = out["prm"].astype(str)
        out["data_type"] = "Prévision"

        # Ajouter site_label en fusionnant avec sites
        sites_df = load_sites()[["prm", "site_label"]]
        out = out.merge(sites_df, on="prm", how="left")

        return out

    except Exception as e:
        st.warning(f"⚠️ Erreur chargement prédictions Fabric/API: {str(e)}")
        return pd.DataFrame()


def _load_predictions_csv() -> pd.DataFrame:
    """Fallback : charge les prédictions depuis les CSV locaux (ancienne méthode)."""
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

    # Ajouter site_label en fusionnant avec sites
    sites_df = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_df, on="prm", how="left")

    return out


@st.cache_data
def load_historical_data() -> pd.DataFrame:
    """Charge l'historique depuis l'API dataclean (/dataclean/allbyprm-json) avec fallback CSV."""
    try:
        sites_df = load_sites()
        if sites_df.empty:
            st.warning("⚠️ Aucun site configuré")
            return pd.DataFrame()

        frames = []

        for _, row in sites_df.iterrows():
            prm = str(row["prm"])
            try:
                # Récupère l'historique depuis API dataclean
                with httpx.Client(timeout=120.0) as client:
                    hist_response = client.get(
                        f"{API_DATACLEAN_URL}/dataclean/allbyprm-json",
                        params={"prm": prm}
                    )

                if hist_response.status_code == 200:
                    hist_data = hist_response.json()
                    rows = hist_data.get("rows", [])

                    if rows:
                        df = pd.DataFrame(rows)

                        # Parser la colonne datetime
                        if "datetime" in df.columns:
                            df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
                        else:
                            continue

                        # Normaliser puissance (si en W, convertir en kW)
                        if "puissance_moy_heure" in df.columns:
                            df["puissance_kw"] = df["puissance_moy_heure"] / 1_000
                        elif "puissance_kw" not in df.columns:
                            continue

                        df["prm"] = prm
                        df = df[["prm", "datetime", "puissance_kw"]].copy()
                        frames.append(df)
                        st.success(f"✅ Historique chargé pour {prm}")
                else:
                    st.warning(f"⚠️ API dataclean indisponible pour {prm} ({hist_response.status_code})")

            except Exception as e:
                st.warning(f"⚠️ Erreur historique {prm}: {str(e)}")
                continue

        if not frames:
            st.info("ℹ️ Aucun historique disponible via l'API, fallback CSV...")
            return _load_historical_data_csv()

        out = pd.concat(frames, ignore_index=True)
        out["prm"] = out["prm"].astype(str)
        out["data_type"] = "Historique"

        # Ajouter site_label en fusionnant avec sites
        sites_df = load_sites()[["prm", "site_label"]]
        out = out.merge(sites_df, on="prm", how="left")

        return out

    except Exception as e:
        st.warning(f"⚠️ Erreur chargement historique API: {str(e)}, fallback CSV...")
        return _load_historical_data_csv()


def _load_historical_data_csv() -> pd.DataFrame:
    """Fallback : charge l'historique depuis les CSV locaux (ancienne méthode)."""
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

    # Ajouter site_label en fusionnant avec sites
    sites_df = load_sites()[["prm", "site_label"]]
    out = out.merge(sites_df, on="prm", how="left")

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


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def init_users_db() -> None:
    with sqlite3.connect(USERS_DB_FILE) as connection:
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'lecteur')),
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        default_users = [
            ("admin", hash_password("admin123"), "admin"),
            ("lecteur", hash_password("lecteur123"), "lecteur"),
        ]
        cursor.executemany(
            """
            INSERT OR IGNORE INTO users(username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            default_users,
        )
        connection.commit()


def authenticate_user(username: str, password: str) -> dict | None:
    with sqlite3.connect(USERS_DB_FILE) as connection:
        cursor = connection.cursor()
        cursor.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?",
            (username,),
        )
        row = cursor.fetchone()

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
        return False, "Role invalide."

    try:
        with sqlite3.connect(USERS_DB_FILE) as connection:
            cursor = connection.cursor()
            cursor.execute(
                """
                INSERT INTO users(username, password_hash, role)
                VALUES (?, ?, ?)
                """,
                (username, hash_password(password), role),
            )
            connection.commit()
    except sqlite3.IntegrityError:
        return False, "Ce nom d'utilisateur existe déjà."

    return True, "Utilisateur créé avec succès."


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

init_users_db()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "role" not in st.session_state:
    st.session_state.role = ""

if not st.session_state.authenticated:
    st.title("Identification")
    st.caption("Connectez-vous pour accéder au dashboard")
    st.info("Comptes de test : admin/admin123 et lecteur/lecteur123")

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
current_role = st.session_state.role

st.sidebar.success(f"Connecté : {current_username} ({current_role})")
if st.sidebar.button("Se déconnecter"):
    st.session_state.authenticated = False
    st.session_state.username = ""
    st.session_state.role = ""
    st.rerun()

if current_role == "admin":
    with st.sidebar.expander("Gestion des utilisateurs", expanded=False):
        with st.form("create_user_form", clear_on_submit=True):
            new_username = st.text_input("Nouveau nom d'utilisateur")
            new_password = st.text_input("Nouveau mot de passe", type="password")
            new_role = st.selectbox("Role", ["admin", "lecteur"])
            create_submitted = st.form_submit_button("Créer l'utilisateur")

        if create_submitted:
            created, message = create_user(new_username, new_password, new_role)
            if created:
                st.success(message)
            else:
                st.error(message)

st.title("Dashboard previsions conso et prix")

sites_df = load_sites()
prices_df = load_prices()
preds_df = load_predictions()
hist_df = load_historical_data()

if preds_df.empty:
    st.warning("Aucune prediction disponible depuis Fabric.")
    st.stop()

if "puissance_kw" not in preds_df.columns:
    st.error("Colonne puissance_kw manquante dans les predictions.")
    st.stop()

# Assurer que site_label existe (créé lors du merge dans load_predictions)
if "site_label" not in preds_df.columns:
    preds_df["site_label"] = "PRM " + preds_df["prm"].astype(str)
else:
    preds_df["site_label"] = preds_df["site_label"].fillna("PRM " + preds_df["prm"].astype(str))

# Idem pour l'historique
if not hist_df.empty:
    if "site_label" not in hist_df.columns:
        hist_df["site_label"] = "PRM " + hist_df["prm"].astype(str)
    else:
        hist_df["site_label"] = hist_df["site_label"].fillna("PRM " + hist_df["prm"].astype(str))

min_date_pred = preds_df["datetime"].min()
max_date_pred = preds_df["datetime"].max()

st.sidebar.header("Filtres")
site_options = sorted(preds_df["site_label"].unique())
site_filter_options = ["Tous les sites"] + site_options
selected_site_filters = st.sidebar.multiselect(
    "Sites",
    site_filter_options,
    default=["Tous les sites"],
)

if not selected_site_filters or "Tous les sites" in selected_site_filters:
    selected_sites = site_options
    all_sites_selected = True
else:
    selected_sites = [site for site in selected_site_filters if site in site_options]
    all_sites_selected = len(selected_sites) == len(site_options)

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

if current_role != "admin":
    st.info("Mode lecteur : la simulation achat base/peak est réservée aux administrateurs.")
elif not all_sites_selected:
    st.info("La simulation est disponible uniquement avec le filtre 'Tous les sites'.")
else:
    st.subheader("Simulation achat base/peak")

    sim_df = (
        filtered.groupby("datetime", as_index=False)["puissance_kw"].sum()
    )

    if sim_df.empty:
        st.info("Aucune donnée disponible pour la simulation tous sites.")
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
        height = max(400, 300 + len(sim_df) * 0.01)
        fig_cum.update_layout(height=min(height, 800))
        st.plotly_chart(fig_cum, use_container_width=True)
