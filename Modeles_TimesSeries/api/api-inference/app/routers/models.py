"""
Routes pour gérer les modèles Prophet vers Fabric Warehouse.

Endpoints principaux :
    GET  /models/list          → lister les modèles disponibles en local
    GET  /models/prm/{prm}     → récupérer le modèle actif (Fabric ou fallback local)
"""

import uuid
import logging
import json
from datetime import datetime
from typing import Dict, List

import mlflow
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.main import (
    FABRIC_OUTBOX_PATH,
    MLFLOW_TRACKING_URI,
    MODELS_DIR,
)
from app.repository.fabric_repository import FabricRepository
from app.config.database import get_db_connection
from app.config.fabric_automation import automate_onelake_upload_and_notebook

# -------------------------------------------------------
# Configuration du logger
# -------------------------------------------------------
logger = logging.getLogger(__name__)

# Création du routeur FastAPI
router = APIRouter(prefix="/models", tags=["Models"])


# ============================================================
# Schémas de réponse (Pydantic)
# ============================================================

class ModelRegistryResponse(BaseModel):
    """
    Représente un modèle actif (issu de Fabric ou local).
    """
    model_id: str
    prm: str
    model_name: str
    model_version: str
    artifact_uri: str
    created_at: datetime
    is_active: bool


class ModelsListResponse(BaseModel):
    """
    Réponse pour la liste des modèles disponibles.
    """
    total: int
    models: List[dict]


class LatestModelInfo(BaseModel):
    """
    Informations sur le dernier modèle entraîné pour un PRM.
    Utilisé par Fabric pour mettre à jour la table ia_models.
    """
    prm: str
    model_name: str
    model_version: str
    artifact_uri: str
    mae: float | None = None
    rmse: float | None = None
    mape: float | None = None
    trained_at: datetime
    is_active: bool = True


class LatestModelsResponse(BaseModel):
    """
    Réponse pour la liste de tous les derniers modèles.
    """
    total: int
    models: List[LatestModelInfo]


class IaModelsSyncItem(BaseModel):
    """
    Ligne prête pour alimenter la table Fabric ia_models.
    """
    id_modele: str
    prm: str
    nom_modele: str
    version_modele: str
    uri: str
    date_creation: datetime
    is_active: bool
    mae: float | None = None
    rmse: float | None = None
    mape: float | None = None


class IaModelsSyncResponse(BaseModel):
    """
    Réponse de synchronisation vers Fabric.
    """
    total: int
    generated_at: datetime
    rows: List[IaModelsSyncItem]


# ============================================================
# UTILITAIRE : récupération des métriques MLflow
# ============================================================

def get_mlflow_metrics(prm: str) -> dict:
    """
    Récupère les métriques MLflow du dernier run associé à un PRM.

    Retour :
        {
            "run_id": str,
            "metrics": dict,
            "params": dict,
            "created_at": datetime
        }
        ou {} si aucun run trouvé
    """
    logger.info(f"[INFO] Lecture des métriques MLflow pour le PRM : {prm}")

    try:
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()

        # Parcourt toutes les expériences MLflow
        experiments = client.search_experiments()

        for exp in experiments:
            # Recherche le dernier run correspondant au PRM
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                filter_string=f"params.prm = '{prm}'",
                order_by=["start_time DESC"],
                max_results=1
            )

            if runs:
                run = runs[0]
                logger.info(f"[INFO] Run MLflow trouvé : {run.info.run_id[:8]}")

                return {
                    "run_id": run.info.run_id,
                    "metrics": run.data.metrics,
                    "params": run.data.params,
                    "created_at": datetime.utcfromtimestamp(run.info.start_time / 1000)
                }

        logger.warning(f"[WARNING] Aucun run MLflow trouvé pour le PRM : {prm}")
        return {}

    except Exception as e:
        logger.error(f"[ERREUR] Impossible de lire MLflow : {str(e)}")
        return {}


# ============================================================
# UTILITAIRE : Outbox Fabric (fallback)
# ============================================================

