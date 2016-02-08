import asyncio
import datetime
import sqlite3

import config
from condormatch import CondorMatch
from condormatch import CondorRacer

class CondorDB(object):
    def __init__(self, db_connection):
        self._db_conn = db_connection

    def _get_racer_from_row(row):
        racer = CondorRacer(row[0],row[2])
        racer.discord_name = row[1]
        racer.steam_id = row[3]
        racer.timezone = row[4]
        return racer        

    def get_from_discord_id(self, discord_id):
        params = (discord_id,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE discord_id=?", params):
            return _get_racer_from_row(row)
        print('Couldn\'t find discord id <{}>.'.format(discord_id))
        return None         

    def get_from_discord_name(self, discord_name):
        params = (discord_name,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE discord_name=?", params):
            return _get_racer_from_row(row)
        print('Couldn\'t find discord name <{}>.'.format(discord_name))
        return None        

    def get_from_twitch_name(self, twitch_name):
        params = (twitch_name,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE twitch_name=?", params):
            return _get_racer_from_row(row)
        print('Couldn\'t find twitch name <{}>.'.format(twitch_name))
        return None

    def get_from_steam_id(self, steam_id):
        params = (steam_id,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE steam_id=?", params):
            return _get_racer_from_row(row)
        print('Couldn\'t find steam id <{}>.'.format(steam_id))
        return None        

    def register_channel(self, match, channel_id):
        params = (channel_id, match.racer_1.discord_id, match.racer_2.discord_id, match.week,)
        self._db_conn.execute("INSERT INTO channel_data (channel_id, racer_1_id, racer_2_id, week_number) VALUES (?,?,?,?)", params)

    def find_match_channel_id(self, match):
        params = (match.racer_1.discord_id, match.racer_2.discord_id, condor_match.week,)
        for row in self._db_conn.execute("SELECT channel_id FROM channel_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            return int(row[0])
        return None

    ## return an "open" channel for reuse
    def get_open_match_channel_info(self, week):
        for row in self._db_conn.execute("SELECT channel_id,racer_1_id,racer_2_id,week_number FROM channel_data"):
            if int(row[3]) != week:
                match = CondorMatch(row[1],row[2],row[3])
                return (int(row[0]), match)
        return None
