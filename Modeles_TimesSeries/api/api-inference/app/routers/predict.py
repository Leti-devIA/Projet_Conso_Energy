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
import os
import time
import uuid
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import httpx
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks

from app.main import CONFIG_PATH, DATACLEAN_BASE_URL, MODELS_DIR, PREDICTIONS_DIR, require_api_key
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

# Statut des jobs de régénération globale
REGENERATE_JOBS: dict[str, dict] = {}
REGENERATE_LOCK = threading.Lock()

# Nombre de workers pour accélérer la régénération multi-sites
REGENERATE_MAX_WORKERS = int(os.getenv("REGENERATE_MAX_WORKERS", "4"))


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


def _discover_prms_with_latest_models() -> list[str]:
    """
    Détecte les PRM disponibles via les modèles *_latest.pkl.
    """
    prms: set[str] = set()

    for model_file in MODELS_DIR.glob("*_latest.pkl"):
        match = re.search(r"(\d{14})", model_file.stem)
        if match:
            prms.add(match.group(1))

    return sorted(prms)


def _build_prediction_payload(prm: str) -> dict:
    """
    Exécute le pipeline de prédiction complet pour un PRM.
    """
    # Vérifie qu'un modèle latest est disponible
    model_path = MODELS_DIR / f"prophet_model_{prm}_latest.pkl"
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Modèle Prophet introuvable")

    # 1) Historique
    historique_df = _fetch_history_from_dataclean(prm)

    # 2) Météo future
    meteo_future = _build_future_weather_from_history(historique_df)

    # 3) Prédiction ML
    df_pred = predict_future(
        prm=prm,
        meteo_future_df=meteo_future,
        model_dir=str(MODELS_DIR),
        config_path=str(CONFIG_PATH),
        history_df=historique_df,
    )

    # 4) Format dashboard
    output_df = format_predictions_for_dashboard(
        df_pred,
        historique_start=historique_df["datetime"].min(),
    )

    # 5) Conversion JSON
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
        "history_end": historique_df["datetime"].max().strftime("%Y-%m-%d %H:%M:%S"),
        "generated_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        "series": series,
    }

    # Sauvegarde sur disque pour que le dashboard puisse lire les données
    PREDICTIONS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = PREDICTIONS_DIR / f"prophet_predictions_{prm}.csv"
    output_df.to_csv(csv_path, index=False)
    print(f"💾 Prédictions sauvegardées : {csv_path.name} ({len(output_df)} lignes) - {csv_path}")

    # Cache mémoire (accès rapide sans relire le CSV)
    LATEST_PREDICTIONS[prm] = payload
    return payload


def _run_regenerate_all_job(job_id: str, prms: list[str]) -> None:
    """
    Lance la régénération en parallèle pour tous les PRM.
    """
    started_at = time.time()
    workers = max(1, min(REGENERATE_MAX_WORKERS, len(prms)))

    ok = 0
    failed = 0
    errors: list[dict] = []

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(_build_prediction_payload, prm): prm for prm in prms}

        for future in as_completed(futures):
            prm = futures[future]

            try:
                future.result()
                ok += 1
            except Exception as exc:
                failed += 1
                errors.append({"prm": prm, "error": str(exc)})

            with REGENERATE_LOCK:
                REGENERATE_JOBS[job_id]["done"] = ok + failed
                REGENERATE_JOBS[job_id]["ok"] = ok
                REGENERATE_JOBS[job_id]["failed"] = failed

    with REGENERATE_LOCK:
        REGENERATE_JOBS[job_id]["status"] = "completed"
        REGENERATE_JOBS[job_id]["finished_at"] = datetime.utcnow().isoformat()
        REGENERATE_JOBS[job_id]["duration_sec"] = round(time.time() - started_at, 2)
        REGENERATE_JOBS[job_id]["errors"] = errors


def trigger_regenerate_all_predictions_startup() -> dict:
    """
    Déclenche la régénération globale au démarrage de l'API.

    Retourne un résumé (job démarré, déjà en cours, ou aucun PRM).
    """
    prms = _discover_prms_with_latest_models()

    if not prms:
        return {
            "started": False,
            "reason": "Aucun modèle _latest trouvé",
            "job_id": None,
            "total_sites": 0,
        }

    with REGENERATE_LOCK:
        # Évite de lancer plusieurs jobs simultanés au démarrage
        running_job = next(
            (job for job in REGENERATE_JOBS.values() if job.get("status") == "running"),
            None,
        )

        if running_job:
            return {
                "started": False,
                "reason": "Job déjà en cours",
                "job_id": running_job.get("job_id"),
                "total_sites": running_job.get("total", 0),
            }

        job_id = str(uuid.uuid4())
        REGENERATE_JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "total": len(prms),
            "done": 0,
            "ok": 0,
            "failed": 0,
            "duration_sec": None,
            "errors": [],
            "trigger": "startup",
        }

    # Thread daemon pour ne pas bloquer le boot de l'API
    worker = threading.Thread(target=_run_regenerate_all_job, args=(job_id, prms), daemon=True)
    worker.start()

    return {
        "started": True,
        "reason": "Régénération lancée",
        "job_id": job_id,
        "total_sites": len(prms),
        "max_workers": max(1, min(REGENERATE_MAX_WORKERS, len(prms))),
    }


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

    try:
        return _build_prediction_payload(prm)

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Erreur de prédiction : {str(exc)}"
        )


