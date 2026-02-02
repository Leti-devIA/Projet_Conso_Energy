import pyodbc
import os
from typing import Optional
from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager

load_dotenv()


class DatabaseManager:
    def __init__(self):
        self._connection: Optional[pyodbc.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> Optional[pyodbc.Connection]:
        """Établit la connexion à la base de données avec ActiveDirectoryInteractive"""
        async with self._lock:
            if self._connection:
                try:
                    # Test si la connexion est encore active
                    self._connection.execute("SELECT 1")
                    return self._connection
                except:
                    self._connection = None  # Connexion expirée, on reconnecte

            server = os.getenv("DB_SERVER")
            database = os.getenv("DB_DATABASE")

            if not all([server, database]):
                print("❌ Missing DB_SERVER or DB_DATABASE environment variables")
                return None

            print(f"🔄 Connecting to server: {server} / database: {database}")

            try:
                connection_string = (
                    f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                    f"SERVER={server};DATABASE={database};"
                    f"Authentication=ActiveDirectoryInteractive;"
                    f"Encrypt=yes;TrustServerCertificate=yes;"
                    f"Connection Timeout=60;"
                )

                # pyodbc est bloquant, donc on utilise run_in_executor
                self._connection = await asyncio.get_event_loop().run_in_executor(
                    None, pyodbc.connect, connection_string
                )

                print("✅ Connected successfully (interactive, token reused)")
                return self._connection

            except Exception as e:
                print(f"❌ Connection failed: {e}")
                return None

    async def get_connection(self) -> Optional[pyodbc.Connection]:
        """Retourne une connexion active, réutilisée si déjà existante"""
        if not self._connection:
            await self.connect()
        return self._connection

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
