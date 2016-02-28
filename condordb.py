import asyncio
import datetime
import sqlite3

import config
from condormatch import CondorMatch
from condormatch import CondorRacer

class CondorDB(object):
    RACE_CANCELLED_FLAG = int(1) << 0
    RACE_FORCE_RECORDED_FLAG = int(1) << 1
    
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
        params = (condor_racer.twitch_name.lower(),)
        for row in self._db_conn.execute("SELECT racer_id FROM user_data WHERE LOWER(twitch_name)=?", params):
            return row[0]

        # if here, no entry
        params = (condor_racer.twitch_name,)
        self._db_conn.execute("INSERT INTO user_data (twitch_name) VALUES (?)", params)
        self._db_conn.commit()
        for row in self._db_conn.execute("SELECT racer_id FROM user_data WHERE twitch_name=?", params):
            return row[0]

    def _get_racer_from_id(self, racer_id):
        params = (racer_id,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE racer_id=?", params):
            return CondorDB._get_racer_from_row(row)
        print('Couldn\'t find racer id <{}>.'.format(racer_id))
        return None            

    def get_from_discord_id(self, discord_id):
        params = (discord_id,)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE discord_id=?", params):
            return CondorDB._get_racer_from_row(row)
        print('Couldn\'t find discord id <{}>.'.format(discord_id))
        return None         

    def get_from_discord_name(self, discord_name):
        params = (discord_name.lower(),)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE LOWER(discord_name)=?", params):
            return CondorDB._get_racer_from_row(row)
        print('Couldn\'t find discord name <{}>.'.format(discord_name))
        return None        

    def get_from_twitch_name(self, twitch_name, register=False):
        params = (twitch_name.lower(),)
        for row in self._db_conn.execute("SELECT discord_id,discord_name,twitch_name,steam_id,timezone FROM user_data WHERE LOWER(twitch_name)=?", params):
            return CondorDB._get_racer_from_row(row)

        if register:
            params = (twitch_name,)
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

    def transfer_racer_to(self, twitch_name, discord_member):
        params = (discord_member.id, discord_member.name, twitch_name.lower(),)
        self._db_conn.execute("UPDATE user_data SET discord_id=?, discord_name=? WHERE LOWER(twitch_name)=?", params)
        self._db_conn.commit()

    def register_racer(self, racer):
        params = (racer.twitch_name.lower(),)
        for row in self._db_conn.execute("SELECT discord_id,discord_name FROM user_data WHERE LOWER(twitch_name)=?", params):
            if row[0] and not int(row[0]) == int(racer.discord_id):
                print('Error: User {0} tried to register twitch name {1}, but that name is already registered to {2}.'.format(racer.discord_name, racer.twitch_name, row[1]))
                return False
            else:
                params = (racer.discord_id, racer.discord_name, racer.twitch_name, racer.steam_id, racer.timezone, racer.twitch_name.lower(),)
                self._db_conn.execute("UPDATE user_data SET discord_id=?, discord_name=?, twitch_name=?, steam_id=?, timezone=? WHERE LOWER(twitch_name)=?", params)
                self._db_conn.commit()
                return True

        params = (racer.discord_id, racer.discord_name, racer.steam_id, racer.timezone, racer.twitch_name,)                
        self._db_conn.execute("INSERT INTO user_data (discord_id, discord_name, timezone, steam_id, twitch_name) VALUES (?,?,?,?,?)", params)
        self._db_conn.commit()
        return True

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

    def get_race_channels_from_week(self, week):
        channel_ids = []
        params = (week,)
        for row in self._db_conn.execute("SELECT channel_id FROM channel_data WHERE week_number=?", params):
            channel_ids.append(int(row[0]))
        return channel_ids        

    def delete_channel(self, channel_id):
        params = (channel_id,)
        self._db_conn.execute("DELETE FROM channel_data WHERE channel_id=?", params)
        self._db_conn.commit()

    ## Gets the most recent match if no week given
    def get_match(self, racer_1, racer_2, week_number=None):
        if week_number == None:
            params = (self._get_racer_id(racer_1), self._get_racer_id(racer_2), self._get_racer_id(racer_2), self._get_racer_id(racer_1),)
            for row in self._db_conn.execute("SELECT week_number FROM match_data WHERE (racer_1_id=? AND racer_2_id=?) OR (racer_1_id=? AND racer_2_id=?) ORDER BY week_number DESC", params):
                try:
                    week_number = int(row[0])
                except ValueError:
                    print('ValueError in parsing week number {}.'.format(row[0]))
                    return None

                return self.get_match(racer_1, racer_2, week_number)
        else:
            match_try = self._get_match(racer_1, racer_2, week_number)
            if match_try:
                return match_try
            else:
                return self._get_match(racer_2, racer_1, week_number)          
        return None

    def _get_match(self, racer_1, racer_2, week_number):
        params = (self._get_racer_id(racer_1), self._get_racer_id(racer_2), week_number)
        for row in self._db_conn.execute("SELECT timestamp,flags FROM match_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            match = CondorMatch(racer_1, racer_2, week_number)
            if row[0]:
                match.set_from_timestamp(int(row[0]))
            match.flags = int(row[1])
            return match
        return None

    def get_match_from_channel_id(self, channel_id):
        params = (channel_id,)
        for row in self._db_conn.execute("SELECT racer_1_id,racer_2_id,week_number FROM channel_data WHERE channel_id=?", params):
            racer_1 = self._get_racer_from_id(row[0])
            racer_2 = self._get_racer_from_id(row[1])
            if not racer_1 or not racer_2:
                print('Error: couldn\'t find racers in CondorDB.get_match_from_channel_id.')
                return None
            return self.get_match(racer_1, racer_2, int(row[2]))
        return None
            
    def update_match(self, match):
        params = (match.timestamp, match.flags, self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        self._db_conn.execute("UPDATE match_data SET timestamp=?,flags=? WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params)       
        self._db_conn.commit()

    def get_upcoming_matches(self, time):
        matches = []
        for row in self._db_conn.execute("SELECT racer_1_id,racer_2_id,week_number,timestamp,flags FROM match_data ORDER BY timestamp ASC"):
            racer_1 = self._get_racer_from_id(row[0])
            racer_2 = self._get_racer_from_id(row[1])
            week = int(row[2])
            match = CondorMatch(racer_1, racer_2, week)
            match.flags = int(row[4])
            if match.confirmed and not match.played:
                match.set_from_timestamp(int(row[3]))
                if match.time - time > datetime.timedelta(minutes=-30):
                    matches.append(match)
        return matches

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
            if not row[0] & CondorDB.RACE_CANCELLED_FLAG:
                num_finished += 1
        return num_finished

    def number_of_wins(self, match, racer, count_draws=False):
        num_wins = 0
        racer_id = self._get_racer_id(racer)
        racer_number = match.racer_number(racer)
        if racer_number == 1 or racer_number == 2:
            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week, racer_number) 
            for row in self._db_conn.execute("SELECT flags FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND winner=?", params):
                if not (int(row[0]) & CondorDB.RACE_CANCELLED_FLAG):
                    num_wins += 1

            if count_draws:
                params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week, 0) 
                for row in self._db_conn.execute("SELECT flags FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND winner=?", params):
                    if not (int(row[0]) & CondorDB.RACE_CANCELLED_FLAG):
                        num_wins += 0.5
        else:
            print('Error: called CondorDB.number_of_wins on a racer not in a match (racer {0}, match {1} v {2}).'.format(racer.twitch_name, match.racer_1.twitch_name, match.racer_2.twitch_name))

        return num_wins

    def largest_recorded_race_number(self, match):
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        for row in self._db_conn.execute("SELECT race_number FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=? ORDER BY race_number DESC", params):
            return int(row[0])
        return 0

    def finished_race_number(self, match, finished_number):
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        for row in self._db_conn.execute("SELECT race_number,flags FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=? ORDER BY race_number ASC", params):
            if not (int(row[1]) & CondorDB.RACE_CANCELLED_FLAG):
                finished_number -= 1
                if finished_number == 0:
                    return int(row[0])
        return None
                
    def record_match(self, match):
        num_cancelled = 0
        r1_wins = 0
        r2_wins = 0
        draws = 0
        noplays = config.RACE_NUMBER_OF_RACES
        flags = match.flags | CondorMatch.FLAG_PLAYED

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

    #returns the list [racer_1_score, racer_2_score, draws]
    def get_score(self, match):
        params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
        for row in self._db_conn.execute("SELECT racer_1_wins,racer_2_wins,draws FROM match_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=?", params):
            try:
                r1wins = int(row[0])
                r2wins = int(row[1])
                draws = int(row[2])
                return [r1wins, r2wins, draws]
            except ValueError:
                print('Error parsing an argument in CondorDB.get_score with racer_1_id = <{0}>, racer_2_id = <{1}>, week_number = <{2}>.'.format(self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week))
                return
                
    def record_race(self, match, racer_1_time, racer_2_time, winner, seed, timestamp, cancelled, force_recorded=False):
        race_number = self.largest_recorded_race_number(match) + 1
        flags = 0
        if cancelled:
            flags = flags | CondorDB.RACE_CANCELLED_FLAG
        if force_recorded:
            flags = flags | CondorDB.RACE_FORCE_RECORDED_FLAG

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
        
        try:
            self._db_conn.execute("INSERT INTO race_data (racer_1_id, racer_2_id, week_number, race_number, timestamp, seed, racer_1_time, racer_2_time, winner, contested, flags) VALUES (?,?,?,?,?,?,?,?,?,?,?)", params)
            self._db_conn.commit()
        except Exception as e:
            self._db_conn.rollback()
            raise

    def cancel_race(self, match, race_number):
        flags = self.get_race_flags(match, race_number) | CondorDB.RACE_CANCELLED_FLAG
        params = (0,
                  flags,
                  self._get_racer_id(match.racer_1),
                  self._get_racer_id(match.racer_2),
                  match.week,
                  race_number,)

        try:
            self._db_conn.execute("UPDATE race_data SET winner=?, flags=? WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND race_number=?", params)
            self._db_conn.commit()
        except Exception as e:
            self._db_conn.rollback()
            raise

    def change_winner(self, match, race_number, winner_number):
        params = (winner_number,
                  self._get_racer_id(match.racer_1),
                  self._get_racer_id(match.racer_2),
                  match.week,
                  race_number,)
        self._db_conn.execute("UPDATE race_data SET winner=? WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND race_number=?", params)
        self._db_conn.commit()

    def get_race_flags(self, match, race_number):
        params = (self._get_racer_id(match.racer_1),
                  self._get_racer_id(match.racer_2),
                  match.week,
                  race_number,)
        for row in self._db_conn.execute("SELECT flags FROM race_data WHERE racer_1_id=? AND racer_2_id=? AND week_number=? AND race_number=?", params):
            return int(row[0])
        return None
    
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
        
        if int(contesting_user.id) == int(match.racer_1.discord_id):
            contested = contested | R1_CONTESTED_FLAG
        elif int(contesting_user.id) == int(match.racer_2.discord_id):
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
