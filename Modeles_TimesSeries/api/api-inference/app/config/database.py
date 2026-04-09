"""
Gestionnaire de connexion au Fabric Warehouse via pyodbc.

Utilise ActiveDirectoryPassword (Docker/serveur) ou ActiveDirectoryInteractive (local).
"""

import os
import pyodbc
import logging
from app.main import DB_SERVER, DB_DATABASE

logger = logging.getLogger(__name__)


def _select_odbc_driver() -> str:
    """Sélectionne un driver SQL Server disponible sur l'environnement courant."""
    forced_driver = os.getenv("DB_ODBC_DRIVER")
    if forced_driver:
        return forced_driver

    available = pyodbc.drivers()
    preferred = [
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
    ]

    for candidate in preferred:
        if candidate in available:
            return candidate

    # Fallback explicite : garde 18 en défaut si la liste est vide
    return "ODBC Driver 18 for SQL Server"


def get_db_connection() -> pyodbc.Connection:
    """
    Crée une connexion au Fabric Warehouse.

    Authentification:
    - ActiveDirectoryPassword si DB_USER/DB_USERNAME + DB_PASSWORD sont présents
    - sinon ActiveDirectoryInteractive

    Returns:
        pyodbc.Connection

    Raises:
        Exception si les variables d'env DB_SERVER ou DB_DATABASE manquent
        Exception si la connexion échoue
    """

    if not DB_SERVER or not DB_DATABASE:
        raise ValueError(
            "DB_SERVER et DB_DATABASE doivent être définis dans .env "
            "(cf. FABRIC_WORKSPACE_ID, FABRIC_LAKEHOUSE_ID)"
        )

    logger.info(f"🔄 Connexion au Warehouse Fabric : {DB_SERVER} / {DB_DATABASE}")

    try:
        driver = _select_odbc_driver()
        db_user = os.getenv("DB_USER") or os.getenv("DB_USERNAME")
        db_password = os.getenv("DB_PASSWORD")

        logger.info(f"🧩 Driver ODBC sélectionné : {driver}")

        auth_part = "Authentication=ActiveDirectoryInteractive;"
        if db_user and db_password:
            auth_part = (
                "Authentication=ActiveDirectoryPassword;"
                f"UID={db_user};"
                f"PWD={db_password};"
            )

        # Chaîne de connexion pour Fabric Warehouse
        conn_str = (
            f"Driver={{{driver}}};"
            f"Server={DB_SERVER},1433;"
            f"Database={DB_DATABASE};"
            f"{auth_part}"
            f"Encrypt=yes;"
            f"TrustServerCertificate=yes;"
            f"Connection Timeout=60;"
        )

        conn = pyodbc.connect(conn_str)
        logger.info("✅ Connecté au Warehouse Fabric")
        return conn

    except Exception as e:
        logger.error(f"❌ Erreur connexion Fabric : {str(e)}")
        logger.warning(
            "💡 Assurez-vous :\n"
            "  1. DB_SERVER et DB_DATABASE sont définis dans .env\n"
            "  2. En Docker: DB_USER/DB_USERNAME + DB_PASSWORD sont définis (sinon mode interactif)\n"
            "  3. Driver ODBC SQL Server installé (18 ou 17)"
        )
        raise
