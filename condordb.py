import asyncio
import datetime
import sqlite3

import config

class CondorDB(object):
    def __init__(self, db_connection):
        self._db_conn = db_connection

    def get_discord_id(self, username):
        params = (username,)
        for row in self._db_conn.execute("SELECT discord_id FROM user_data WHERE _name=?", params):
            return row[0]
        print('Couldn\'t find racer <{}>.'.format(username))
        return None

    def get_name(self, discord_id):
        params = (discord_id,)
        for row in self._db_conn.execute("SELECT gsheets_name FROM user_data WHERE discord_id=?", params):
            return row[0]
        print('Couldn\'t find discord id <{}>.'.format(discord_id))
        return None

    def register_channel(self, match, channel_id):
        

    ## TODO: return an "open" channel for reuse
    def get_open_match_channel_id(self):
        return 0
