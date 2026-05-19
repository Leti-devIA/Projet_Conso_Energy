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
        rows = cursor.fetchall()
        return [dict(zip(columns, row)) for row in rows]
    finally:
        cursor.close()


def get_rows_by_prms(connection, prms: list[str]):
    cursor = connection.cursor()

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
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_all_previsions_meteo(connection):
    cursor = connection.cursor()

    query = """
        SELECT *
        FROM dbo.PREVISIONS_METEO
    """
    cursor.execute(query)

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_all_sites(connection):
    cursor = connection.cursor()

    query = """
        SELECT *
        FROM dbo.SITES
    """
    cursor.execute(query)

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_all_prix_spot(connection):
    cursor = connection.cursor()

    query = """
        SELECT *
        FROM dbo.PREVISIONS_PRIX
    """
    cursor.execute(query)

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
