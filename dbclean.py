import sqlite3

DB_NAME = 'data/condors4.db'

db_conn = sqlite3.connect(DB_NAME)

try:
    params = (3,)
    db_conn.execute("DELETE FROM match_data WHERE week_number=?", params)
    db_conn.commit()
except Exception as e:
    print('Error deleting.')
    db_conn.rollback()
finally:
    db_conn.close()
