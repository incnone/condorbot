import sqlite3

db_conn = sqlite3.connect('data/condors4.db')

ANGELICA_REAL = 57
ANGELICA_FAKE = 59

params = (ANGELICA_REAL, ANGELICA_FAKE,)
db_conn.execute("UPDATE match_data SET racer_1_id=? WHERE racer_1_id=?", params)
db_conn.execute("UPDATE match_data SET racer_2_id=? WHERE racer_2_id=?", params)
db_conn.execute("UPDATE channel_data SET racer_1_id=? WHERE racer_1_id=?", params)
db_conn.execute("UPDATE channel_data SET racer_2_id=? WHERE racer_2_id=?", params)
db_conn.execute("UPDATE race_data SET racer_1_id=? WHERE racer_1_id=?", params)
db_conn.execute("UPDATE race_data SET racer_2_id=? WHERE racer_2_id=?", params)
params = (ANGELICA_FAKE,)
db_conn.execute("DELETE FROM user_data WHERE racer_id=?", params)

db_conn.commit()
