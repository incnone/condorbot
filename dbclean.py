import sqlite3

DB_NAME = 'data/condors4.db'

db_conn = sqlite3.connect(DB_NAME)

try:
    db_conn.execute("DELETE FROM user_data WHERE twitch_name=Tictacfoe"):
    db_new.commit()
except Exception as e:
    print('Error deleting.')
    db_new.rollback()
finally:
    db_conn.close()
