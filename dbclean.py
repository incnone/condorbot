import sqlite3

DB_NAME = 'data/condors4.db'

db_conn = sqlite3.connect(DB_NAME)

try:
    params = ('Tictacfoe',)
    db_conn.execute("DELETE FROM user_data WHERE twitch_name=?", params)
    db_conn.commit()
except Exception as e:
    print('Error deleting.')
    db_conn.rollback()
finally:
    db_conn.close()
