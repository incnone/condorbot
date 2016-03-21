import sqlite3

db_conn = sqlite3.connect('data/condors4.db')

param_list = [(27, 10,), (1,35,), (46, 33,)]
for params in param_list:
    db_conn.execute("DELETE FROM channel_data WHERE racer_1_id=? AND racer_2_id=?", params)

db_conn.commit()
