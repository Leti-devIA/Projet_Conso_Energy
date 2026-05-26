import pyodbc
import os
from typing import Optional
from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager

load_dotenv()
pyodbc.pooling = False

class DatabaseManager:
    def __init__(self):
        self._connection: Optional[pyodbc.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> Optional[pyodbc.Connection]:
        async with self._lock:
            if self._connection:
                try:
                    self._connection.execute("SELECT 1")
                    return self._connection
                except Exception:
                    try:
                        self._connection.close()
                    except Exception:
                        pass
                    self._connection = None

            server = os.getenv("DB_SERVER")
            database = os.getenv("DB_DATABASE")
            username = os.getenv("DB_USER")
            password = os.getenv("DB_PASSWORD")

            if not all([server, database, username, password]):
                print("❌ Missing DB_SERVER, DB_DATABASE, DB_USER, or DB_PASSWORD")
                return None

            print(f"🔄 Connecting to server: {server} / database: {database}")

            connection_string = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={server};DATABASE={database};"
                f"Authentication=ActiveDirectoryPassword;"
                f"UID={os.getenv('DB_USER')};PWD={os.getenv('DB_PASSWORD')};"
                f"Encrypt=yes;TrustServerCertificate=yes;"
                f"Connection Timeout=60;"
            )

            try:
                self._connection = await asyncio.get_event_loop().run_in_executor(
                    None, pyodbc.connect, connection_string
                )
                print("✅ Connected successfully")
                return self._connection
            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return None

    async def get_connection(self) -> Optional[pyodbc.Connection]:
        """Retourne une connexion active, réutilisée si déjà existante"""
        return await self.connect()

    async def close(self):
        """Ferme la connexion"""
        if self._connection:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, self._connection.close
                )
                print("🔒 Database connection closed")
            except:
                pass
            finally:
                self._connection = None

    @asynccontextmanager
    async def get_cursor(self):
        """Context manager pour obtenir un cursor"""
        connection = await self.get_connection()
        if not connection:
            yield None
            return

        cursor = connection.cursor()
        try:
            yield cursor
            connection.commit()
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            cursor.close()


# Instance globale du gestionnaire
db_manager = DatabaseManager()

# Fonctions de compatibilité
async def connect_database():
    return await db_manager.connect()

async def get_database_connection():
    return await db_manager.get_connection()

async def close_database_connection():
    await db_manager.close()


def create_new_connection():
    """
    Crée une connexion FRESH à chaque appel.

    Pourquoi :
    - La connexion singleton cause des conflits quand plusieurs requêtes arrivent
      en même temps (pyodbc : 'Connection is busy').
    - Ici, chaque requête SQL a sa propre connexion → plus de conflits.
    """
    server = os.getenv("DB_SERVER")
    database = os.getenv("DB_DATABASE")
    username = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")

    if not all([server, database, username, password]):
        raise RuntimeError("Variables DB_SERVER / DB_DATABASE / DB_USER / DB_PASSWORD manquantes")

    connection_string = (
        f"DRIVER={{ODBC Driver 17 for SQL Server}};"
        f"SERVER={server};DATABASE={database};"
        f"Authentication=ActiveDirectoryPassword;"
        f"UID={username};PWD={password};"
        f"Encrypt=yes;TrustServerCertificate=yes;"
        f"MARS_Connection=Yes;"
        f"Connection Timeout=60;"
    )

    return pyodbc.connect(connection_string, autocommit=True)
