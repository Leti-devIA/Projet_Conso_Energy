import re
from pathlib import Path

import httpx
from fastapi import APIRouter, Depends, HTTPException

from app.security import require_api_key
from app.settings import DATACLEAN_BASE_URL, RAW_SITES_DIR

router = APIRouter(prefix="/sync", tags=["sync"])

# PRM Enedis : 14 chiffres exactement
PRM_PATTERN = re.compile(r"^\d{14}$")


def _count_rows(csv_path: Path) -> int:
    """
    Compte les lignes de données d'un CSV (hors en-tête).
    Utile pour retourner une information claire au dashboard.
    """
    with csv_path.open("r", encoding="utf-8", errors="ignore") as file:
        line_count = sum(1 for _ in file)

    return max(0, line_count - 1)


@router.post(
    "/prm/{prm}",
    summary="Synchroniser un historique PRM depuis l'API dataclean",
    description=(
        "Télécharge le CSV depuis /dataclean/allbyprm?prm=... puis le sauvegarde "
        "dans data/raw/sites/dataclean_prm_{prm}.csv."
    )
)
def sync_prm(prm: str, _: str = Depends(require_api_key)) -> dict:
    """
    Étapes de la synchronisation :
    1) valider le format du PRM,
    2) appeler l'API dataclean,
    3) streamer le CSV vers un fichier local,
    4) retourner le nombre de lignes importées.
    """
    if not PRM_PATTERN.match(prm):
        raise HTTPException(status_code=422, detail="Le PRM doit contenir exactement 14 chiffres")

    target_path = RAW_SITES_DIR / f"dataclean_prm_{prm}.csv"
    target_path.parent.mkdir(parents=True, exist_ok=True)

    source_url = f"{DATACLEAN_BASE_URL}/dataclean/allbyprm"

    try:
        # Streaming HTTP -> écriture disque : évite de charger un gros CSV en RAM
        with httpx.Client(timeout=120.0) as client:
            with client.stream("GET", source_url, params={"prm": prm}) as response:
                response.raise_for_status()
                with target_path.open("wb") as output_file:
                    for chunk in response.iter_bytes():
                        output_file.write(chunk)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Erreur dataclean ({exc.response.status_code})"
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Dataclean API indisponible") from exc

    return {
        "message": "Synchronisation réussie",
        "prm": prm,
        "file_path": str(target_path),
        "rows": _count_rows(target_path)
    }
