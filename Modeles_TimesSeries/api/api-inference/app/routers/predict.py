import re
import sys
from pathlib import Path

import httpx
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

from app.security import require_api_key
from app.settings import CONFIG_PATH, DATACLEAN_BASE_URL, MODELS_DIR
from app.project_paths import resolve_project_root
from app.config.database import get_db_connection
from app.repository.fabric_repository import FabricRepository

# Ce path permet d'importer les modules du projet principal (src/*)
PROJECT_ROOT = resolve_project_root(Path(__file__))
sys.path.insert(0, str(PROJECT_ROOT))

from src.generate_climate_averages import (
    add_climate_trend,
    add_heatwaves,
    calculate_climate_averages,
    generate_future_meteo,
)
from src.predict import format_predictions_for_dashboard, predict_future
from src.utils import load_config

router = APIRouter(tags=["predictions"])

# PRM Enedis : 14 chiffres
PRM_PATTERN = re.compile(r"^\d{14}$")

# Cache mémoire des dernières prédictions par PRM.
# Note : ce cache est perdu au redémarrage de l'API (comportement normal en mode simple).
LATEST_PREDICTIONS: dict[str, dict] = {}


def _fetch_history_from_dataclean(prm: str) -> pd.DataFrame:
    """
    Récupère l'historique directement depuis api-dataclean en JSON.
    Objectif : ne plus dépendre d'un CSV intermédiaire pour prédire.
    """
    source_url = f"{DATACLEAN_BASE_URL}/dataclean/allbyprm-json"

    try:
        with httpx.Client(timeout=180.0) as client:
            response = client.get(source_url, params={"prm": prm})
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur dataclean ({exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Dataclean API indisponible") from exc

    rows = payload.get("rows", [])
    if not rows:
        raise HTTPException(status_code=404, detail="Aucune donnée historique trouvée côté dataclean")

    df = pd.DataFrame(rows)

    if "datetime" not in df.columns:
        raise HTTPException(
            status_code=500,
            detail="La réponse dataclean doit contenir la colonne 'datetime'"
        )

    df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce")
    df = df.dropna(subset=["datetime"]).sort_values("datetime").reset_index(drop=True)

    if df.empty:
        raise HTTPException(status_code=404, detail="Historique vide après parsing des dates")

    return df


def _build_future_weather_from_history(history_df: pd.DataFrame) -> pd.DataFrame:
    """
    Génère une météo future à partir de l'historique en mémoire (sans CSV).
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

    meteo_future = add_climate_trend(meteo_future, start_date)
    meteo_future = add_heatwaves(meteo_future)
    return meteo_future


@router.post(
    "/predict/prm/{prm}",
    summary="Lancer une prédiction Prophet pour un PRM",
    description=(
        "Récupère l'historique depuis api-dataclean (JSON), génère la météo future, "
        "applique le modèle Prophet et retourne directement les résultats en JSON."
    )
)
def predict_prm(prm: str, _: str = Depends(require_api_key)) -> dict:
    """
    Pipeline simplifié de prédiction :
    1) Vérifier les prérequis (historique + modèle),
    2) Générer la météo future,
    3) Calculer la prédiction,
    4) Formater pour le dashboard,
    5) Retourner un JSON (sans écrire de CSV).
    """
    if not PRM_PATTERN.match(prm):
        raise HTTPException(status_code=422, detail="Le PRM doit contenir exactement 14 chiffres")

    model_path = MODELS_DIR / f"prophet_model_{prm}_latest.pkl"
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Modèle Prophet introuvable pour ce PRM")

    try:
        # 1) Historique direct depuis api-dataclean (JSON)
        historique_df = _fetch_history_from_dataclean(prm)

        # 2) Génération météo future en mémoire
        meteo_future = _build_future_weather_from_history(historique_df)

        # 3) Prédiction Prophet
        df_pred = predict_future(
            prm=prm,
            meteo_future_df=meteo_future,
            model_dir=str(MODELS_DIR),
            config_path=str(CONFIG_PATH)
        )

        # 4) Format dashboard
        output_df = format_predictions_for_dashboard(
            df_pred,
            historique_start=historique_df["datetime"].min()
        )

        # 5) Réponse JSON uniquement (pas d'écriture disque)
        response_df = output_df.copy()
        if "datetime" in response_df.columns:
            response_df["datetime"] = pd.to_datetime(response_df["datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

        series = response_df.to_dict(orient="records")

        payload = {
            "message": "Prédiction générée",
            "prm": prm,
            "rows": len(response_df),
            "start": series[0]["datetime"] if series else None,
            "end": series[-1]["datetime"] if series else None,
            "series": series,
        }

        # Mémoriser la dernière prédiction calculée pour /predictions/.../latest
        LATEST_PREDICTIONS[prm] = payload
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de prédiction: {str(exc)}") from exc

    return payload


@router.get(
    "/predictions/prm/{prm}/latest",
    summary="Récupérer la dernière prédiction d'un PRM",
    description=(
        "Retourne la dernière prédiction stockée dans Fabric (table ia_predictions) pour un PRM."
    )
)
def get_latest_prediction(prm: str, _: str = Depends(require_api_key)) -> dict:
    """Lecture des prédictions depuis Fabric pour le dashboard."""
    if not PRM_PATTERN.match(prm):
        raise HTTPException(status_code=422, detail="Le PRM doit contenir exactement 14 chiffres")

    conn = None
    try:
        conn = get_db_connection()
        repo = FabricRepository(conn)
        series = repo.get_latest_predictions_series(prm)

        if series is None:
            raise HTTPException(
                status_code=503,
                detail="Impossible de lire ia_predictions dans Fabric"
            )

        if not series:
            raise HTTPException(
                status_code=404,
                detail="Aucune prédiction trouvée dans Fabric pour ce PRM"
            )

        return {
            "message": "Prédiction lue depuis Fabric",
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
        raise HTTPException(status_code=503, detail=f"Erreur Fabric: {str(exc)}") from exc
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass
