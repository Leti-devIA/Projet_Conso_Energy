from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.config.database import get_database_connection
from app.services.csv_export import stream_rows_to_csv
from app.repository.data_repository import get_rows_by_prm, get_all_previsions_meteo, get_all_sites
import asyncio
import traceback

router = APIRouter()


@router.get("/allbyprm")
async def export_all_by_prm(prm: str = Query(...)):
    """Export des données pour un PRM donné au format CSV"""
    print(f"📥 Requête reçue pour PRM: {prm}")

    connection = await get_database_connection()
    if not connection:
        print("❌ Pas de connexion à la base de données")
        raise HTTPException(status_code=503, detail="Base de données non disponible")

    try:
        print("✅ Connexion établie, exécution de la requête SQL...")

        # Exécuter la requête dans un executor car pyodbc est synchrone
        loop = asyncio.get_event_loop()
        cursor, columns = await loop.run_in_executor(
            None,
            get_rows_by_prm,
            connection,
            prm
        )

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(cursor, columns),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=dataclean_prm_{prm}.csv"
            }
        )

    except Exception as e:
        print(f"❌ ERREUR COMPLÈTE: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")


@router.get("/previsions-meteo")
async def export_previsions_meteo():
    """Export de toutes les prévisions météo au format CSV"""
    print("📥 Requête reçue pour export des prévisions météo")

    connection = await get_database_connection()
    if not connection:
        print("❌ Pas de connexion à la base de données")
        raise HTTPException(status_code=503, detail="Base de données non disponible")

    try:
        print("✅ Connexion établie, exécution de la requête SQL...")

        # Exécuter la requête dans un executor car pyodbc est synchrone
        loop = asyncio.get_event_loop()
        cursor, columns = await loop.run_in_executor(
            None,
            get_all_previsions_meteo,
            connection
        )

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(cursor, columns),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=previsions_meteo.csv"
            }
        )

    except Exception as e:
        print(f"❌ ERREUR COMPLÈTE: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")



@router.get("/sites")
async def export_sites():
    """Export de toutes les sites de l'entreprise au format CSV"""
    print("📥 Requête reçue pour export des sites")

    connection = await get_database_connection()
    if not connection:
        print("❌ Pas de connexion à la base de données")
        raise HTTPException(status_code=503, detail="Base de données non disponible")

    try:
        print("✅ Connexion établie, exécution de la requête SQL...")

        # Exécuter la requête dans un executor car pyodbc est synchrone
        loop = asyncio.get_event_loop()
        cursor, columns = await loop.run_in_executor(
            None,
            get_all_sites,
            connection
        )

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(cursor, columns),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=table_sites.csv"
            }
        )

    except Exception as e:
        print(f"❌ ERREUR COMPLÈTE: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")