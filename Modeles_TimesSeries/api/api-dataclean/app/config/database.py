import pyodbc
import os
from typing import Optional
from dotenv import load_dotenv
import asyncio
from contextlib import asynccontextmanager

load_dotenv()
pyodbc.pooling = False


def _first_env(*keys: str) -> Optional[str]:
    for key in keys:
        value = os.getenv(key)
        if value is not None and str(value).strip() != "":
            return str(value).strip()
    return None


def _to_odbc_bool(value: Optional[str], default: str) -> str:
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return "yes"
    if normalized in {"0", "false", "no", "n", "off"}:
        return "no"
    return default


def _get_db_credentials():
    server = _first_env("DB_SERVER")
    database = _first_env("DB_DATABASE")
    username = _first_env("DB_USER", "DB_USERNAME")
    password = _first_env("DB_PASSWORD")
    return server, database, username, password


def _build_connection_string(authentication: Optional[str]) -> str:
    server, database, username, password = _get_db_credentials()

    if not all([server, database, username, password]):
        raise RuntimeError(
            "Variables DB_SERVER / DB_DATABASE / DB_USER (ou DB_USERNAME) / DB_PASSWORD manquantes"
        )

    driver = _first_env("DB_DRIVER") or "ODBC Driver 17 for SQL Server"
    encrypt = _to_odbc_bool(os.getenv("DB_ENCRYPT"), "yes")
    trust_cert = _to_odbc_bool(os.getenv("DB_TRUST_CERTIFICATE"), "yes")

    parts = [
        f"DRIVER={{{driver}}}",
        f"SERVER={server}",
        f"DATABASE={database}",
        f"UID={username}",
        f"PWD={password}",
        f"Encrypt={encrypt}",
        f"TrustServerCertificate={trust_cert}",
        "Connection Timeout=60",
    ]

    if authentication:
        parts.insert(3, f"Authentication={authentication}")

    return ";".join(parts) + ";"


def _connect_with_fallback(*, autocommit: bool) -> pyodbc.Connection:
    requested_auth = _first_env("DB_AUTHENTICATION")

    auth_candidates = []
    if requested_auth:
        auth_candidates.append(requested_auth)
    else:
        auth_candidates.append("ActiveDirectoryPassword")
    auth_candidates.append(None)

    last_exc: Optional[Exception] = None
    for auth in auth_candidates:
        connection_string = _build_connection_string(auth)
        try:
            return pyodbc.connect(connection_string, autocommit=autocommit)
        except pyodbc.Error as exc:
            last_exc = exc
            if auth:
                print(f"⚠️ Connexion ODBC avec Authentication={auth} échouée: {exc}")
            else:
                print(f"⚠️ Connexion ODBC sans Authentication explicite échouée: {exc}")

    raise last_exc if last_exc else RuntimeError("Échec de connexion ODBC")

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

            server, database, username, password = _get_db_credentials()

            if not all([server, database, username, password]):
                print("❌ Missing DB_SERVER, DB_DATABASE, DB_USER/DB_USERNAME, or DB_PASSWORD")
                return None

            print(f"🔄 Connecting to server: {server} / database: {database}")

            try:
                self._connection = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: _connect_with_fallback(autocommit=False)
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
    return _connect_with_fallback(autocommit=True)
