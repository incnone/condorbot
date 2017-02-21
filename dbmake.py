import config
import mysql.connector


config.init('data/bot_config.txt')


# Make the new master database, with tables set up as we want them
def make_new_database():
    db_conn = mysql.connector.connect(
        user=config.MYSQL_DB_USER,
        password=config.MYSQL_DB_PASSWD,
        host=config.MYSQL_DB_HOST,
        database=config.MYSQL_DB_NAME)

    cursor = db_conn.cursor()

    cursor.execute("""CREATE TABLE user_data
                    (racer_id integer,
                    discord_id bigint UNIQUE ON CONFLICT REPLACE,
                    discord_name text,
                    twitch_name text UNIQUE ON CONFLICT ABORT,
                    steam_id int,
                    timezone text,
                    PRIMARY KEY (racer_id))""")
    cursor.execute("""CREATE TABLE match_data
                    (racer_1_id int REFERENCES user_data (racer_id),
                    racer_2_id int REFERENCES user_data (racer_id),
                    week_number int,
                    timestamp bigint DEFAULT 0,
                    racer_1_wins int DEFAULT 0,
                    racer_2_wins int DEFAULT 0,
                    draws int DEFAULT 0,
                    noplays int DEFAULT 0,
                    cancels int DEFAULT 0,
                    flags int DEFAULT 0,
                    league int DEFAULT 0,
                    number_of_races int DEFAULT 0,
                    cawmentator_id int DEFAULT 0,
                    PRIMARY KEY (racer_1_id, racer_2_id, week_number) ON CONFLICT REPLACE)""")
    cursor.execute("""CREATE TABLE channel_data
                    (channel_id int,
                    racer_1_id int REFERENCES match_data (racer_1_id),
                    racer_2_id int REFERENCES match_data (racer_2_id),
                    week_number int REFERENCES match_data (week_number),
                    PRIMARY KEY (channel_id) ON CONFLICT REPLACE)
                    """)
    cursor.execute("""CREATE TABLE race_data
                    (racer_1_id int REFERENCES match_data (racer_1_id),
                    racer_2_id int REFERENCES match_data (racer_2_id),
                    week_number int REFERENCES match_data (week_number),
                    race_number int,
                    timestamp bigint,
                    seed int,
                    racer_1_time int,
                    racer_2_time int,
                    winner int DEFAULT -1,
                    contested int DEFAULT 0,
                    flags int DEFAULT 0,
                    PRIMARY KEY (racer_1_id, racer_2_id, week_number, race_number) ON CONFLICT ABORT)
                    """)

    db_conn.commit()
    db_conn.close()

# -------------------------

make_new_database()
