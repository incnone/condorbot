import asyncio
import datetime
import sqlite3

import config
from condormatch import CondorMatch
from condormatch import CondorRacer

class CondorDB(object):
    RACE_CANCELLED_FLAG = int(1) << 0
    
    def __init__(self, db_connection):
        self._db_conn = db_connection

    def _get_racer_from_row(row):
        racer = CondorRacer(row[2])
        racer.discord_id = row[0]
        racer.discord_name = row[1]
        racer.steam_id = row[3]
        racer.timezone = row[4]
        return racer

    def _get_racer_id(self, condor_racer):
        params = (condor_racer.twitch_name,)
        for row in self._db_conn.execute("SELECT racer_id FROM user_data WHERE twitch_name=?", params):
            return row[0]

        # if here, no entry
        self._db_conn.execute("INSERT INTO user_data (twitch_name) VALUES (?)", params)
        self._db_conn.commit()
        for row in self._db_conn.execute("SELECT racer_id FROM user_data WHERE twitch_name=?", params):
            return row[0]

    def _get_racer_from_id(self, racer_id):
        params = (racer_id,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE racer_id=?", params):
            return CondorDB._get_racer_from_row(row)
        print('Couldn\'t find racer id <{}>.'.format(discord_id))
        return None            

    def get_from_discord_id(self, discord_id):
        params = (discord_id,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE discord_id=?", params):
            return CondorDB._get_racer_from_row(row)
        print('Couldn\'t find discord id <{}>.'.format(discord_id))
        return None         

    def get_from_discord_name(self, discord_name):
        params = (discord_name,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE discord_name=?", params):
            return CondorDB._get_racer_from_row(row)
        print('Couldn\'t find discord name <{}>.'.format(discord_name))
        return None        

    def get_from_twitch_name(self, twitch_name, register=False):
        params = (twitch_name,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE twitch_name=?", params):
            return CondorDB._get_racer_from_row(row)

        if register:
            self._db_conn.execute("INSERT INTO user_data (twitch_name) VALUES (?)", params)
            self._db_conn.commit()
            for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE twitch_name=?", params):
                return CondorDB._get_racer_from_row(row)
            
        print('Couldn\'t find twitch name <{}>.'.format(twitch_name))
        return None

    def get_from_steam_id(self, steam_id):
        params = (steam_id,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE steam_id=?", params):
            return CondorDB._get_racer_from_row(row)
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
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        self._db_conn.execute("INSERT INTO match_data (racer_1_id, racer_2_id, week_number) VALUES (?,?,?)", params)
        params = (channel_id,) + params
        self._db_conn.execute("INSERT INTO channel_data (channel_id, racer_1_id, racer_2_id, week_number) VALUES (?,?,?,?)", params)
        self._db_conn.commit()

    def delete_channel(self, channel_id):
        params = (channel_id,)
        self._db_conn.execute("DELETE FROM channel_data WHERE channel_id=?", params)
        self._db_conn.commit()

    def register_racer(self, racer):
        params = (racer.twitch_name,)
        full_params = (racer.discord_id, racer.discord_name, racer.steam_id, racer.timezone, racer.twitch_name,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name FROM user_data WHERE twitch_name=?", params):
            if row[0] and not int(row[0]) == int(racer.discord_id):
                print('Error: User {0} tried to register twitch name {1}, but that name is already registered to {2}.'.format(racer.discord_name, racer.twitch_name, row[1]))
                return
            else:
                self._db_conn.execute("UPDATE user_data SET discord_id=?, discord_name=?, steam_id=?, timezone=? WHERE twitch_name=?", full_params)
                self._db_conn.commit()
                return
                
        self._db_conn.execute("INSERT INTO user_data (discord_id, discord_name, timezone, steam_id, twitch_name) VALUES (?,?,?,?,?)", full_params)
        self._db_conn.commit()

    def register_timezone(self, discord_id, timezone):
        params = (timezone, discord_id,)
        self._db_conn.execute("UPDATE user_data SET timezone=? WHERE discord_id=?", params)
        self._db_conn.commit()

    def find_match_channel_id(self, match):
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        for row in self._db_conn.execute("SELECT channel_id FROM channel_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            return int(row[0])
        return None

    def find_channel_ids_with(self, racer):
        channel_ids = []
        racer_id = self._get_racer_id(racer)
        params = (racer_id, racer_id,)
        for row in self._db_conn.execute("SELECT channel_id FROM channel_data WHERE racer_1_id=? OR racer_2_id=?", params):
            channel_ids.append(int(row[0]))
        return channel_ids

    ## return an "open" channel for reuse
    def get_open_match_channel_info(self, week):
        for row in self._db_conn.execute("SELECT channel_id,racer_1_id,racer_2_id,week_number FROM channel_data"):
            if int(row[3]) != week:
                racer_1 = self._get_racer_from_id(row[1])
                racer_2 = self._get_racer_from_id(row[2])
                match = CondorMatch(racer_1,racer_2,row[3])
                return (int(row[0]), match)
        return None

    def get_all_race_channel_ids(self):
        channel_ids = []
        for row in self._db_conn.execute("SELECT channel_id FROM channel_data"):
            channel_ids.append(int(row[0]))
        return channel_ids

    ## Gets the most recent match if no week given
    def get_match(self, racer_1, racer_2, week_number=None):
        if week_number == None:
            params = (self._get_racer_id(racer_1), self._get_racer_id(racer_2),)
            for row in self._db_conn.execute("SELECT week_number,timestamp,flags FROM match_data WHERE racer_1_id=? AND racer_2_id=? ORDER BY week_number DESC", params):
                match = CondorMatch(racer_1, racer_2, row[0])
                if row[1]:
                    match.set_from_timestamp(int(row[1]))
                match.flags = row[2]
                return match
        else:
            params = (self._get_racer_id(racer_1), self._get_racer_id(racer_2), week_number)
            for row in self._db_conn.execute("SELECT timestamp,flags FROM match_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
                match = CondorMatch(racer_1, racer_2, week_number)
                if row[0]:
                    match.set_from_timestamp(int(row[0]))
                match.flags = row[1]
                return match            
        return None

    def get_match_from_channel_id(self, channel_id):
        params = (channel_id,)
        for row in self._db_conn.execute("SELECT racer_1_id,racer_2_id,week_number FROM channel_data WHERE channel_id=?", params):
            racer_1 = self._get_racer_from_id(row[0])
            racer_2 = self._get_racer_from_id(row[1])
            return self.get_match(racer_1, racer_2, int(row[2]))
        return None
            
    def update_match(self, match):
        params = (match.timestamp, match.flags, self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        self._db_conn.execute("UPDATE match_data SET timestamp=?,flags=? WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params)       
        self._db_conn.commit()               

    def get_cawmentator(self, match):
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        for row in self._db_conn.execute("SELECT cawmentator_id FROM match_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            return self.get_from_discord_id(row[0])
        return None

    def add_cawmentary(self, match, cawmentator_id):
        match_found = False
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
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
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        self._db_conn.execute("UPDATE match_data SET cawmentator_id=0 WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params)
        self._db_conn.commit()

    def number_of_finished_races(self, match):
        num_finished = 0
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        for row in self._db_conn.execute("SELECT flags FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            if not row[0] & RACE_CANCELLED_FLAG:
                num_finished += 1
        return num_finished

    def record_match(self, match):
        num_cancelled = 0
        r1_wins = 0
        r2_wins = 0
        draws = 0
        noplays = config.RACE_NUMBER_OF_RACES
        flags = match.flags
                
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        for row in self._db_conn.execute("SELECT winner,contested,flags FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            if int(row[1]):
                flags = flags | CondorMatch.FLAG_CONTESTED
            if row[2] & CondorDB.RACE_CANCELLED_FLAG:
                num_cancelled += 1
            else:
                noplays -= 1
                if int(row[0]) == 1:
                    r1_wins += 1
                elif int(row[0]) == 2:
                    r2_wins += 1
                else:
                    draws += 1

        params = (r1_wins, r2_wins, draws, noplays, num_cancelled, flags, self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        self._db_conn.execute("UPDATE match_data SET racer_1_wins=?, racer_2_wins=?, draws=?, noplays=?, cancels=?, flags=? WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params)
        self._db_conn.commit()                
        
    def record_race(self, match, race_number, racer_1_time, racer_2_time, seed, timestamp, cancelled):
        flags = 0
        if cancelled:
            flags = flags | CondorDB.RACE_CANCELLED_FLAG

        winner = 0
        if racer_1_time < racer_2_time:
            winner = 1
        elif racer_2_time < racer_1_time:
            winner = 2
        elif not cancelled:
            winner = 3
            
        params = (self._get_racer_id(match.racer_1),
                  self._get_racer_id(match.racer_2),
                  match.week,
                  race_number,
                  timestamp,
                  seed,
                  racer_1_time,
                  racer_2_time,
                  winner,
                  0,
                  flags,)
        self._db_conn.execute("INSERT INTO race_data (racer_1_id, racer_2_id, week_number, race_number, timestamp, seed, racer_1_time, racer_2_time, winner, contested, flags) VALUES (?,?,?,?,?,?,?,?,?,?,?)", params)
        self._db_conn.commit()
    
    def set_contested(self, match, race_number, contesting_user):
        R1_CONTESTED_FLAG = int(1) << 0
        R2_CONTESTED_FLAG = int(1) << 1
        OTHER_CONTESTED_FLAG = int(1) << 2

        params = (self._get_racer_id(match.racer_1),
                  self._get_racer_id(match.racer_2),
                  match.week,
                  race_number,)
        found = False
        contested = 0
        for row in self._db_conn.execute("SELECT contested FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND race_number=?", params):
            found = True
            contested = int(row[0])
        if not found:
            print('Couldn\'t set a race contested, because I couldn\'t find it. Racers: {0} v {1}.'.format(match.racer_1.twitch_name, match.racer_2.twitch_name))
            return
        
        if int(contesting_user.discord_id) == int(match.racer_1.discord_id):
            contested = contested | R1_CONTESTED_FLAG
        elif int(contesting_user.discord_id) == int(match.racer_2.discord_id):
            contested = contested | R2_CONTESTED_FLAG
        else:
            contested = contested | OTHER_CONTESTED_FLAG
            
        params = (contested,
                  self._get_racer_id(match.racer_1),
                  self._get_racer_id(match.racer_2),
                  match.week,
                  race_number,)
        self._db_conn.execute("UPDATE race_data SET contested=? WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND race_number=?", params)
        self._db_conn.commit()
