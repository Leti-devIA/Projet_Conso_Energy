def get_rows_by_prm(connection, prm: str):
    cursor = connection.cursor()

    query = """
        SELECT *
        FROM dbo.ENEDIS_METEO_CLEAN
        WHERE prm = ?
    """
    cursor.execute(query, (prm,))

    columns = [col[0] for col in cursor.description]
    return cursor, columns


def get_all_previsions_meteo(connection):
    cursor = connection.cursor()

    query = """
        SELECT *
        FROM dbo.PREVISIONS_METEO
    """
    cursor.execute(query)

    columns = [col[0] for col in cursor.description]
    return cursor, columns
