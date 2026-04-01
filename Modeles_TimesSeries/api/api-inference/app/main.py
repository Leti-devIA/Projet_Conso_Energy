import sys
from pathlib import Path
from app.project_paths import resolve_project_root

# -------------------------------------------------------
# On ajoute Modeles_TimesSeries/ au path Python
# pour que les imports de src/ fonctionnent partout
# -------------------------------------------------------
PROJECT_ROOT = resolve_project_root(Path(__file__))
sys.path.insert(0, str(PROJECT_ROOT))

# On change aussi le dossier courant pour que config/config.yaml soit trouvé
import os
os.chdir(PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.health import router as health_router
from app.routers.predict import router as predict_router
from app.routers.models import router as models_router
from app.routers.sync import router as sync_router
from app.settings import CORS_ORIGINS

# ---------------------------------------------------------------------
# Application principale FastAPI
# ---------------------------------------------------------------------
# Cette API joue le rôle de "pont" entre :
# 1) API dataclean (source des historiques),
# 2) pipeline de prédiction (génération météo + modèle Prophet),
# 3) dashboard (consommation des résultats via endpoint JSON).
app = FastAPI(
    title="API Inference - Projet Conso Energ",
    description="API REST pour synchroniser les données dataclean, lancer les prédictions et servir le dashboard.",
    version="1.0.0"
)

# CORS : autorise le dashboard (ou plusieurs origines séparées par virgule)
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

app.include_router(health_router)
app.include_router(sync_router)
app.include_router(predict_router)
app.include_router(models_router)

@app.get("/")
def root() -> dict:
    """Point d'entrée simple pour vérifier que l'API répond."""
    return {"status": "API inference prête"}
