"""
Routes de prédiction (pipeline ML complet).

Rôle :
------
Ce module permet :
1. de lancer une prédiction pour un PRM (pipeline complet)
2. de récupérer la dernière prédiction stockée dans Fabric

Pipeline de prédiction :
-----------------------
Dataclean → Historique → Météo future → Modèle Prophet → JSON dashboard
"""

import re
import httpx
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.main import CONFIG_PATH, DATACLEAN_BASE_URL, MODELS_DIR, require_api_key
from app.config.database import get_db_connection
from app.repository.fabric_repository import FabricRepository

from src.generate_climate_averages import (
    add_climate_trend,
    add_heatwaves,
    calculate_climate_averages,
    generate_future_meteo,
)
from src.predict import format_predictions_for_dashboard, predict_future
from src.utils import load_config


# ============================================================
# INITIALISATION ROUTER
# ============================================================

router = APIRouter(tags=["predictions"])

# PRM Enedis = 14 chiffres
PRM_PATTERN = re.compile(r"^\d{14}$")

# Cache mémoire (non persistant)
LATEST_PREDICTIONS: dict[str, dict] = {}


# ============================================================
# UTILITAIRE : récupération historique (API Dataclean)
# ============================================================

def _fetch_history_from_dataclean(prm: str) -> pd.DataFrame:
    """
    Récupère l'historique de consommation depuis l'API Dataclean.

    Avantage :
    - Pas de dépendance à des fichiers CSV
    - Données toujours à jour
    """
    url = f"{DATACLEAN_BASE_URL}/dataclean/allbyprm-json"

    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.get(url, params={"prm": prm})
            response.raise_for_status()
            payload = response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur API Dataclean ({exc.response.status_code})"
        )

    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="API Dataclean indisponible")

    rows = payload.get("rows", [])

    if not rows:
        raise HTTPException(status_code=404, detail="Aucune donnée historique trouvée")

    df = pd.DataFrame(rows)

    if "datetime" not in df.columns:
        raise HTTPException(status_code=500, detail="Colonne 'datetime' manquante")

    # Nettoyage des dates
    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime")

    if df.empty:
        raise HTTPException(status_code=404, detail="Historique vide après nettoyage")

    return df.reset_index(drop=True)


# ============================================================
# UTILITAIRE : génération météo future
# ============================================================

def _build_future_weather_from_history(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Génère une météo future synthétique à partir de l'historique.
    """
    config = load_config(str(CONFIG_PATH))
    horizon_hours = int(config.get("prediction", {}).get("horizon", 8760))

    meteo_moyenne = calculate_climate_averages(history_df)

    start_date = (history_df["datetime"].max() + pd.Timedelta(hours=1)).ceil("h")

    meteo_future = generate_future_meteo(
        start_date=start_date,
        nb_heures=horizon_hours,
        meteo_moyenne=meteo_moyenne,
        add_variability=True,
    )

    # Ajout de réalisme climatique
    meteo_future = add_climate_trend(meteo_future, start_date)
    meteo_future = add_heatwaves(meteo_future)

    return meteo_future


# ============================================================
# ROUTE 1 : Lancer une prédiction
# ============================================================

@router.post("/predict/prm/{prm}")
def predict_prm(prm: str, _: str = Depends(require_api_key)) -> dict:
    """
    Lance une prédiction complète pour un PRM.

    Étapes :
    1. Validation du PRM
    2. Vérification du modèle
    3. Récupération historique (Dataclean)
    4. Génération météo future
    5. Prédiction (Prophet)
    6. Formatage pour dashboard
    7. Retour JSON
    """

    # -------------------------------------------------------
    # 1) Validation PRM
    # -------------------------------------------------------
    if not PRM_PATTERN.match(prm):
        raise HTTPException(status_code=422, detail="PRM invalide (14 chiffres requis)")

    # -------------------------------------------------------
    # 2) Vérification modèle
    # -------------------------------------------------------
    model_path = MODELS_DIR / f"prophet_model_{prm}_latest.pkl"

    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Modèle Prophet introuvable")

    try:
        # -------------------------------------------------------
        # 3) Historique
        # -------------------------------------------------------
        historique_df = _fetch_history_from_dataclean(prm)

        # -------------------------------------------------------
        # 4) Météo future
        # -------------------------------------------------------
        meteo_future = _build_future_weather_from_history(historique_df)

        # -------------------------------------------------------
        # 5) Prédiction ML
        # -------------------------------------------------------
        df_pred = predict_future(
            prm=prm,
            meteo_future_df=meteo_future,
            model_dir=str(MODELS_DIR),
            config_path=str(CONFIG_PATH)
        )

        # -------------------------------------------------------
        # 6) Format dashboard
        # -------------------------------------------------------
        output_df = format_predictions_for_dashboard(
            df_pred,
            historique_start=historique_df["datetime"].min()
        )

        # -------------------------------------------------------
        # 7) Conversion JSON
        # -------------------------------------------------------
        response_df = output_df.copy()

        if "datetime" in response_df.columns:
            response_df["datetime"] = pd.to_datetime(
                response_df["datetime"], errors="coerce"
            ).dt.strftime("%Y-%m-%d %H:%M:%S")

        series = response_df.to_dict(orient="records")

        payload = {
            "message": "Prédiction générée",
            "prm": prm,
            "rows": len(response_df),
            "start": series[0]["datetime"] if series else None,
            "end": series[-1]["datetime"] if series else None,
            "series": series,
        }

        # Cache mémoire
        LATEST_PREDICTIONS[prm] = payload

        return payload

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur de prédiction : {str(exc)}"
        )


# ============================================================
# ROUTE 2 : Lire la dernière prédiction (Fabric)
# ============================================================

@router.get("/predictions/prm/{prm}/latest")
def get_latest_prediction(prm: str, _: str = Depends(require_api_key)) -> dict:
    """
    Récupère la dernière prédiction depuis Fabric.

    Utilisé par :
    - dashboard
    - visualisation des résultats
    """

    if not PRM_PATTERN.match(prm):
        raise HTTPException(status_code=422, detail="PRM invalide")

    conn = None

    try:
        conn = get_db_connection()
        repo = FabricRepository(conn)

        series = repo.get_latest_predictions_series(prm)

        if series is None:
            raise HTTPException(status_code=503, detail="Fabric indisponible")

        if not series:
            raise HTTPException(status_code=404, detail="Aucune prédiction trouvée")

        return {
            "message": "Prédiction récupérée depuis Fabric",
            "prm": prm,
            "rows": len(series),
            "start": series[0]["datetime"],
            "end": series[-1]["datetime"],
            "series": series,
            "source": "fabric",
        }

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Erreur Fabric : {str(exc)}"
        )

    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass