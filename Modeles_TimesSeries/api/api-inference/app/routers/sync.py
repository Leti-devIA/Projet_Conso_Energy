"""
Routes de synchronisation des données depuis l'API Dataclean.

Rôle :
------
Permet de récupérer les données historiques de consommation (PRM)
et de les stocker localement sous forme de fichiers CSV.

Pipeline :
----------
Dataclean API → téléchargement CSV → stockage local → utilisation ultérieure
"""

import re
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.main import DATACLEAN_BASE_URL, RAW_SITES_DIR, require_api_key


# ============================================================
# INITIALISATION ROUTER
# ============================================================

router = APIRouter(prefix="/sync", tags=["sync"])

# PRM Enedis = 14 chiffres
PRM_PATTERN = re.compile(r"^\d{14}$")


# ============================================================
# UTILITAIRE : compter les lignes d’un CSV
# ============================================================

def _count_rows(csv_path: Path) -> int:
    """
    Compte le nombre de lignes dans un fichier CSV (hors en-tête).

    Utilité :
    - fournir un retour clair au frontend/dashboard
    - vérifier le volume de données importées
    """
    with csv_path.open("r", encoding="utf-8", errors="ignore") as file:
        line_count = sum(1 for _ in file)

    return max(0, line_count - 1)


# ============================================================
# ROUTE : Synchronisation PRM
# ============================================================

@router.post("/prm/{prm}")
def sync_prm(prm: str, _: str = Depends(require_api_key)) -> dict:
    """
    Synchronise l'historique de consommation pour un PRM donné.

    Étapes :
    1. Validation du PRM
    2. Appel API Dataclean
    3. Téléchargement du CSV (streaming)
    4. Sauvegarde en local
    5. Retour d'information (nombre de lignes)

    Avantage :
    - Streaming → évite de charger le fichier entier en mémoire
    """

    # -------------------------------------------------------
    # 1) Validation PRM
    # -------------------------------------------------------
    if not PRM_PATTERN.match(prm):
        raise HTTPException(status_code=422, detail="PRM invalide (14 chiffres requis)")

    # -------------------------------------------------------
    # 2) Préparation chemin de stockage
    # -------------------------------------------------------
    target_path = RAW_SITES_DIR / f"dataclean_prm_{prm}.csv"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    source_url = f"{DATACLEAN_BASE_URL}/dataclean/allbyprm"

    try:
        # -------------------------------------------------------
        # 3) Téléchargement en streaming
        # -------------------------------------------------------
        with httpx.Client(timeout=120.0) as client:
            with client.stream("GET", source_url, params={"prm": prm}) as response:
                response.raise_for_status()

                # -------------------------------------------------------
                # 4) Écriture du fichier CSV
                # -------------------------------------------------------
                with target_path.open("wb") as output_file:
                    for chunk in response.iter_bytes():
                        output_file.write(chunk)

    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur API Dataclean ({exc.response.status_code})"
        )

    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="API Dataclean indisponible")

    # -------------------------------------------------------
    # 5) Retour résultat
    # -------------------------------------------------------
    return {
        "message": "Synchronisation réussie",
        "prm": prm,
        "file_path": str(target_path),
        "rows": _count_rows(target_path)
    }