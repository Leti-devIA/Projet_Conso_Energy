"""
Point d'entrée principal de l'API FastAPI.

Rôle de cette API :
-------------------
Cette API agit comme un "orchestrateur" entre :
1. API Dataclean → source de données historiques
2. Pipeline ML → prédictions (Prophet + météo)
3. Fabric / stockage → persistance des modèles
4. Dashboard → consommation via endpoints REST
"""

import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware


# ============================================================
# UTILITAIRE : Résolution de la racine projet
# ============================================================

def resolve_project_root(start: Path) -> Path:
    """
    Retrouve automatiquement la racine du projet.

    Logique :
    - Remonte dans les dossiers parents
    - Cherche un dossier contenant /src et /config
    """
    current = start.resolve()

    if current.is_file():
        current = current.parent

    for candidate in [current, *current.parents]:
        if (candidate / "src").exists() and (candidate / "config").exists():
            return candidate

    return current


# ============================================================
# CHARGEMENT ENVIRONNEMENT
# ============================================================

env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_file)

PROJECT_ROOT = resolve_project_root(Path(__file__))

# Ajoute le projet au PYTHONPATH
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Force le working directory
os.chdir(PROJECT_ROOT)


# ============================================================
# SÉCURITÉ : API KEY
# ============================================================

def require_api_key(x_api_key: str | None = Header(default=None)) -> str:
    """
    Protection simple des endpoints via clé API.

    Header attendu :
        X-API-Key: <clé>

    Valeur par défaut (dev) :
        dev-inference-key
    """
    expected_key = os.getenv("INFERENCE_API_KEY", "dev-inference-key")

    if x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Clé API invalide ou manquante",
        )

    return x_api_key


# ============================================================
# UTILITAIRE : conversion booléenne
# ============================================================

def _as_bool(value: str | None, default: bool = False) -> bool:
    """
    Convertit une variable d'environnement en booléen.

    Valeurs acceptées :
        true, 1, yes, y, on
    """
    if value is None:
        return default

    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# ============================================================
# VARIABLES DE CONFIGURATION
# ============================================================

# API externe
DATACLEAN_BASE_URL = os.getenv("DATACLEAN_BASE_URL", "http://127.0.0.1:8000")

# Chemins projet
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
RAW_SITES_DIR = PROJECT_ROOT / "data" / "raw" / "sites"
RAW_METEO_DIR = PROJECT_ROOT / "data" / "raw" / "meteo"
PREDICTIONS_DIR = PROJECT_ROOT / "data" / "predictions"
MODELS_DIR = PROJECT_ROOT / "models" / "saved"

# Outbox Fabric (fallback)
FABRIC_OUTBOX_PATH = PROJECT_ROOT / "exports" / "fabric_outbox.jsonl"

# CORS
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# MLflow
_mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", str(PROJECT_ROOT / "mlruns"))

if not _mlflow_uri.startswith(("http://", "https://", "file://", "databricks")):
    MLFLOW_TRACKING_URI = Path(_mlflow_uri).resolve().as_uri()
else:
    MLFLOW_TRACKING_URI = _mlflow_uri

# Base de données (Fabric)
DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")

# Fabric automation
FABRIC_AUTOMATION_ENABLED = _as_bool(os.getenv("FABRIC_AUTOMATION_ENABLED", "false"))
FABRIC_TENANT_ID = os.getenv("FABRIC_TENANT_ID")
FABRIC_CLIENT_ID = os.getenv("FABRIC_CLIENT_ID")
FABRIC_CLIENT_SECRET = os.getenv("FABRIC_CLIENT_SECRET")

# OneLake
ONELAKE_WORKSPACE_NAME = os.getenv("ONELAKE_WORKSPACE_NAME")
ONELAKE_LAKEHOUSE_NAME = os.getenv("ONELAKE_LAKEHOUSE_NAME")
ONELAKE_OUTBOX_REMOTE_PATH = os.getenv(
    "ONELAKE_OUTBOX_REMOTE_PATH",
    "Files/exports/fabric_outbox.jsonl",
)

# Notebook Fabric
FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
FABRIC_NOTEBOOK_ITEM_ID = os.getenv("FABRIC_NOTEBOOK_ITEM_ID")

# Payload pour déclencher un notebook Fabric
_default_notebook_payload = {"executionData": {"parameters": {}}}
_payload_raw = os.getenv("FABRIC_NOTEBOOK_TRIGGER_PAYLOAD_JSON")

if _payload_raw:
    try:
        FABRIC_NOTEBOOK_TRIGGER_PAYLOAD = json.loads(_payload_raw)
    except Exception:
        FABRIC_NOTEBOOK_TRIGGER_PAYLOAD = _default_notebook_payload
else:
    FABRIC_NOTEBOOK_TRIGGER_PAYLOAD = _default_notebook_payload


# ============================================================
# IMPORT DES ROUTERS (APIs)
# ============================================================

from app.routers.health import router as health_router
from app.routers.predict import router as predict_router
from app.routers.models import router as models_router
from app.routers.sync import router as sync_router


# ============================================================
# INITIALISATION FASTAPI
# ============================================================

app = FastAPI(
    title="API Inference - Projet Conso Energ",
    description="API REST pour synchroniser les données, lancer les prédictions et servir un dashboard.",
    version="1.0.0"
)


# ============================================================
# CONFIGURATION CORS
# ============================================================

origins = [origin.strip() for origin in CORS_ORIGINS.split(",") if origin.strip()]

if not origins:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ENREGISTREMENT DES ROUTES
# ============================================================

app.include_router(health_router)
app.include_router(sync_router)
app.include_router(predict_router)
app.include_router(models_router)


# ============================================================
# ROUTE RACINE
# ============================================================

@app.get("/")
def root() -> dict:
    """
    Endpoint de test pour vérifier que l'API fonctionne.
    """
    return {"status": "API inference prête"}