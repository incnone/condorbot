import codecs
#import config
import sqlite3

DB_OUT_NAME = 'data/condors4.db'

## Make the new master database, with tables set up as we want them
def make_new_database():
    db_conn = sqlite3.connect(DB_OUT_NAME)
    db_conn.execute("""CREATE TABLE user_data
                    (racer_id integer,
                    discord_id bigint UNIQUE ON CONFLICT REPLACE,
                    discord_name text,
                    twitch_name text UNIQUE ON CONFLICT ABORT,
                    steam_id int,
                    timezone text,
                    PRIMARY KEY (racer_id))""")
    db_conn.execute("""CREATE TABLE match_data
                    (racer_1_id int REFERENCES user_data (racer_id),
                    racer_2_id int REFERENCES user_data (racer_id),
                    week_number int,
                    timestamp bigint DEFAULT 0,
                    racer_1_wins int DEFAULT 0,
                    racer_2_wins int DEFAULT 0,
                    draws int DEFAULT 0,
                    noplays int DEFAULT 0,
                    flags int DEFAULT 0,
                    cawmentator_id int DEFAULT 0,
                    PRIMARY KEY (racer_1_id, racer_2_id, week_number) ON CONFLICT REPLACE)""")
    db_conn.execute("""CREATE TABLE channel_data
                    (channel_id int,
                    racer_1_id int REFERENCES match_data (racer_1_id),
                    racer_2_id int REFERENCES match_data (racer_2_id),
                    week_number int REFERENCES match_data (week_number),
                    PRIMARY KEY (channel_id) ON CONFLICT REPLACE)
                    """)
    db_conn.commit()
    db_conn.close()

##-------------------------

make_new_database()
