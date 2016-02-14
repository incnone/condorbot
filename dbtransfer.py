import sqlite3

DB_IN_NAME = 'data/oldcondors4.db'
DB_OUT_NAME = 'data/condors4.db'

db_old = sqlite3.connect(DB_IN_NAME)
db_old.row_factory = sqlite3.Row
db_new = sqlite3.connect(DB_OUT_NAME)

try:
    for row in db_old.execute("SELECT * FROM user_data"):
        params = (row['racer_id'], row['discord_id'], row['discord_name'], row['twitch_name'], row['steam_id'], row['timezone'])
        db_new.execute("INSERT INTO user_data (racer_id, discord_id, discord_name, twitch_name, steam_id, timezone) VALUES (?,?,?,?,?,?)", params)

    db_new.commit()
except Exception as e:
    print('Error transfering databases.')
    db_new.rollback()
finally:
    db_old.close()
    db_new.close
