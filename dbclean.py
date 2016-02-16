import sqlite3

DB_NAME = 'data/condors4.db'

db_conn = sqlite3.connect(DB_NAME)

try:
    params = (42, 38, 1, 4,)
    db_conn.execute("DELETE FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND race_number=?", params)
    db_conn.commit()
except Exception as e:
    print('Error deleting.')
    db_conn.rollback()
finally:
    db_conn.close()