def append_fabric_outbox_record(payload: dict) -> None:
    """
    Stocke une opération Fabric dans un fichier local (outbox),
    utilisée si Fabric n'est pas disponible.

    Permet une ingestion différée (pattern "event sourcing").
    """
    payload = dict(payload)
    payload.setdefault("event_id", str(uuid.uuid4()))
    payload.setdefault("queued_at", datetime.utcnow().isoformat())

    FABRIC_OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)

    with FABRIC_OUTBOX_PATH.open("a", encoding="utf-8") as outbox:
        outbox.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")

    logger.info("[INFO] Événement ajouté dans l'outbox Fabric (fallback)")


# ============================================================
# ROUTE 1 : Lister les modèles disponibles

# ============================================================
# ROUTE 0 : Dernier modèle entraîné → pour Fabric ia_models
# ============================================================

@router.get(
    "/latest",
    response_model=LatestModelsResponse,
    summary="Récupérer tous les derniers modèles entraînés",
)
async def get_latest_models() -> LatestModelsResponse:
    """
    Retourne les informations de tous les modèles _latest.pkl.

    Cette route est appelée par Fabric pour mettre à jour
    la table ia_models avec les derniers modèles entraînés.

    Pour chaque modèle trouvé, on enrichit avec les métriques MLflow.
    """
    logger.info("[INFO] Recherche de tous les derniers modèles entraînés...")

    if not MODELS_DIR.exists():
        logger.warning(f"[WARNING] Dossier modèles introuvable : {MODELS_DIR}")
        return LatestModelsResponse(total=0, models=[])

    results = []

    # Parcourt tous les fichiers prophet_model_{prm}_latest.pkl
    for pkl_file in MODELS_DIR.glob("*_latest.pkl"):

        # Extrait le PRM depuis le nom du fichier
        filename = pkl_file.stem  # ex: prophet_model_30000650060080_latest
        prm = None

        for token in filename.replace("prophet_model_", "").split("_"):
            if token.isdigit() and len(token) == 14:
                prm = token
                break

        # Si aucun PRM valide trouvé, on passe au fichier suivant
        if not prm:
            logger.warning(f"[WARNING] PRM non trouvé dans : {pkl_file.name}")
            continue

        # Récupère les métriques MLflow associées à ce PRM
        mlflow_data = get_mlflow_metrics(prm)
        metrics = mlflow_data.get("metrics", {})
        trained_at = mlflow_data.get("created_at", datetime.utcfromtimestamp(pkl_file.stat().st_mtime))

        results.append(LatestModelInfo(
            prm=prm,
            model_name=mlflow_data.get("params", {}).get("model_name", "prophet"),
            model_version=trained_at.strftime("%Y.%m.%d.1"),
            artifact_uri=str(pkl_file),
            # Métriques de performance du modèle
            mae=metrics.get("mae"),
            rmse=metrics.get("rmse"),
            mape=metrics.get("mape"),
            trained_at=trained_at,
            is_active=True,
        ))

        logger.info(f"[INFO] Modèle ajouté : PRM={prm}")

    logger.info(f"[INFO] {len(results)} modèle(s) latest trouvé(s)")

    return LatestModelsResponse(total=len(results), models=results)


@router.get(
    "/latest/ia-models",
    response_model=IaModelsSyncResponse,
    summary="Payload prêt Fabric pour ia_models",
)
async def get_latest_models_for_fabric() -> IaModelsSyncResponse:
    """
    Retourne les derniers modèles au format cible de la table ia_models.

    Cette route est prévue pour être appelée directement par Fabric,
    sans faire un appel /list puis /prm/{prm} pour chaque modèle.
    """
    logger.info("[INFO] Préparation du payload ia_models pour Fabric...")

    if not MODELS_DIR.exists():
        logger.warning(f"[WARNING] Dossier modèles introuvable : {MODELS_DIR}")
        return IaModelsSyncResponse(total=0, generated_at=datetime.utcnow(), rows=[])

    rows: List[IaModelsSyncItem] = []

    for pkl_file in MODELS_DIR.glob("*_latest.pkl"):
        filename = pkl_file.stem
        prm = None

        # Extrait un PRM sur 14 chiffres depuis le nom du fichier
        for token in filename.replace("prophet_model_", "").split("_"):
            if token.isdigit() and len(token) == 14:
                prm = token
                break

        if not prm:
            logger.warning(f"[WARNING] PRM non détecté pour : {pkl_file.name}")
            continue

        mlflow_data = get_mlflow_metrics(prm)
        metrics = mlflow_data.get("metrics", {})
        created_at = mlflow_data.get("created_at", datetime.utcfromtimestamp(pkl_file.stat().st_mtime))

        rows.append(
            IaModelsSyncItem(
                id_modele=mlflow_data.get("run_id", str(uuid.uuid4())),
                prm=prm,
                nom_modele=mlflow_data.get("params", {}).get("model_name", "prophet"),
                version_modele=created_at.strftime("%Y.%m.%d.1"),
                uri=str(pkl_file),
                date_creation=created_at,
                is_active=True,
                mae=metrics.get("mae"),
                rmse=metrics.get("rmse"),
                mape=metrics.get("mape"),
            )
        )

    # Trie par date de création décroissante pour simplifier le contrôle côté Fabric
    rows.sort(key=lambda item: item.date_creation, reverse=True)

    logger.info(f"[INFO] Payload Fabric prêt : {len(rows)} ligne(s)")
    return IaModelsSyncResponse(
        total=len(rows),
        generated_at=datetime.utcnow(),
        rows=rows,
    )
# ============================================================

@router.get(
    "/list",
    response_model=ModelsListResponse,
    summary="Lister les modèles disponibles",
)
async def list_available_models() -> ModelsListResponse:
    """
    Liste tous les modèles Prophet disponibles en local.

    Recherche les fichiers :
        prophet_model_{prm}_latest.pkl
    """
    logger.info("[INFO] Recherche des modèles disponibles en local...")

    try:
        if not MODELS_DIR.exists():
            logger.warning(f"[WARNING] Dossier des modèles introuvable : {MODELS_DIR}")
            return {"total": 0, "models": []}

        models = []

        # Parcourt tous les fichiers *_latest.pkl
        for pkl_file in MODELS_DIR.glob("*_latest.pkl"):

            # Extraction du PRM depuis le nom du fichier
            filename = pkl_file.stem
            prefix = filename.replace("prophet_model_", "").replace("_latest", "")

            # Recherche d’un PRM valide (14 chiffres)
            for token in prefix.split("_"):
                if token.isdigit() and len(token) == 14:
                    models.append({
                        "prm": token,
                        "model_path": str(pkl_file),
                        "exists": True
                    })
                    break

        logger.info(f"[INFO] {len(models)} modèle(s) trouvé(s)")

        return {
            "total": len(models),
            "models": models
        }

    except Exception as e:
        logger.error(f"[ERREUR] Échec du listage des modèles : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ROUTE 2 : Lire le modèle actif d’un PRM
# ============================================================

@router.get(
    "/prm/{prm}",
    response_model=ModelRegistryResponse,
    summary="Lire le modèle actif d’un PRM",
)
async def get_active_model(prm: str) -> ModelRegistryResponse:
    """
    Récupère le modèle actif pour un PRM.

    Stratégie :
    1. Essayer Fabric (source officielle)
    2. Sinon fallback sur fichier local
    """
    logger.info(f"[INFO] Lecture du modèle actif pour le PRM : {prm}")

    try:
        # -------------------------------------------------------
        # 1) Tentative via Fabric
        # -------------------------------------------------------
        try:
            conn = get_db_connection()
            repo = FabricRepository(conn)

            result = repo.get_active_model(prm)
            conn.close()

            if result:
                logger.info("[INFO] Modèle trouvé dans Fabric")

                return ModelRegistryResponse(**result)

        except Exception as e:
            logger.warning(f"[WARNING] Fabric indisponible → fallback local ({type(e).__name__})")

        # -------------------------------------------------------
        # 2) Fallback : modèle local
        # -------------------------------------------------------
        local_pkl = MODELS_DIR / f"prophet_model_{prm}_latest.pkl"

        if not local_pkl.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Aucun modèle trouvé pour le PRM : {prm}"
            )

        mlflow_data = get_mlflow_metrics(prm)

        logger.info("[INFO] Modèle trouvé en local")

        return ModelRegistryResponse(
            model_id=mlflow_data.get("run_id", str(uuid.uuid4())),
            prm=prm,
            model_name=mlflow_data.get("params", {}).get("model_name", "prophet"),
            model_version=datetime.utcnow().strftime("%Y.%m.%d.1"),
            artifact_uri=str(local_pkl),
            created_at=mlflow_data.get("created_at", datetime.utcnow()),
            is_active=True
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"[ERREUR] Lecture du modèle impossible pour {prm} : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))