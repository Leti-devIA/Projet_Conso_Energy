from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse
from app.config.database import get_database_connection, create_new_connection
from app.services.csv_export import stream_rows_to_csv
from app.repository.data_repository import get_rows_by_prm, get_rows_by_prms, get_all_previsions_meteo, get_all_sites, get_all_prix_spot
import asyncio
import traceback
import pyodbc

router = APIRouter()


def _records_to_csv_parts(records: list[dict]):
    if not records:
        return [], []

    columns = list(records[0].keys())
    rows = [[record.get(column) for column in columns] for record in records]
    return rows, columns


async def _execute_with_new_connection(query_fn, *args, retries: int = 2):
    """
    Exécute une fonction SQL avec une NOUVELLE connexion à chaque appel.

    Pourquoi une nouvelle connexion :
    - Évite l'erreur pyodbc 'Connection is busy' quand plusieurs workers
      exécutent des requêtes en parallèle sur la même connexion.
    - Chaque appel est indépendant.

    Le retry gère les coupures réseau temporaires (code 08S01).
    """
    loop = asyncio.get_running_loop()
    last_exc = None

    for tentative in range(retries + 1):
        try:
            def _run():
                # Nouvelle connexion dédiée à cet appel
                conn = create_new_connection()
                try:
                    return query_fn(conn, *args)
                finally:
                    conn.close()  # Fermeture garantie même en cas d'erreur

            return await loop.run_in_executor(None, _run)

        except pyodbc.Error as exc:
            last_exc = exc
            await asyncio.sleep(0.5 * (tentative + 1))  # Attente progressive

    raise last_exc


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
        records = await loop.run_in_executor(
            None,
            get_rows_by_prm,
            connection,
            prm
        )

        rows, columns = _records_to_csv_parts(records)

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(rows, columns),
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
        # get_rows_by_prm retourne directement une list[dict]
        records = await _execute_with_new_connection(get_rows_by_prm, prm)

        print(f"✅ {len(records)} ligne(s) retournée(s) en JSON")

        # Date la plus récente récupérée pour ce PRM
        dates = [r.get("datetime") for r in records if r.get("datetime")]
        if dates:
            print(f"📅 Date la plus récente pour PRM {prm} : {max(dates)}")

        return {
            "prm": prm,
            "count": len(records),
            "rows": records,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"❌ ERREUR COMPLÈTE: {type(e).__name__}: {str(e)}")
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
        # get_rows_by_prms retourne directement une list[dict]
        records = await _execute_with_new_connection(get_rows_by_prms, normalized_prms)

        print(f"✅ {len(records)} ligne(s) batch retournée(s) en JSON")

        # Date la plus récente par PRM
        from collections import defaultdict
        max_dates: dict = defaultdict(lambda: None)
        for r in records:
            dt = r.get("datetime")
            prm_key = str(r.get("prm", ""))
            if dt and (max_dates[prm_key] is None or dt > max_dates[prm_key]):
                max_dates[prm_key] = dt
        for prm_key, max_dt in sorted(max_dates.items()):
            print(f"📅 Date la plus récente pour PRM {prm_key} : {max_dt}")

        return {
            "prms": normalized_prms,
            "count": len(records),
            "rows": records,
        }

    except Exception as e:
        if isinstance(e, HTTPException):
            raise e
        print(f"❌ ERREUR COMPLÈTE BATCH: {type(e).__name__}: {str(e)}")
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
        records = await loop.run_in_executor(
            None,
            get_all_previsions_meteo,
            connection
        )

        rows, columns = _records_to_csv_parts(records)

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(rows, columns),
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
        records = await loop.run_in_executor(
            None,
            get_all_sites,
            connection
        )

        rows, columns = _records_to_csv_parts(records)

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(rows, columns),
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
        records = await loop.run_in_executor(
            None,
            get_all_prix_spot,
            connection
        )

        rows, columns = _records_to_csv_parts(records)

        print(f"📊 Colonnes trouvées: {columns}")
        print(f"✅ Génération du CSV...")

        return StreamingResponse(
            stream_rows_to_csv(rows, columns),
            media_type="text/csv",
            headers={
                "Content-Disposition": "attachment; filename=prix_spot.csv"
            }
        )

    except Exception as e:
        print(f"❌ ERREUR COMPLÈTE: {type(e).__name__}: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Erreur lors de l'export: {str(e)}")