# ============================================================
# ROUTE 1B : Régénérer les prédictions de tous les sites
# ============================================================

@router.post("/predict/all/regenerate")
def regenerate_all_predictions(
    background_tasks: BackgroundTasks,
    _: str = Depends(require_api_key),
) -> dict:
    """
    Lance une régénération rapide de tous les sites (asynchrone).

    Conçu pour être appelé au démarrage de l'application.
    """
    prms = _discover_prms_with_latest_models()

    if not prms:
        raise HTTPException(status_code=404, detail="Aucun modèle _latest trouvé")

    job_id = str(uuid.uuid4())

    with REGENERATE_LOCK:
        REGENERATE_JOBS[job_id] = {
            "job_id": job_id,
            "status": "running",
            "started_at": datetime.utcnow().isoformat(),
            "finished_at": None,
            "total": len(prms),
            "done": 0,
            "ok": 0,
            "failed": 0,
            "duration_sec": None,
            "errors": [],
        }

    background_tasks.add_task(_run_regenerate_all_job, job_id, prms)

    return {
        "message": "Régénération globale lancée",
        "job_id": job_id,
        "total_sites": len(prms),
        "max_workers": max(1, min(REGENERATE_MAX_WORKERS, len(prms))),
        "status_endpoint": f"/predict/all/regenerate/{job_id}",
    }


@router.get("/predict/all/regenerate/{job_id}")
def get_regenerate_status(job_id: str, _: str = Depends(require_api_key)) -> dict:
    """
    Retourne l'état d'avancement d'un job de régénération globale.
    """
    with REGENERATE_LOCK:
        job = REGENERATE_JOBS.get(job_id)

    if not job:
        raise HTTPException(status_code=404, detail="Job introuvable")

    return job


# ============================================================
# ROUTE 2 : Lire la dernière prédiction (Fabric)
# ============================================================

@router.get("/predictions/prm/{prm}/latest")
def get_latest_prediction(
    prm: str,
    force_refresh: bool = False,
    _: str = Depends(require_api_key),
) -> dict:
    """
    Récupère la dernière prédiction pour un PRM.

    Stratégie (fallback progressif) :
    1. Cache mémoire (le plus rapide)
    2. CSV local (rapide, persistant)
    3. Fabric (dernier recours)
    """
    if not PRM_PATTERN.match(prm):
        raise HTTPException(status_code=422, detail="PRM invalide")

    # Option debug/qualité : forcer un recalcul ponctuel si besoin
    if force_refresh:
        payload = _build_prediction_payload(prm)
        return {
            **payload,
            "source": "recomputed",
        }

    # -------------------------------------------------------
    # 1) Cache mémoire (disponible si la régénération startup a tourné)
    # -------------------------------------------------------
    if prm in LATEST_PREDICTIONS:
        payload = LATEST_PREDICTIONS[prm]
        return {
            **payload,
            "source": "cache",
        }

    # -------------------------------------------------------
    # 2) Fallback CSV local (sauvegardé après chaque prédiction)
    # -------------------------------------------------------
    csv_path = PREDICTIONS_DIR / f"prophet_predictions_{prm}.csv"

    if csv_path.exists():
        # Lit le CSV et le retourne au format attendu par le dashboard
        df = pd.read_csv(csv_path)
        df["datetime"] = pd.to_datetime(df["datetime"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")

        # Normalise en kW si absent
        if "puissance_moy_heure_pred" not in df.columns and "yhat" in df.columns:
            df["puissance_moy_heure_pred"] = df["yhat"]
        if "puissance_kw" not in df.columns and "puissance_moy_heure_pred" in df.columns:
            df["puissance_kw"] = df["puissance_moy_heure_pred"] / 1000

        # Garde uniquement les colonnes attendues par le dashboard
        cols_utiles = [c for c in ["datetime", "puissance_moy_heure_pred", "puissance_kw"] if c in df.columns]
        series = df[cols_utiles].to_dict(orient="records")

        payload = {
            "message": "Prédiction récupérée depuis CSV local",
            "prm": prm,
            "rows": len(series),
            "start": series[0]["datetime"] if series else None,
            "end": series[-1]["datetime"] if series else None,
            "history_end": None,
            "generated_at": None,
            "series": series,
            "source": "csv",
        }

        # Remplit le cache mémoire pour accélérer les prochains appels
        LATEST_PREDICTIONS[prm] = {k: v for k, v in payload.items() if k != "source"}
        return payload

    # -------------------------------------------------------
    # 3) Tentative Fabric (dernier recours)
    # -------------------------------------------------------
    conn = None
    try:
        conn = get_db_connection()
        repo = FabricRepository(conn)
        series = repo.get_latest_predictions_series(prm)

        if series:
            payload = {
                "message": "Prédiction récupérée depuis Fabric",
                "prm": prm,
                "rows": len(series),
                "start": series[0]["datetime"],
                "end": series[-1]["datetime"],
                "history_end": None,
                "generated_at": None,
                "series": series,
                "source": "fabric",
            }

            # Remplit le cache mémoire pour accélérer les prochains appels
            LATEST_PREDICTIONS[prm] = {k: v for k, v in payload.items() if k != "source"}
            return payload
    except Exception:
        pass
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass

    raise HTTPException(
        status_code=404,
        detail=f"Aucune prédiction trouvée pour le PRM {prm}. Lancez POST /predict/prm/{prm}"
    )
