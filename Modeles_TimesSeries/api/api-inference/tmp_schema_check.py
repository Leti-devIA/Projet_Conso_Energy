from app.config.database import get_db_connection
conn = get_db_connection()
cur = conn.cursor()
cur.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='ia_predictions' ORDER BY ORDINAL_POSITION")
for row in cur.fetchall():
    print(row[0])
conn.close()
