from asyncio.log import logger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers.dataclean import router as dataclean_router
from app.config.database import connect_database
from dotenv import load_dotenv
import uvicorn

# Charger les variables d'environnement
load_dotenv()

app = FastAPI(
    title="Projet Consommation Energetique - API",
    description="API pour l'export des données provenant de Microsoft Fabric, incluant les données historiques d'Enedis et les prévisions météo.",
    version="1.0.0"
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "API dataclean ok"}

@app.on_event("startup")
async def startup():
    """Initialisation de l'application"""
    logger.info("Démarrage de l'API")
    print("Démarrage de l'API...")
    await connect_database()

@app.get("/")
def root():
    return {"status": "Bienvenue à l'API de data Enedis-Météo"}

# Routes
app.include_router(dataclean_router, prefix="/dataclean", tags=["Données nettoyées"])


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )