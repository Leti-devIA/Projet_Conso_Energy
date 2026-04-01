"""
Routes pour gérer les modèles Prophet vers Fabric Warehouse.

Endpoints :
    GET  /models/list                  → lister tous les modèles _latest.pkl
    GET  /models/prm/{prm}             → lire le modèle actif depuis Fabric
    POST /models/prm/{prm}/push        → push 1 modèle + MLflow metrics → Fabric
    POST /models/push-all              → push tous les modèles trouvés
"""

import uuid
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List

import mlflow
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel

from app.security import require_api_key
from app.repository.fabric_repository import FabricRepository
from app.config.database import get_db_connection
from app.config.fabric_automation import automate_onelake_upload_and_notebook
from app.project_paths import resolve_project_root

# Logs
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])

# ============================================================
# Chemins
# ============================================================
PROJECT_ROOT = resolve_project_root(Path(__file__))
MODELS_DIR = PROJECT_ROOT / "models" / "saved"
FABRIC_OUTBOX_PATH = PROJECT_ROOT / "exports" / "fabric_outbox.jsonl"


# ============================================================
# Schémas Pydantic
# ============================================================

class ModelPushResponse(BaseModel):
    """Réponse après un push réussi"""
    model_id: str
    prm: str
    model_name: str
    model_version: str
    artifact_uri: str
    created_at: datetime
    is_active: bool
    metrics_count: int
    message: str


class ModelRegistryResponse(BaseModel):
    """Modèle actif depuis Fabric"""
    model_id: str
    prm: str
    model_name: str
    model_version: str
    artifact_uri: str
    created_at: datetime
    is_active: bool


class BulkPushResponse(BaseModel):
    """Résumé du push en masse"""
    total: int
    successful: int
    failed: int
    results: List[dict]


class ModelsListResponse(BaseModel):
    """Réponse pour la liste des modèles disponibles"""
    total: int
    models: List[dict]


# ============================================================
# Utilitaires : MLflow
# ============================================================

def get_mlflow_metrics(prm: str) -> dict:
    """
    📊 Récupère les métriques du dernier run MLflow pour un PRM.

    Returns:
        Dict avec {run_id, metrics, params, created_at}
        ou {} si aucun run trouvé
    """
    logger.info(f"📊 Lecture MLflow pour {prm}...")

    try:
        # Import settings pour obtenir le MLFLOW_TRACKING_URI correct
        from app.settings import MLFLOW_TRACKING_URI

        logger.info(f"   → Connexion à MLflow : {MLFLOW_TRACKING_URI}")
        mlflow.set_tracking_uri(MLFLOW_TRACKING_URI)
        client = mlflow.tracking.MlflowClient()

        # Cherche l'expérience Prophet
        experiments = client.search_experiments()

        for exp in experiments:
            # Cherche un run avec ce PRM dans les params
            runs = client.search_runs(
                experiment_ids=[exp.experiment_id],
                filter_string=f"params.prm = '{prm}'",
                order_by=["start_time DESC"],
                max_results=1
            )

            if runs:
                run = runs[0]
                logger.info(f"✅ Run MLflow trouvé : {run.info.run_id[:8]}...")

                return {
                    "run_id": run.info.run_id,
                    "metrics": run.data.metrics,
                    "params": run.data.params,
                    "created_at": datetime.utcfromtimestamp(run.info.start_time / 1000)
                }

        logger.warning(f"⚠️ Aucun run MLflow trouvé pour prm={prm}")
        return {}

    except Exception as e:
        logger.error(f"❌ Erreur lecture MLflow : {str(e)}")
        return {}


def append_fabric_outbox_record(payload: dict) -> None:
    """Stocke localement l'intention d'écriture Fabric pour ingestion ultérieure."""
    payload = dict(payload)
    payload.setdefault("event_id", str(uuid.uuid4()))
    payload.setdefault("queued_at", datetime.utcnow().isoformat())

    FABRIC_OUTBOX_PATH.parent.mkdir(parents=True, exist_ok=True)
    with FABRIC_OUTBOX_PATH.open("a", encoding="utf-8") as outbox:
        outbox.write(json.dumps(payload, ensure_ascii=False, default=str) + "\n")


# ============================================================
# ROUTE 0 : Lister tous les modèles disponibles
# ============================================================

