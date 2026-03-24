"""
Gestionnaire de connexion au Fabric Warehouse via pyodbc.

Utilise ActiveDirectoryInteractive pour l'authentification Azure AD.
"""

import pyodbc
import logging
from app.settings import DB_SERVER, DB_DATABASE

logger = logging.getLogger(__name__)


def get_db_connection() -> pyodbc.Connection:
    """
    Crée une connexion au Fabric Warehouse.

    Authentification: ActiveDirectoryInteractive (popup Azure AD au premier appel)

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
        # Chaîne de connexion pour Fabric Warehouse
        conn_str = (
            f"Driver={{ODBC Driver 17 for SQL Server}};"
            f"Server={DB_SERVER},1433;"
            f"Database={DB_DATABASE};"
            f"Authentication=ActiveDirectoryInteractive;"
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
            "  2. Vous êtes authentifiés : az login\n"
            "  3. ODBC Driver 17 for SQL Server est installé"
        )
        raise
