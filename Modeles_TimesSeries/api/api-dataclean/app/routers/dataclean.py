from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.config.database import get_database_connection, close_database_connection
from app.services.csv_export import stream_rows_to_csv
from app.repository.data_repository import get_rows_by_prm, get_rows_by_prms, get_all_previsions_meteo, get_all_sites, get_all_prix_spot
import asyncio
import traceback
import pyodbc

router = APIRouter()


def _is_link_failure(error: Exception) -> bool:
    return isinstance(error, pyodbc.OperationalError) and "08S01" in str(error)


async def _execute_query_with_retry(query_fn, *args):
    loop = asyncio.get_event_loop()

    connection = await get_database_connection()
    if not connection:
        raise HTTPException(status_code=503, detail="Base de données non disponible")

    try:
        return await loop.run_in_executor(None, query_fn, connection, *args)
    except Exception as first_error:
        if not _is_link_failure(first_error):
            raise

        print("⚠️ Lien ODBC perdu (08S01), tentative de reconnexion...")
        await close_database_connection()

        connection = await get_database_connection()
        if not connection:
            raise HTTPException(status_code=503, detail="Base de données indisponible après reconnexion")

        try:
            return await loop.run_in_executor(None, query_fn, connection, *args)
        except Exception as second_error:
            if _is_link_failure(second_error):
                raise HTTPException(
                    status_code=503,
                    detail="Connexion SQL temporairement indisponible (ODBC 08S01)."
                )
            raise


@router.get(
    "/allbyprm",
    summary="Export CSV des données historiques Enedis + météo par PRM",
    description="Exporte en format CSV toutes les données pré-nettoyées de Microsoft Fabric pour un Point de Référence Mesure donné."
)
async def export_all_by_prm(prm: str = Query(...)):
    """Export des données pré-nettoyées pour un PRM donné au format CSV"""
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


@router.get(
    "/allbyprm-json",
    summary="Récupération JSON des données historiques Enedis + météo par PRM",
    description=(
        "Retourne les données d'un PRM au format JSON (liste d'objets), "
        "pour consommation directe par une API d'inférence sans passage par CSV."
    )
)
async def get_all_by_prm_json(prm: str = Query(...)):
    """Version JSON de /allbyprm, pensée pour les appels serveur-à-serveur."""
    print(f"📥 Requête JSON reçue pour PRM: {prm}")

    try:
        print("✅ Connexion établie, exécution de la requête SQL JSON...")

        loop = asyncio.get_event_loop()
        cursor, columns = await _execute_query_with_retry(get_rows_by_prm, prm)

        rows = await loop.run_in_executor(None, cursor.fetchall)
        records = []

        for row in rows:
            item = {}
            for idx, col in enumerate(columns):
                value = row[idx]
                # Conversion des types date/heure pour JSON
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                item[col] = value
            records.append(item)

        print(f"✅ {len(records)} ligne(s) retournée(s) en JSON")
        return {
            "prm": prm,
            "count": len(records),
            "rows": records
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"❌ ERREUR COMPLÈTE: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export JSON: {str(e)}")


@router.get(
    "/allbyprm-json-batch",
    summary="Récupération JSON de l'historique pour plusieurs PRM en un appel",
    description=(
        "Retourne les données historiques de plusieurs PRM au format JSON. "
        "Exemple d'appel : /dataclean/allbyprm-json-batch?prms=123&prms=456"
    )
)
async def get_all_by_prms_json(prms: list[str] = Query(...)):
    """Version batch de /allbyprm-json pour éviter un appel API par PRM."""
    normalized_prms = [str(prm).strip() for prm in prms if str(prm).strip()]
    normalized_prms = list(dict.fromkeys(normalized_prms))

    if not normalized_prms:
        raise HTTPException(status_code=400, detail="Le paramètre 'prms' est obligatoire.")

    print(f"📥 Requête JSON batch reçue pour {len(normalized_prms)} PRM(s)")

    try:
        loop = asyncio.get_event_loop()
        cursor, columns = await _execute_query_with_retry(get_rows_by_prms, normalized_prms)

        rows = await loop.run_in_executor(None, cursor.fetchall)
        records = []

        for row in rows:
            item = {}
            for idx, col in enumerate(columns):
                value = row[idx]
                if hasattr(value, "isoformat"):
                    value = value.isoformat()
                item[col] = value
            records.append(item)

        print(f"✅ {len(records)} ligne(s) batch retournée(s) en JSON")
        return {
            "prms": normalized_prms,
            "count": len(records),
            "rows": records,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"❌ ERREUR COMPLÈTE BATCH: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export JSON batch: {str(e)}")


@router.get(
        "/previsions-meteo",
        summary="Export CSV de toutes les prévisions météo des 15 prochains jours",
        description="Exporte en format CSV toutes les prévisions météo disponibles dans la table de Microsoft Fabric pour les 15 prochains jours."
)
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



@router.get(
        "/sites",
        summary="Export CSV de tous les sites de l'entreprise avec leur PRM associé",
        description="Exporte en format CSV toutes les sites de l'entreprise disponibles dans la table de Microsoft Fabric."
)
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


@router.get(
        "/prixspot",
        summary="Export CSV de tous les prix spot de l'électricité des 3 prochaines années",
        description="Exporte en format CSV tous les prix spot de l'électricité des 3 prochaines années disponibles dans la table de Microsoft Fabric.")
async def export_prix_spot():
    """Export de toutes les prix spot au format CSV"""
    print("📥 Requête reçue pour export des prix spot")

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
            get_all_prix_spot,
            connection
        )

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(cursor, columns),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=prix_spot.csv"
            }
        )

    except Exception as e:
        print(f"❌ ERREUR COMPLÈTE: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")