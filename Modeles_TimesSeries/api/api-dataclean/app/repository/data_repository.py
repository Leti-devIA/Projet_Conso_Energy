import pyodbc


def _fetch_all_as_dicts(cursor, columns: list[str], batch_size: int = 5000) -> list[dict]:
    records: list[dict] = []
    while True:
        chunk = cursor.fetchmany(batch_size)
        if not chunk:
            break
        records.extend(dict(zip(columns, row)) for row in chunk)
    return records


def _safe_close_cursor(cursor) -> None:
    try:
        cursor.close()
    except pyodbc.ProgrammingError:
        pass


def get_rows_by_prm(connection, prm: str):
    query = """
        SELECT *
        FROM dbo.ENEDIS_METEO_CLEAN
        WHERE prm = ?
        ORDER BY datetime
    """
    cursor = connection.cursor()
    try:
        cursor.execute(query, (prm,))
        columns = [col[0] for col in cursor.description]
        return _fetch_all_as_dicts(cursor, columns)
    finally:
        _safe_close_cursor(cursor)


def get_rows_by_prms(connection, prms: list[str]):
    cursor = connection.cursor()
    try:
        if not prms:
            raise ValueError("La liste des PRM ne peut pas être vide")

        placeholders = ", ".join(["?"] * len(prms))
        query = f"""
            SELECT *
            FROM dbo.ENEDIS_METEO_CLEAN
            WHERE prm IN ({placeholders})
            ORDER BY prm, datetime
        """
        cursor.execute(query, tuple(prms))

        columns = [col[0] for col in cursor.description]
        return _fetch_all_as_dicts(cursor, columns)
    finally:
        _safe_close_cursor(cursor)


def get_all_previsions_meteo(connection):
    cursor = connection.cursor()
    try:
        query = """
            SELECT *
            FROM dbo.PREVISIONS_METEO
        """
        cursor.execute(query)

        columns = [col[0] for col in cursor.description]
        return _fetch_all_as_dicts(cursor, columns)
    finally:
        _safe_close_cursor(cursor)


def get_all_sites(connection):
    cursor = connection.cursor()
    try:
        query = """
            SELECT *
            FROM dbo.SITES
        """
        cursor.execute(query)

        columns = [col[0] for col in cursor.description]
        return _fetch_all_as_dicts(cursor, columns)
    finally:
        _safe_close_cursor(cursor)


def get_all_prix_spot(connection):
    cursor = connection.cursor()
    try:
        query = """
            SELECT *
            FROM dbo.PREVISIONS_PRIX
        """
        cursor.execute(query)

        columns = [col[0] for col in cursor.description]
        return _fetch_all_as_dicts(cursor, columns)
    finally:
        _safe_close_cursor(cursor)
