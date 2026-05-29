"""
Route de vérification de l’état de l’API (health check).

Objectif :
----------
Permet de vérifier rapidement si l’API est opérationnelle.
Utilisée par :
- outils de monitoring
- orchestrateurs (Docker, Kubernetes)
- tests simples (ping API)
"""

from fastapi import APIRouter

# Création du routeur
router = APIRouter()


# ============================================================
# ROUTE : Health Check
# ============================================================

@router.get(
    "/health",
    summary="État de l’API",
    description="Vérifie rapidement que l’API répond.",
    response_description="API disponible",
)
def health() -> dict:
    """
    Endpoint de santé de l'API.

    Retour :
        {
            "status": "ok tout va bien"
        }

    Utilité :
    - Vérifier que l'API répond
    - Tester la disponibilité du service
    """
    return {"status": "ok tout va bien"}