@router.get(
    "/list",
    response_model=ModelsListResponse,
    summary="📋 Lister tous les modèles _latest.pkl disponibles",
    description="""
    Retourne la liste de tous les modèles Prophet entraînés (fichiers _latest.pkl).

    Utile pour Fabric pour itérer sur tous les modèles et les charger dans ia_modeles.
    """,
)
async def list_available_models() -> ModelsListResponse:
    """
    Liste tous les modèles _latest.pkl disponibles en local.

    Returns:
        {
            "total": int,
            "models": [
                {
                    "prm": "30000250086126",
                    "model_path": "/models/saved/prophet_model_30000250086126_latest.pkl",
                    "exists": true
                },
                ...
            ]
        }
    """
    logger.info(f"📋 Listage des modèles disponibles...")

    try:
        # Cherche tous les fichiers *_latest.pkl dans MODELS_DIR
        if not MODELS_DIR.exists():
            logger.warning(f"⚠️ Répertoire modèles {MODELS_DIR} n'existe pas")
            return {"total": 0, "models": []}

        models = []
        for pkl_file in MODELS_DIR.glob("*_latest.pkl"):
            # Extrait le PRM du nom de fichier
            # Format : prophet_model_{prm}_latest.pkl
            filename = pkl_file.stem  # retire .pkl
            parts = filename.split("_latest")
            if len(parts) > 0:
                prefix = parts[0].replace("prophet_model_", "")
                # Essaie d'extraire le PRM (dernier groupe de 14 chiffres)
                for token in prefix.split("_"):
                    if token.isdigit() and len(token) == 14:
                        prm = token
                        models.append({
                            "prm": prm,
                            "model_path": str(pkl_file),
                            "exists": True
                        })
                        break

        logger.info(f"✅ {len(models)} modèle(s) trouvé(s)")
        return {
            "total": len(models),
            "models": models
        }

    except Exception as e:
        logger.error(f"❌ Erreur listage modèles : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# # ============================================================
# # ROUTE 1 : Push 1 modèle vers Fabric
# # ============================================================

# @router.post(
#     "/prm/{prm}/push",
#     response_model=ModelPushResponse,
#     summary="📤 Enregistrer 1 modèle vers Fabric",
#     description="""
#     Push le modèle Prophet + métriques MLflow d'un PRM vers Fabric :

#     1. Récupère le .pkl local (`models/saved/prophet_model_{prm}_latest.pkl`)
#     2. Récupère les métriques MLflow (run_id, MAE, RMSE, etc.)
#     3. Écrit dans `ia.model_registry` (désactive l'ancienne version)
#     4. Écrit dans `ia.training_metrics`

#     **Authentification** : X-API-Key obligatoire
#     """,
# )
# async def push_model(
#     prm: str,
#     x_api_key: str = Header(..., alias="X-API-Key"),
# ) -> ModelPushResponse:
#     """
#     Endpoint : POST /models/prm/{prm}/push

#     Exemple cURL :
#     ```bash
#     curl -X POST http://127.0.0.1:8001/models/prm/30000250086126/push \\
#       -H "X-API-Key: dev-inference-key"
#     ```
#     """

#     # -------------------------------------------------------
#     # 1) Vérif authentification
#     # -------------------------------------------------------
#     try:
#         require_api_key(x_api_key)
#     except Exception as e:
#         raise HTTPException(status_code=401, detail=str(e))

#     # -------------------------------------------------------
#     # 2) Vérif existence du modèle local
#     # -------------------------------------------------------
#     local_pkl = MODELS_DIR / f"prophet_model_{prm}_latest.pkl"

#     if not local_pkl.exists():
#         raise HTTPException(
#             status_code=404,
#             detail=f"Modèle non trouvé : {local_pkl}"
#         )

#     logger.info(f"🔄 Push modèle {prm}...")

#     try:
#         # -------------------------------------------------------
#         # 3) Récupère métriques MLflow
#         # -------------------------------------------------------
#         mlflow_data = get_mlflow_metrics(prm)

#         model_id = mlflow_data.get("run_id", str(uuid.uuid4()))
#         created_at = mlflow_data.get("created_at", datetime.utcnow())
#         metrics = mlflow_data.get("metrics", {})
#         params = mlflow_data.get("params", {})

#         # Pour OneLake (simulation : on utilise juste le chemin local)
#         artifact_uri = str(local_pkl)

#         # -------------------------------------------------------
#         # 4) Écrit dans Fabric Warehouse (via FabricRepository)
#         # -------------------------------------------------------
#         logger.info(f"   📝 Model : {params.get('model_name', 'prophet')}")
#         logger.info(f"   📝 Version : {created_at.strftime('%Y.%m.%d.1')}")
#         logger.info(f"   📝 Métriques : {len(metrics)} trouvée(s)")
#         used_outbox = False
#         conn = None

#         try:
#             # Récupère connexion Fabric
#             conn = get_db_connection()
#             logger.info("✅ Connexion Fabric établie")

#             # Crée repository
#             repo = FabricRepository(conn)

#             # Écrit registry
#             logger.info(f"   → Upsert dans ia.model_registry...")
#             repo.upsert_model_registry(
#                 model_id=model_id,
#                 prm=prm,
#                 model_name=params.get("model_name", "prophet"),
#                 model_version=created_at.strftime("%Y.%m.%d.1"),
#                 artifact_uri=artifact_uri,
#                 created_at=created_at,
#                 is_active=True
#             )
#             logger.info("   ✅ ia.model_registry upsertée")

#             # Écrit métriques
#             logger.info(f"   → Insert {len(metrics)} métrique(s) dans ia.training_metrics...")
#             metrics_count = repo.insert_training_metrics(
#                 model_id=model_id,
#                 prm=prm,
#                 metrics=metrics,
#                 measured_at=created_at
#             )
#             logger.info(f"   ✅ {metrics_count} métrique(s) insérée(s)")

#             # Ferme connexion
#             conn.close()

#         except ValueError as e:
#             # Fabric env vars manquantes
#             logger.warning(f"⚠️  Fabric non configuré : {str(e)}")
#             logger.warning("   → Modèle enregistré localement seulement (pas de Fabric)")
#             metrics_count = len(metrics)

#         except FabricDmlNotSupportedError as e:
#             logger.warning(f"⚠️  Fabric Lakehouse SQL endpoint en lecture seule DML : {str(e)}")
#             used_outbox = True
#             append_fabric_outbox_record({
#                 "event_type": "model_push",
#                 "queued_at": datetime.utcnow().isoformat(),
#                 "prm": prm,
#                 "model": {
#                     "model_id": model_id,
#                     "model_name": params.get("model_name", "prophet"),
#                     "model_version": created_at.strftime("%Y.%m.%d.1"),
#                     "artifact_uri": artifact_uri,
#                     "created_at": created_at,
#                     "is_active": True,
#                 },
#                 "metrics": metrics,
#                 "measured_at": created_at,
#                 "reason": "Fabric SQL endpoint does not support DML for this table type (24559)",
#             })
#             logger.warning(f"   📨 Écriture placée dans l'outbox locale : {FABRIC_OUTBOX_PATH}")
#             try:
#                 automation_result = automate_onelake_upload_and_notebook(FABRIC_OUTBOX_PATH)
#                 if automation_result.get("enabled"):
#                     logger.info("   🚀 Upload OneLake + trigger Notebook exécutés")
#                 else:
#                     logger.info("   ℹ️ Automatisation Fabric désactivée (FABRIC_AUTOMATION_ENABLED=false)")
#             except Exception as automation_error:
#                 logger.warning(f"   ⚠️ Automatisation Fabric échouée : {str(automation_error)}")
#             metrics_count = len(metrics)

#         except Exception as e:
#             logger.error(f"❌ Erreur écriture Fabric : {str(e)}")
#             raise HTTPException(status_code=503, detail=f"Fabric Warehouse unavailable: {str(e)}")
#         finally:
#             if conn:
#                 try:
#                     conn.close()
#                 except Exception:
#                     pass

#         logger.info(f"✅ {prm} enregistré : {metrics_count} métrique(s)")

#         return ModelPushResponse(
#             model_id=model_id,
#             prm=prm,
#             model_name=params.get("model_name", "prophet"),
#             model_version=created_at.strftime("%Y.%m.%d.1"),
#             artifact_uri=artifact_uri,
#             created_at=created_at,
#             is_active=True,
#             metrics_count=metrics_count,
#             message=("✅ Modèle enregistré (outbox locale)" if used_outbox else "✅ Modèle enregistré avec succès")
#         )

#     except FileNotFoundError as e:
#         raise HTTPException(status_code=404, detail=str(e))
#     except Exception as e:
#         logger.error(f"❌ Erreur push {prm} : {str(e)}")
#         raise HTTPException(status_code=500, detail=f"Erreur serveur : {str(e)}")


# # ============================================================
# # ROUTE 2 : Push tous les modèles
# # ============================================================

# @router.post(
#     "/push-all",
#     response_model=BulkPushResponse,
#     summary="📤 Enregistrer tous les modèles vers Fabric",
#     description="""
#     Lance le push de **tous** les modèles trouvés dans `models/saved/`.

#     Chaque modèle est traité séquentiellement.
#     """
# )
# async def push_all_models(
#     x_api_key: str = Header(..., alias="X-API-Key"),
# ) -> BulkPushResponse:
#     """
#     Endpoint : POST /models/push-all

#     Exemple cURL :
#     ```bash
#     curl -X POST http://127.0.0.1:8001/models/push-all \\
#       -H "X-API-Key: dev-inference-key"
#     ```
#     """

#     # -------------------------------------------------------
#     # 1) Vérif authentification
#     # -------------------------------------------------------
#     try:
#         require_api_key(x_api_key)
#     except Exception as e:
#         raise HTTPException(status_code=401, detail=str(e))

#     logger.info("🔄 Push en masse : tous les modèles...")

#     # -------------------------------------------------------
#     # 2) Découvre tous les modèles locaux
#     # -------------------------------------------------------
#     if not MODELS_DIR.exists():
#         raise HTTPException(
#             status_code=404,
#             detail=f"Dossier models/saved introuvable : {MODELS_DIR}"
#         )

#     # Retrouve les .pkl de type "prophet_model_{prm}_latest.pkl"
#     model_files = list(MODELS_DIR.glob("prophet_model_*_latest.pkl"))

#     if not model_files:
#         raise HTTPException(
#             status_code=404,
#             detail="Aucun modèle trouvé dans models/saved/"
#         )

#     logger.info(f"🔍 {len(model_files)} modèle(s) découvert(s)")

#     # -------------------------------------------------------
#     # 3) Push chaque modèle en séquence
#     # -------------------------------------------------------
#     results = []
#     successful = 0
#     failed = 0

#     # Récupère connexion Fabric une seule fois
#     conn = None
#     try:
#         conn = get_db_connection()
#         logger.info("✅ Connexion Fabric établie pour bulk push")
#     except ValueError as e:
#         logger.warning(f"⚠️  Fabric non configuré : {str(e)}")
#         logger.warning("   → Les modèles seront enregistrés localement seulement")

#     for pkl_file in model_files:
#         # Extrait le PRM du nom du fichier
#         prm = pkl_file.stem.replace("prophet_model_", "").replace("_latest", "")

#         try:
#             logger.info(f"  → Push {prm}...")

#             # Récupère métriques
#             mlflow_data = get_mlflow_metrics(prm)

#             model_id = mlflow_data.get("run_id", str(uuid.uuid4()))
#             created_at = mlflow_data.get("created_at", datetime.utcnow())
#             metrics = mlflow_data.get("metrics", {})
#             params = mlflow_data.get("params", {})

#             metrics_count = len(metrics)

#             # Écrit dans Fabric si disponible
#             if conn:
#                 try:
#                     repo = FabricRepository(conn)
#                     repo.upsert_model_registry(
#                         model_id=model_id,
#                         prm=prm,
#                         model_name=params.get("model_name", "prophet"),
#                         model_version=created_at.strftime("%Y.%m.%d.1"),
#                         artifact_uri=str(pkl_file),
#                         created_at=created_at,
#                         is_active=True
#                     )
#                     metrics_count = repo.insert_training_metrics(
#                         model_id=model_id,
#                         prm=prm,
#                         metrics=metrics,
#                         measured_at=created_at
#                     )
#                     logger.info(f"     ✅ Fabric upsert OK ({metrics_count} metrics)")
#                 except FabricDmlNotSupportedError as e:
#                     logger.warning(f"     ⚠️  DML non supporté, fallback outbox : {str(e)}")
#                     append_fabric_outbox_record({
#                         "event_type": "model_push_bulk",
#                         "queued_at": datetime.utcnow().isoformat(),
#                         "prm": prm,
#                         "model": {
#                             "model_id": model_id,
#                             "model_name": params.get("model_name", "prophet"),
#                             "model_version": created_at.strftime("%Y.%m.%d.1"),
#                             "artifact_uri": str(pkl_file),
#                             "created_at": created_at,
#                             "is_active": True,
#                         },
#                         "metrics": metrics,
#                         "measured_at": created_at,
#                         "reason": "Fabric SQL endpoint does not support DML for this table type (24559)",
#                     })
#                     logger.warning(f"     📨 Outbox locale : {FABRIC_OUTBOX_PATH}")
#                     try:
#                         automation_result = automate_onelake_upload_and_notebook(FABRIC_OUTBOX_PATH)
#                         if automation_result.get("enabled"):
#                             logger.info("     🚀 Upload OneLake + trigger Notebook exécutés")
#                         else:
#                             logger.info("     ℹ️ Automatisation Fabric désactivée")
#                     except Exception as automation_error:
#                         logger.warning(f"     ⚠️ Automatisation Fabric échouée : {str(automation_error)}")
#                     metrics_count = len(metrics)
#                 except Exception as e:
#                     logger.error(f"     ⚠️  Fabric write failed : {str(e)}")
#                     # On continue quand même

#             results.append({
#                 "prm": prm,
#                 "success": True,
#                 "message": f"✅ Enregistré ({metrics_count} métrique(s))"
#             })
#             successful += 1

#         except Exception as e:
#             logger.error(f"  ❌ {prm} : {str(e)}")
#             results.append({
#                 "prm": prm,
#                 "success": False,
#                 "message": f"❌ {str(e)[:100]}"
#             })
#             failed += 1

#     # Ferme connexion
#     if conn:
#         try:
#             conn.close()
#             logger.info("✅ Connexion Fabric fermée")
#         except:
#             pass

#     logger.info(f"✅ Push en masse terminé : {successful}/{len(model_files)} réussi(s)")

#     return BulkPushResponse(
#         total=len(model_files),
#         successful=successful,
#         failed=failed,
#         results=results
#     )


# ============================================================
# ROUTE 3 : Lire le modèle actif d'un PRM
# ============================================================

@router.get(
    "/prm/{prm}",
    response_model=ModelRegistryResponse,
    summary="📖 Lire le modèle actif d'un PRM",
    description="""
    Récupère l'enregistrement du **modèle actif** depuis `ia.model_registry`.

    Utile pour :
    - vérifier quel modèle est utilisé pour les prédictions
    - récupérer le chemin OneLake du .pkl
    """,
)
async def get_active_model(prm: str) -> ModelRegistryResponse:
    """
    Endpoint : GET /models/prm/{prm}

    Exemple cURL :
    ```bash
    curl http://127.0.0.1:8001/models/prm/30000250086126
    ```
    """

    logger.info(f"📖 Lecture modèle actif pour {prm}...")

    try:
        # Tente d'abord Fabric
        try:
            conn = get_db_connection()
            repo = FabricRepository(conn)
            result = repo.get_active_model(prm)
            conn.close()

            if result:
                logger.info(f"✅ Modèle trouvé dans Fabric")
                return ModelRegistryResponse(
                    model_id=result["model_id"],
                    prm=result["prm"],
                    model_name=result["model_name"],
                    model_version=result["model_version"],
                    artifact_uri=result["artifact_uri"],
                    created_at=result["created_at"],
                    is_active=result["is_active"]
                )
        except Exception as e:
            # Fabric non configuré ou ODBC driver manquant, essaie local
            logger.warning(f"⚠️  Fabric indisponible ({type(e).__name__}), utilise fichier local")
            pass

        # Fallback : fichier local
        local_pkl = MODELS_DIR / f"prophet_model_{prm}_latest.pkl"

        if not local_pkl.exists():
            raise HTTPException(
                status_code=404,
                detail=f"Aucun modèle trouvé pour {prm}"
            )

        mlflow_data = get_mlflow_metrics(prm)
        model_id = mlflow_data.get("run_id", str(uuid.uuid4()))
        created_at = mlflow_data.get("created_at", datetime.utcnow())
        params = mlflow_data.get("params", {})

        logger.info(f"✅ Modèle trouvé en local")

        return ModelRegistryResponse(
            model_id=model_id,
            prm=prm,
            model_name=params.get("model_name", "prophet"),
            model_version=created_at.strftime("%Y.%m.%d.1"),
            artifact_uri=str(local_pkl),
            created_at=created_at,
            is_active=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Erreur lecture modèle {prm} : {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
