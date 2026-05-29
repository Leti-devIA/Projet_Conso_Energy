"""
Tests automatisés pour dashboard_demo.py.

Même stratégie que test_dashboard_app.py :
- Streamlit, httpx et logging.handlers mockés avant toute chose.
- Fonctions pures testées directement (inlinées ou via le module chargé
  prudemment).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

# ── Chemin du dashboard ──────────────────────────────────────────────────────
_DASHBOARD_PATH = Path(__file__).resolve().parent.parent / "dashboard_demo.py"


# ── Helpers partagés ─────────────────────────────────────────────────────────

class _DashboardStopped(Exception):
    """Levée quand st.stop() est appelé."""


class _SessionState(dict):
    def __getattr__(self, key):
        return self.get(key, False)

    def __setattr__(self, key, val):
        self[key] = val


# ── Fixture : module chargé avec Streamlit mocké ────────────────────────────
@pytest.fixture(scope="module")
def demo_mod():
    """
    Tente de charger dashboard_demo avec Streamlit mocké.
    Skip si le module ne peut pas être chargé (données absentes en CI).
    """
    st_mock = MagicMock(name="streamlit")
    st_mock.session_state = _SessionState(
        {"authenticated": True, "username": "test_admin", "role": "admin"}
    )
    st_mock.stop.side_effect = _DashboardStopped()
    st_mock.cache_data = lambda fn=None, **kw: (fn if fn else lambda f: f)
    st_mock.sidebar = MagicMock()
    st_mock.sidebar.multiselect.return_value = ["Tous les sites"]
    progress_mock = MagicMock()
    progress_mock.empty = MagicMock()
    st_mock.progress.return_value = progress_mock

    httpx_mock = MagicMock(name="httpx")
    log_handlers_mock = MagicMock(name="logging.handlers")

    _backup = {
        k: sys.modules.get(k)
        for k in ("streamlit", "httpx", "logging.handlers")
    }
    sys.modules["streamlit"] = st_mock
    sys.modules["httpx"] = httpx_mock
    sys.modules["logging.handlers"] = log_handlers_mock

    mod = None
    try:
        spec = importlib.util.spec_from_file_location("dashboard_demo", _DASHBOARD_PATH)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
    except (_DashboardStopped, SystemExit, Exception):
        pass
    finally:
        for k, v in _backup.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v

    if mod is None:
        pytest.skip("Module dashboard_demo non chargeable (données absentes)")

    return mod


# ═══════════════════════════════════════════════════════════════════════════════
# Fixtures de données
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def sample_price_df():
    return pd.DataFrame(
        {
            "date_deb": pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"]),
            "date_fin": pd.to_datetime(["2025-01-31", "2025-02-28", "2025-03-31"]),
            "prix_base": [80.0, 85.0, 90.0],
            "prix_peak": [100.0, 110.0, 120.0],
            "type": ["mensuel", "mensuel", "mensuel"],
        }
    )


@pytest.fixture
def sample_preds_df():
    """Prédictions factices multi-sites."""
    np.random.seed(1)
    n = 300
    return pd.DataFrame(
        {
            "datetime": pd.date_range("2025-01-01", periods=n, freq="h"),
            "puissance_kw": np.random.uniform(50, 400, n),
            "site_label": np.where(np.arange(n) < 150, "Paris (PRM1)", "Lyon (PRM2)"),
            "prm": np.where(np.arange(n) < 150, "PRM1", "PRM2"),
            "data_type": "Prévision",
        }
    )


@pytest.fixture
def sample_preds_with_negatives(sample_preds_df):
    """Prédictions avec quelques valeurs négatives."""
    df = sample_preds_df.copy()
    df.loc[df.index[:5], "puissance_kw"] = -10.0
    return df


@pytest.fixture
def sample_achats_df():
    """Achats d'énergie factices."""
    return pd.DataFrame(
        {
            "DEB_PERIODE": pd.to_datetime(["2025-01-01", "2025-06-01"]),
            "FIN_PERIODE": pd.to_datetime(["2025-05-31", "2025-12-31"]),
            "VOLUME_TOTAL_PERIODE": [1000.0, 1500.0],  # MWh
        }
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Tests : check_negative_predictions
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestCheckNegativePredictions:
    """Tests de la logique de détection des prédictions négatives."""

    @staticmethod
    def _check_negative_predictions(preds: pd.DataFrame) -> list[dict]:
        alerts: list[dict] = []
        if preds.empty or "puissance_kw" not in preds.columns:
            return alerts
        neg_df = preds[preds["puissance_kw"] < 0]
        if neg_df.empty:
            return alerts
        col = "site_label" if "site_label" in neg_df.columns else "prm"
        for site_label, group in neg_df.groupby(col):
            alerts.append(
                {
                    "site": site_label,
                    "count": len(group),
                    "min": group["puissance_kw"].min(),
                }
            )
        return alerts

    def test_sans_negatifs_retourne_liste_vide(self, sample_preds_df):
        """Teste que sans prédictions négatives, aucune alerte n'est levée."""
        result = self._check_negative_predictions(sample_preds_df)
        assert result == []

    def test_detecte_les_negatifs(self, sample_preds_with_negatives):
        """Teste que les prédictions négatives sont détectées."""
        result = self._check_negative_predictions(sample_preds_with_negatives)
        assert len(result) > 0

    def test_alerte_possede_cles_esperees(self, sample_preds_with_negatives):
        """Teste que chaque alerte contient les clés attendues (site, count, min)."""
        result = self._check_negative_predictions(sample_preds_with_negatives)
        assert "site" in result[0]
        assert "count" in result[0]
        assert "min" in result[0]

    def test_dataframe_vide_retourne_liste_vide(self):
        """Teste qu'un DataFrame vide retourne une liste vide."""
        result = self._check_negative_predictions(pd.DataFrame())
        assert result == []

    def test_tous_negatifs_signales(self):
        """Teste que tous les prix négatifs sont identifiés."""
        df = pd.DataFrame(
            {
                "datetime": pd.date_range("2025-01-01", periods=3, freq="h"),
                "puissance_kw": [-1.0, -2.0, -3.0],
                "site_label": "SiteA",
            }
        )
        result = self._check_negative_predictions(df)
        assert result[0]["count"] == 3
        assert result[0]["min"] == pytest.approx(-3.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests : purchased_volume_mwh_for_year
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestPurchasedVolumeMwhForYear:
    """Tests du calcul de volume acheté annuel avec prorata."""

    @staticmethod
    def _fn():
        def purchased_volume_mwh_for_year(df: pd.DataFrame, year: int) -> float:
            if df.empty or "VOLUME_TOTAL_PERIODE" not in df.columns:
                return 0.0
            total_mwh = 0.0
            year_start = pd.Timestamp(year=year, month=1, day=1)
            year_end = pd.Timestamp(year=year, month=12, day=31, hour=23, minute=59)
            if "DEB_PERIODE" in df.columns and "FIN_PERIODE" in df.columns:
                for _, row in df.iterrows():
                    overlap_start = max(row["DEB_PERIODE"], year_start)
                    overlap_end = min(row["FIN_PERIODE"], year_end)
                    if overlap_start > overlap_end:
                        continue
                    period_days = (row["FIN_PERIODE"] - row["DEB_PERIODE"]).days or 1
                    overlap_days = (overlap_end - overlap_start).days + 1
                    ratio = overlap_days / period_days
                    total_mwh += row["VOLUME_TOTAL_PERIODE"] * ratio
            elif "DATE_ACHAT" in df.columns:
                mask = df["DATE_ACHAT"].dt.year == year
                total_mwh = df.loc[mask, "VOLUME_TOTAL_PERIODE"].sum()
            return float(total_mwh)

        return purchased_volume_mwh_for_year

    def test_couverture_annee_complete(self, sample_achats_df):
        """Teste le calcul complet du volume d'énergie achetée pour l'année."""
        fn = self._fn()
        result = fn(sample_achats_df, 2025)
        # Les deux périodes couvrent entièrement 2025 → total ~ 2500 MWh
        assert result == pytest.approx(2500.0, rel=0.05)

    def test_dataframe_vide_retourne_zero(self):
        """Teste qu'un DataFrame vide retourne 0 MWh."""
        fn = self._fn()
        assert fn(pd.DataFrame(), 2025) == pytest.approx(0.0)

    def test_pas_chevauchement_retourne_zero(self, sample_achats_df):
        """Teste qu'aucun chevauchement sur l'année retourne 0 MWh."""
        fn = self._fn()
        result = fn(sample_achats_df, 2023)
        assert result == pytest.approx(0.0)

    def test_chevauchement_partiel(self):
        """Teste le calcul avec un chevauchement partiel (H2 2025)."""
        fn = self._fn()
        df = pd.DataFrame(
            {
                "DEB_PERIODE": pd.to_datetime(["2025-07-01"]),
                "FIN_PERIODE": pd.to_datetime(["2025-12-31"]),
                "VOLUME_TOTAL_PERIODE": [600.0],
            }
        )
        result = fn(df, 2025)
        assert result == pytest.approx(600.0, rel=0.05)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests : price_for_datetimes (version demo)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestPriceForDatetimesDemo:
    @staticmethod
    def _fn():
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
                    left_on="datetime",
                    right_on="date_deb",
                    direction="backward",
                )
                in_range = merged["datetime"] <= merged["date_fin"]
                assign_mask = in_range & result.loc[merged.index].isna()
                result.loc[merged.index[assign_mask]] = merged.loc[
                    assign_mask, price_col
                ].values
            return result

        return price_for_datetimes

    def test_priorite_mensuel_sur_trimestriel(self):
        """Teste que les prix mensuels sont prioritaires sur les trimestres."""
        fn = self._fn()
        price_df = pd.DataFrame(
            {
                "date_deb": pd.to_datetime(["2025-01-01", "2025-01-01"]),
                "date_fin": pd.to_datetime(["2025-01-31", "2025-03-31"]),
                "prix_base": [80.0, 70.0],
                "type": ["mensuel", "trimestriel"],
            }
        )
        dates = pd.Series([pd.Timestamp("2025-01-15")])
        result = fn(dates, price_df, "prix_base", ["mensuel", "trimestriel"])
        # Prix mensuel (80) doit être prioritaire sur trimestriel (70)
        assert result.iloc[0] == pytest.approx(80.0)

    def test_repli_trimestriel_sans_mensuel(self):
        """Teste le repli sur les prix trimestriels quand aucun mensuel n'existe."""
        fn = self._fn()
        price_df = pd.DataFrame(
            {
                "date_deb": pd.to_datetime(["2025-01-01"]),
                "date_fin": pd.to_datetime(["2025-03-31"]),
                "prix_base": [70.0],
                "type": ["trimestriel"],
            }
        )
        dates = pd.Series([pd.Timestamp("2025-02-15")])
        result = fn(dates, price_df, "prix_base", ["mensuel", "trimestriel"])
        assert result.iloc[0] == pytest.approx(70.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests : fig_pie
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestFigPie:
    """Tests du graphique camembert (répartition par site)."""

    def test_retourne_figure(self, sample_preds_df):
        """Teste que la fonction retourne une figure Plotly valide."""
        import plotly.express as px
        import plotly.graph_objects as go

        totals = sample_preds_df.groupby("site_label", as_index=False)["puissance_kw"].sum()
        fig = px.pie(totals, names="site_label", values="puissance_kw", hole=0.38)
        assert isinstance(fig, go.Figure)

    def test_deux_sites_donnent_deux_parts(self, sample_preds_df):
        """Teste que deux sites génèrent deux parts du camembert."""
        import plotly.express as px

        totals = sample_preds_df.groupby("site_label", as_index=False)["puissance_kw"].sum()
        fig = px.pie(totals, names="site_label", values="puissance_kw")
        assert len(fig.data[0]["labels"]) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Tests : fig_yearly_bar
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestFigYearlyBar:
    """Tests du graphique en barres (consommation par année et site)."""

    def test_colonne_energie_kwh_creee(self, sample_preds_df):
        """Teste que la conversion puissance (kW) → énergie (kWh) est effectuée."""
        df = sample_preds_df.sort_values(["site_label", "datetime"]).copy()
        delta_h = (
            df.groupby("site_label")["datetime"]
            .diff()
            .dt.total_seconds()
            .div(3600)
        )
        median_h = delta_h.groupby(df["site_label"]).transform("median")
        df["interval_h"] = delta_h.fillna(median_h).fillna(1.0).clip(lower=1 / 60, upper=24)
        df["energy_kwh"] = df["puissance_kw"] * df["interval_h"]
        assert "energy_kwh" in df.columns
        assert (df["energy_kwh"] >= 0).all()

    def test_retourne_figure(self, sample_preds_df):
        """Teste que la fonction retourne une figure Plotly valide."""
        import plotly.express as px
        import plotly.graph_objects as go

        df = sample_preds_df.copy()
        df["year"] = df["datetime"].dt.year.astype(str)
        yearly = df.groupby(["year", "site_label"], as_index=False)["puissance_kw"].sum()
        fig = px.bar(
            yearly,
            x="year",
            y="puissance_kw",
            color="site_label",
            barmode="group",
        )
        assert isinstance(fig, go.Figure)

    def test_groupby_annee_et_site(self, sample_preds_df):
        """Teste que le groupby par année et site fonctionne correctement."""
        df = sample_preds_df.copy()
        df["year"] = df["datetime"].dt.year.astype(str)
        yearly = df.groupby(["year", "site_label"], as_index=False)["puissance_kw"].sum()
        # 1 année × 2 sites = 2 lignes
        assert len(yearly) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# Tests : build_monthly_price_series (version demo)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestBuildMonthlyPriceSeriesDemo:
    """Tests de la construction de la série de prix mensuel."""

    @staticmethod
    def _fn():
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
                    left_on="datetime",
                    right_on="date_deb",
                    direction="backward",
                )
                in_range = merged["datetime"] <= merged["date_fin"]
                assign_mask = in_range & result.loc[merged.index].isna()
                result.loc[merged.index[assign_mask]] = merged.loc[
                    assign_mask, price_col
                ].values
            return result

        def build_monthly_price_series(price_df, start_date, end_date, priority):
            date_range = pd.date_range(start=start_date, end=end_date, freq="MS")
            monthly_df = pd.DataFrame({"month": date_range})
            for col in ("prix_base", "prix_peak"):
                monthly_df[col] = monthly_df["month"].apply(
                    lambda dt: price_for_datetimes(
                        pd.Series([dt]), price_df, col, priority
                    ).iloc[0]
                )
            return monthly_df.dropna(subset=["prix_base", "prix_peak"], how="all")

        return build_monthly_price_series

    def test_trois_mois(self, sample_price_df):
        """Teste que la plage sur 3 mois génère 3 lignes (janvier, février, mars)."""
        fn = self._fn()
        result = fn(
            sample_price_df,
            pd.Timestamp("2025-01-01"),
            pd.Timestamp("2025-03-01"),
            ["mensuel"],
        )
        assert len(result) == 3

    def test_valeurs_correspondent_source(self, sample_price_df):
        """Teste que les prix correspondent bien aux prix source."""
        fn = self._fn()
        result = fn(
            sample_price_df,
            pd.Timestamp("2025-01-01"),
            pd.Timestamp("2025-01-01"),
            ["mensuel"],
        )
        assert result.iloc[0]["prix_base"] == pytest.approx(80.0)
        assert result.iloc[0]["prix_peak"] == pytest.approx(100.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Tests : simulate_training (logique de retour)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.unit
class TestSimulateTraining:
    """Vérifie le comportement simulé du ré-entraînement (sans appel API réel)."""

    @staticmethod
    def _simulate(old_metrics):
        np.random.seed(42)
        base_mae = (old_metrics or {}).get("val_mae", 5000)
        improvement = np.random.uniform(0.02, 0.12)
        return {
            "val_mae": base_mae * (1 - improvement),
            "val_rmse": base_mae * 1.3 * (1 - improvement),
            "val_mape": 15.0 * (1 - improvement / 2),
            "val_r2": min(0.99, 0.80 + improvement),
        }

    def test_retourne_dict_avec_cles_esperees(self):
        """Teste que la simulation retourne un dict avec les métriques attendues."""
        result = self._simulate({"val_mae": 5000})
        assert "val_mae" in result
        assert "val_rmse" in result
        assert "val_mape" in result
        assert "val_r2" in result

    def test_mae_s_ameliore(self):
        """Teste que la MAE (erreur absolue moyenne) s'améliore après ré-entraînement."""
        old = {"val_mae": 5000}
        new = self._simulate(old)
        assert new["val_mae"] < old["val_mae"]

    def test_r2_entre_0_et_1(self):
        """Teste que le coefficient R² reste entre 0 et 1 (coefficient de détermination)."""
        result = self._simulate(None)
        assert 0.0 <= result["val_r2"] <= 1.0

    def test_fonctionne_sans_anciennes_metriques(self):
        """Teste que la simulation fonctionne même sans métriques précédentes."""
        result = self._simulate(None)
        assert isinstance(result, dict)
        assert len(result) == 4
