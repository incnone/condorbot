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

    def is_registered_user(self, discord_id):
        params = (discord_id,)
        for row in self._db_conn.execute("SELECT discord_id FROM user_data WHERE discord_id=?", params):
            return True
        return False

    def is_registered_channel(self, channel_id):
        params = (channel_id,)
        for row in self._db_conn.execute("SELECT channel_id FROM channel_data WHERE channel_id=?", params):
            return True
        return False

    def register_channel(self, match, channel_id):
        params = (channel_id, match.racer_1.discord_id, match.racer_2.discord_id, match.week,)
        self._db_conn.execute("INSERT INTO channel_data (channel_id, racer_1_id, racer_2_id, week_number) VALUES (?,?,?,?)", params)
        self._db_conn.commit()

    def register_racer(self, racer):
        params = (racer.discord_id, racer.discord_name, racer.twitch_name, racer.steam_id, racer.timezone,)
        self._db_conn.execute("INSERT INTO user_data (discord_id, discord_name, twitch_name, steam_id, timezone) VALUES (?,?,?,?,?)", params)
        self._db_conn.commit()

    def register_timezone(self, discord_id, timezone):
        params = (timezone, discord_id,)
        self._db_conn.execute("UPDATE user_data SET timezone=? WHERE discord_id=?", params)
        self._db_conn.commit()

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

    ## Gets the most recent match
    def get_match(self, racer_1, racer_2):
        params = (racer_1.discord_id, racer_2.discord_id,)
        for row in self._db_conn.execute("SELECT week_number,timestamp FROM match_data WHERE racer_1_id=? AND racer_2_id=? ORDER BY week_number DESC", params):
            match = CondorMatch(racer_1, racer_2, row[0])
            if row[1]:
                match.time = datetime.datetime.fromtimestamp(row[1])
            return match
        return None

    def schedule_match(self, channel_id, utc_datetime):
        params = (channel_id,)
        for row in self._db_conn.execute("SELECT racer_1_id,racer_2_id,week_number FROM channel_data WHERE channel_id=?", params):
            r1id = row[0]
            r2id = row[1]
            week = row[2]
            params = (row[0], row[1], row[2],)
            for row in self._db_conn.execute("SELECT played FROM match_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
                if row[0]:
                    print('Error: trying to schedule a match that has already been played.')
                    return

            params = params + (utc_datetime.timestamp,)
            self._db_conn.execute("INSERT INTO match_data (racer_1_id,racer_2_id,week_number,timestamp) VALUES (?,?,?,?)", params)       
            self._db_conn.commit()

    def get_cawmentator(self, match):
        params = (match.racer_1.discord_id, match.racer_2.discord_id, match.week,)
        for row in self._db_conn.execute("SELECT cawmentator_id FROM match_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            return self.get_from_discord_id(row[0])
        return None

    def add_cawmentary(self, match, cawmentator_id):
        match_found = False
        params = (match.racer_1.discord_id, match.racer_2.discord_id, match.week,)
        for row in self._db_conn.execute("SELECT cawmentator_id FROM match_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            match_found = True
            break

        if match_found:           
            params = (cawmentator_id,) + params
            self._db_conn.execute("UPDATE match_data SET cawmentator_id=? WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params)
            self._db_conn.commit()
        else:
            print('Error: tried to add cawmentary to an unscheduled match.')

    def remove_cawmentary(self, match):
        params = (match.racer_1.discord_id, match.racer_2.discord_id, match.week,)
        self._db_conn.execute("UPDATE match_data SET cawmentator_id=0 WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params)
        self._db_conn.commit()
            
        
