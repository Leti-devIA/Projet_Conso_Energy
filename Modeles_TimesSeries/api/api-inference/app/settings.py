import os
import json
from pathlib import Path
from dotenv import load_dotenv
from app.project_paths import resolve_project_root

# Charge le fichier .env
env_file = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(env_file)

PROJECT_ROOT = resolve_project_root(Path(__file__))

DATACLEAN_BASE_URL = os.getenv("DATACLEAN_BASE_URL", "http://127.0.0.1:8000")
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"
RAW_SITES_DIR = PROJECT_ROOT / "data" / "raw" / "sites"
RAW_METEO_DIR = PROJECT_ROOT / "data" / "raw" / "meteo"
PREDICTIONS_DIR = PROJECT_ROOT / "data" / "predictions"
MODELS_DIR = PROJECT_ROOT / "models" / "saved"

CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")

# ============================================================
# MLflow Tracking (local directory with file:// scheme)
# ============================================================
_mlflow_uri = os.getenv("MLFLOW_TRACKING_URI", str(PROJECT_ROOT / "mlruns"))

# Resolve to absolute path first
if not os.path.isabs(_mlflow_uri):
    if "../" in _mlflow_uri or "..\\" in _mlflow_uri:
        # Relative path from settings.py location
        _mlflow_path = (Path(__file__).resolve().parent / _mlflow_uri).resolve()
    else:
        _mlflow_path = Path(_mlflow_uri).resolve()
else:
    _mlflow_path = Path(_mlflow_uri).resolve()

# Convert to file:// URI using as_uri() for proper Windows support
if not _mlflow_uri.startswith(("http://", "https://", "file://", "databricks")):
    MLFLOW_TRACKING_URI = _mlflow_path.as_uri()
else:
    MLFLOW_TRACKING_URI = _mlflow_uri

# ============================================================
# Fabric Warehouse (T-SQL via pyodbc)
# ============================================================
DB_SERVER = os.getenv("DB_SERVER")
DB_DATABASE = os.getenv("DB_DATABASE")


def _as_bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


# ============================================================
# Fabric automation (local API -> OneLake -> Notebook trigger)
# ============================================================
FABRIC_AUTOMATION_ENABLED = _as_bool(os.getenv("FABRIC_AUTOMATION_ENABLED", "false"))
FABRIC_TENANT_ID = os.getenv("FABRIC_TENANT_ID")
FABRIC_CLIENT_ID = os.getenv("FABRIC_CLIENT_ID")
FABRIC_CLIENT_SECRET = os.getenv("FABRIC_CLIENT_SECRET")

ONELAKE_WORKSPACE_NAME = os.getenv("ONELAKE_WORKSPACE_NAME")
ONELAKE_LAKEHOUSE_NAME = os.getenv("ONELAKE_LAKEHOUSE_NAME")
ONELAKE_OUTBOX_REMOTE_PATH = os.getenv("ONELAKE_OUTBOX_REMOTE_PATH", "Files/exports/fabric_outbox.jsonl")

FABRIC_WORKSPACE_ID = os.getenv("FABRIC_WORKSPACE_ID")
FABRIC_NOTEBOOK_ITEM_ID = os.getenv("FABRIC_NOTEBOOK_ITEM_ID")

_default_notebook_payload = {
    "executionData": {
        "parameters": {}
    }
}

_payload_raw = os.getenv("FABRIC_NOTEBOOK_TRIGGER_PAYLOAD_JSON")
if _payload_raw:
    try:
        FABRIC_NOTEBOOK_TRIGGER_PAYLOAD = json.loads(_payload_raw)
    except Exception:
        FABRIC_NOTEBOOK_TRIGGER_PAYLOAD = _default_notebook_payload
else:
    FABRIC_NOTEBOOK_TRIGGER_PAYLOAD = _default_notebook_payload
