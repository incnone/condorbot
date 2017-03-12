import datetime
import logging
import mysql.connector

import config
from condormatch import CondorLeague
from condormatch import CondorMatch
from condormatch import CondorRacer
from condormatch import CondorRacerStats


class CondorDB(object):
    RACE_CANCELLED_FLAG = int(1) << 0
    RACE_FORCE_RECORDED_FLAG = int(1) << 1

    def __init__(self):
        self._db_conn = None
        self._connect_stack = 0

    def _connect(self):
        try:
            if self._connect_stack == 0:
                self._db_conn = mysql.connector.connect(
                    user=config.MYSQL_DB_USER,
                    password=config.MYSQL_DB_PASSWD,
                    host=config.MYSQL_DB_HOST,
                    database=config.MYSQL_DB_NAME,
                    buffered=True)
            self._connect_stack += 1
        except mysql.connector.errors.InterfaceError:
            self._connect_stack = 0
            raise

    def _close(self):
        self._connect_stack -= 1
        if self._connect_stack == 0:
            self._db_conn.close()

    @staticmethod
    def _log_warning(warning_str):
        logging.getLogger('discord').warning(warning_str)

    @staticmethod
    def _get_racer_from_row(row):
        racer = CondorRacer(row[0])
        racer.discord_name = row[1]
        racer.twitch_name = row[2]
        racer.timezone = row[3]
        racer.rtmp_name = row[4]
        racer.additional_info = row[5]
        return racer

    def _get_racer_id(self, condor_racer):
        if condor_racer is None:
            return None

        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (condor_racer.discord_id, condor_racer.twitch_name, condor_racer.rtmp_name)

            cursor.execute(
                "SELECT racer_id "
                "FROM user_data "
                "WHERE discord_id=%s OR twitch_name=%s OR rtmp_name=%s",
                params)

            for row in cursor:
                return row[0]

            # If no entry, make one
            params = (condor_racer.discord_id, condor_racer.discord_name, condor_racer.twitch_name,
                      condor_racer.timezone, condor_racer.rtmp_name,)
            cursor.execute(
                "INSERT INTO user_data (discord_id, discord_name, twitch_name, timezone, rtmp_name) "
                "VALUES (%s, %s, %s, %s, %s)",
                params)
            self._db_conn.commit()

            params = (condor_racer.discord_id, condor_racer.twitch_name, condor_racer.rtmp_name)
            cursor.execute(
                "SELECT racer_id "
                "FROM user_data "
                "WHERE discord_id=%s OR twitch_name=%s OR rtmp_name=%s",
                params)

            for row in cursor:
                return row[0]

        finally:
            self._close()

    def _get_racer_from_id(self, racer_id):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (racer_id,)
            cursor.execute(
                "SELECT discord_id,discord_name,twitch_name,timezone,rtmp_name,user_info "
                "FROM user_data "
                "WHERE racer_id=%s",
                params)
            for row in cursor:
                return CondorDB._get_racer_from_row(row)

            self._log_warning('Couldn\'t find racer id <{}>.'.format(racer_id))
        finally:
            self._close()

    def get_all_racers(self):
        try:
            self._connect()
            cursor = self._db_conn.cursor(buffered=True)
            racer_list = []
            cursor.execute(
                "SELECT discord_id,discord_name,twitch_name,timezone,rtmp_name,user_info "
                "FROM user_data")
            for row in cursor:
                racer_list.append(self._get_racer_from_row(row))
            return racer_list
        finally:
            self._close()

    def get_from_discord_id(self, discord_id):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (discord_id,)
            cursor.execute(
                "SELECT discord_id,discord_name,twitch_name,timezone,rtmp_name,user_info "
                "FROM user_data "
                "WHERE discord_id=%s",
                params)
            for row in cursor:
                return CondorDB._get_racer_from_row(row)

            self._log_warning('Couldn\'t find discord id <{}>.'.format(discord_id))
        finally:
            self._close()

    def get_from_discord_name(self, discord_name):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (discord_name.lower(),)
            cursor.execute(
                "SELECT discord_id,discord_name,twitch_name,timezone,rtmp_name,user_info "
                "FROM user_data "
                "WHERE LOWER(discord_name)=%s",
                params)
            for row in cursor:
                return CondorDB._get_racer_from_row(row)

            self._log_warning('Couldn\'t find discord name <{}>.'.format(discord_name))
        finally:
            self._close()

    def get_from_twitch_name(self, twitch_name):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (twitch_name.lower(),)
            cursor.execute(
                "SELECT discord_id,discord_name,twitch_name,timezone,rtmp_name,user_info "
                "FROM user_data "
                "WHERE LOWER(twitch_name)=%s",
                params)
            for row in cursor:
                return CondorDB._get_racer_from_row(row)

            self._log_warning('Couldn\'t find twitch name <{}>.'.format(twitch_name))
        finally:
            self._close()

    def get_from_rtmp_name(self, rtmp_name, register=False):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (rtmp_name.lower(),)
            cursor.execute(
                "SELECT discord_id,discord_name,twitch_name,timezone,rtmp_name,user_info "
                "FROM user_data "
                "WHERE LOWER(rtmp_name)=%s",
                params)
            for row in cursor:
                return CondorDB._get_racer_from_row(row)

            if register:
                params = (rtmp_name,)
                cursor.execute(
                    "INSERT INTO user_data (rtmp_name) "
                    "VALUES (%s)",
                    params)
                self._db_conn.commit()
                return self.get_from_rtmp_name(rtmp_name, False)
            else:
                self._log_warning('Couldn\'t find RTMP name <{}>.'.format(rtmp_name))

        finally:
            self._close()

    def is_registered_user(self, discord_id):
        try:
            self._connect()
            to_return = False
            cursor = self._db_conn.cursor()
            params = (discord_id,)
            cursor.execute(
                "SELECT discord_id "
                "FROM user_data "
                "WHERE discord_id=%s",
                params)
            for _ in cursor:
                to_return = True
            return to_return
        finally:
            self._close()

    def is_registered_channel(self, channel_id):
        try:
            self._connect()
            to_return = False
            cursor = self._db_conn.cursor()
            params = (channel_id,)
            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data "
                "WHERE channel_id=%s",
                params)
            for _ in cursor:
                to_return = True
            return to_return
        finally:
            self._close()

    def register_channel(self, match, channel_id):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,
                      match.flags, match.number_of_races, match.league.value,
                      match.flags, match.number_of_races, match.league.value)
            cursor.execute(
                "INSERT INTO match_data (racer_1_id, racer_2_id, week_number, flags, number_of_races, league) "
                "VALUES (%s,%s,%s,%s,%s,%s) "
                "ON DUPLICATE KEY UPDATE flags=%s, number_of_races=%s, league=%s",
                params)

            params = (channel_id, self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week)
            cursor.execute(
                "REPLACE INTO channel_data (channel_id, racer_1_id, racer_2_id, week_number) "
                "VALUES (%s,%s,%s,%s) ",
                params)

            self._db_conn.commit()
        finally:
            self._close()

    def delete_channel(self, channel_id):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (channel_id,)
            cursor.execute(
                "DELETE FROM channel_data "
                "WHERE channel_id=%s",
                params)

            self._db_conn.commit()
        finally:
            self._close()

    def transfer_racer_to(self, twitch_name, discord_member):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (discord_member.id, discord_member.name, twitch_name.lower(),)
            cursor.execute(
                "UPDATE user_data "
                "SET discord_id=%s, discord_name=%s "
                "WHERE LOWER(twitch_name)=%s",
                params)

            self._db_conn.commit()
        finally:
            self._close()

    def register(self, discord_member):
        try:
            self._connect()
            already_registered = False

            cursor = self._db_conn.cursor()

            params = (discord_member.id,)
            cursor.execute(
                "SELECT discord_id "
                "FROM user_data "
                "WHERE discord_id=%s",
                params)

            for _ in cursor:
                already_registered = True
                params = (discord_member.name, discord_member.id,)
                cursor.execute(
                    "UPDATE user_data "
                    "SET discord_name=%s "
                    "WHERE discord_id=%s",
                    params)

            if not already_registered:
                params = (discord_member.id, discord_member.name,)
                cursor.execute(
                    "INSERT INTO user_data (discord_id, discord_name) "
                    "VALUES (%s, %s)",
                    params)

            self._db_conn.commit()
            return not already_registered
        finally:
            self._close()

    def register_twitch(self, discord_member, twitch_name):
        try:
            self._connect()
            self.register(discord_member)
            duplicate_stream = False

            cursor = self._db_conn.cursor()
            params = (twitch_name,)
            cursor.execute(
                "SELECT twitch_name "
                "FROM user_data "
                "WHERE LOWER(twitch_name)=%s",
                params)
            for _ in cursor:
                duplicate_stream = True

            if not duplicate_stream:
                params = (twitch_name, discord_member.id,)
                cursor.execute(
                    "UPDATE user_data "
                    "SET twitch_name=%s "
                    "WHERE discord_id=%s",
                    params)
                cursor.execute(
                    "UPDATE user_data "
                    "SET rtmp_name=%s "
                    "WHERE discord_id=%s AND rtmp_name IS NULL",
                    params)
                self._db_conn.commit()

            return not duplicate_stream
        finally:
            self._close()

    def register_rtmp(self, discord_member, rtmp_name):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (rtmp_name,)
            cursor.execute(
                "SELECT rtmp_name "
                "FROM user_data "
                "WHERE rtmp_name=%s AND discord_id IS NULL",
                params)

            found = False
            for _ in cursor:
                found = True
            if not found:
                return self._register_rtmp_no_duplicate(discord_member, rtmp_name)

            racer = self.get_from_discord_id(discord_member.id)
            if racer is None:
                return False

            params = (discord_member.id,)
            cursor.execute(
                "DELETE FROM user_data "
                "WHERE discord_id=%s",
                params)

            params = (racer.discord_id, racer.discord_name, racer.twitch_name, racer.timezone, rtmp_name)
            cursor.execute(
                "UPDATE user_data "
                "SET discord_id=%s, discord_name=%s, twitch_name=%s, timezone=%s "
                "WHERE rtmp_name=%s",
                params)
            self._db_conn.commit()

            return True
        finally:
            self._close()

    def _register_rtmp_no_duplicate(self, discord_member, rtmp_name):
        try:
            self._connect()
            self.register(discord_member)
            duplicate_rtmp = False

            cursor = self._db_conn.cursor()
            params = (rtmp_name,)
            cursor.execute(
                "SELECT rtmp_name "
                "FROM user_data "
                "WHERE LOWER(rtmp_name)=%s",
                params)
            for _ in cursor:
                duplicate_rtmp = True

            if not duplicate_rtmp:
                params = (rtmp_name, discord_member.id,)
                cursor.execute(
                    "UPDATE user_data "
                    "SET rtmp_name=%s "
                    "WHERE discord_id=%s",
                    params)
                self._db_conn.commit()

            return not duplicate_rtmp
        finally:
            self._close()

    def register_timezone(self, discord_member, timezone):
        try:
            self._connect()
            self.register(discord_member)

            cursor = self._db_conn.cursor()
            params = (timezone, discord_member.id,)
            cursor.execute(
                "UPDATE user_data "
                "SET timezone=%s "
                "WHERE discord_id=%s",
                params)
            self._db_conn.commit()
        finally:
            self._close()

    def find_match_channel_id(self, match):
        try:
            self._connect()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)

            cursor = self._db_conn.cursor()
            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
                return int(row[0])

            self._log_warning('Couldn\'t find a match channel id.')

        finally:
            self._close()

    def find_channel_ids_with(self, racer):
        try:
            self._connect()
            channel_ids = []
            racer_id = self._get_racer_id(racer)

            cursor = self._db_conn.cursor()
            params = (racer_id, racer_id,)
            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data "
                "WHERE racer_1_id=%s OR racer_2_id=%s",
                params)

            for row in cursor:
                channel_ids.append(int(row[0]))

            return channel_ids
        finally:
            self._close()

    # Return an "open" channel for reuse
    def get_open_match_channel_info(self, week):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            cursor.execute(
                "SELECT channel_id,racer_1_id,racer_2_id,week_number "
                "FROM channel_data")
            for row in cursor:
                if int(row[3]) != week:
                    racer_1 = self._get_racer_from_id(row[1])
                    racer_2 = self._get_racer_from_id(row[2])
                    match = CondorMatch(racer_1, racer_2, row[3])
                    return int(row[0]), match

        finally:
            self._close()

    def get_all_race_channel_ids(self):
        try:
            self._connect()
            channel_ids = []
            cursor = self._db_conn.cursor()

            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data")
            for row in cursor:
                channel_ids.append(int(row[0]))

            return channel_ids
        finally:
            self._close()

    def get_race_channels_from_week(self, week):
        try:
            self._connect()
            channel_ids = []
            cursor = self._db_conn.cursor()

            params = (week,)
            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data "
                "WHERE week_number=%s",
                params)
            for row in cursor:
                channel_ids.append(int(row[0]))

            return channel_ids
        finally:
            self._close()

    # Gets the most recent match if no week given
    def get_match(self, racer_1, racer_2, week_number=None):
        try:
            self._connect()
            if week_number is None:
                cursor = self._db_conn.cursor()

                params = (self._get_racer_id(racer_1), self._get_racer_id(racer_2),
                          self._get_racer_id(racer_2), self._get_racer_id(racer_1),)
                cursor.execute(
                    "SELECT week_number "
                    "FROM match_data "
                    "WHERE (racer_1_id=%s AND racer_2_id=%s) OR (racer_1_id=%s AND racer_2_id=%s) "
                    "ORDER BY week_number DESC",
                    params)

                for row in cursor:
                    try:
                        week_number = int(row[0])
                        return self.get_match(racer_1, racer_2, week_number)
                    except ValueError:
                        self._log_warning('ValueError in parsing week number {}.'.format(row[0]))
            else:
                match_try = self._get_match(racer_1, racer_2, week_number)
                if match_try:
                    return match_try
                else:
                    return self._get_match(racer_2, racer_1, week_number)
        finally:
            self._close()

    def _get_match(self, racer_1, racer_2, week_number):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(racer_1), self._get_racer_id(racer_2), week_number)
            cursor.execute(
                "SELECT timestamp,flags,number_of_races,league FROM match_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
                match = CondorMatch(racer_1, racer_2, week_number)
                if row[0]:
                    match.set_from_timestamp(int(row[0]))
                match.flags = int(row[1])
                match.set_number_of_races(int(row[2]))
                match.set_league_from_value(int(row[3]))
                return match
        finally:
            self._close()

    def get_all_channel_ids_with_racer(self, racer):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(racer), self._get_racer_id(racer),)
            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data "
                "WHERE racer_1_id=%s OR racer_2_id=%s",
                params)

            ids = []
            for row in cursor:
                ids.append(int(row[0]))

            return ids
        finally:
            self._close()

    def get_channel_id_from_match(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
                return int(row[0])
        finally:
            self._close()

    def get_match_from_channel_id(self, channel_id):
        try:
            self._connect()
            cursor = self._db_conn.cursor(buffered=True)

            params = (channel_id,)
            cursor.execute(
                "SELECT racer_1_id,racer_2_id,week_number "
                "FROM channel_data "
                "WHERE channel_id=%s",
                params)
            for row in cursor:
                racer_1 = self._get_racer_from_id(row[0])
                racer_2 = self._get_racer_from_id(row[1])
                if not racer_1 or not racer_2:
                    self._log_warning('Error: couldn\'t find racers in CondorDB.get_match_from_channel_id.')
                    return None
                else:
                    return self.get_match(racer_1, racer_2, int(row[2]))
        finally:
            self._close()

    def get_all_matches(self):
        try:
            self._connect()
            match_list = []
            cursor = self._db_conn.cursor(buffered=True)

            cursor.execute(
                "SELECT channel_id "
                "FROM channel_data")
            for row in cursor:
                match = self.get_match_from_channel_id(int(row[0]))
                if match:
                    match_list.append(match)

            return match_list
        finally:
            self._close()
            
    def update_match(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (match.timestamp, match.flags, match.league.value,
                      self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "UPDATE match_data "
                "SET timestamp=%s,flags=%s,league=%s "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s", params)
            self._db_conn.commit()
        finally:
            self._close()

    def get_upcoming_matches(self, time):
        try:
            self._connect()
            matches = []
            cursor = self._db_conn.cursor(buffered=True)

            cursor.execute(
                "SELECT racer_1_id,racer_2_id,week_number,timestamp,flags,number_of_races,league "
                "FROM match_data "
                "ORDER BY timestamp ASC")
            for row in cursor:
                racer_1 = self._get_racer_from_id(row[0])
                racer_2 = self._get_racer_from_id(row[1])
                week = int(row[2])
                match = CondorMatch(racer_1, racer_2, week)
                match.flags = int(row[4])
                match.set_number_of_races(int(row[5]))
                match.set_league_from_value(int(row[6]))
                if match.confirmed and not match.played:
                    match.set_from_timestamp(int(row[3]))
                    if match.time - time > datetime.timedelta(minutes=-30):
                        matches.append(match)

            return matches
        finally:
            self._close()

    def get_cawmentator(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT cawmentator_id "
                "FROM match_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
                return self.get_from_discord_id(row[0])

        finally:
            self._close()

    def add_cawmentary(self, match, cawmentator_id):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            match_found = False
            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT cawmentator_id "
                "FROM match_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for _ in cursor:
                match_found = True
                break

            if match_found:
                params = (cawmentator_id,) + params
                cursor.execute(
                    "UPDATE match_data "
                    "SET cawmentator_id=%s "
                    "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s", params)
                self._db_conn.commit()
            else:
                self._log_warning('Error: tried to add cawmentary to an unscheduled match.')
        finally:
            self._close()

    def remove_cawmentary(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "UPDATE match_data "
                "SET cawmentator_id=0 "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            self._db_conn.commit()
        finally:
            self._close()

    def _modify_racer_stats(self, racer_id, racer_number, racer_stats):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (racer_id,)

            total_time_of_wins = 0
            if racer_number == 1:
                cursor.execute(
                    "SELECT flags, winner, racer_1_time "
                    "FROM race_data "
                    "WHERE racer_1_id=%s",
                    params)
            else:
                cursor.execute(
                    "SELECT flags, winner, racer_2_time "
                    "FROM race_data "
                    "WHERE racer_2_id=%s",
                    params)
            for row in cursor:
                if not int(row[0]) & CondorDB.RACE_CANCELLED_FLAG:
                    if int(row[1]) == racer_number:
                        racer_stats.wins += 1
                        total_time_of_wins += int(row[2])
                    elif int(row[1]) != 0:
                        racer_stats.losses += 1
            return total_time_of_wins
        finally:
            self._close()

    def get_racer_stats(self, racer):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            racer_id = self._get_racer_id(racer)
            racer_stats = CondorRacerStats(racer)

            # Get wins, losses, and mean time
            total_time_of_wins = 0
            total_time_of_wins += self._modify_racer_stats(racer_id, 1, racer_stats)
            total_time_of_wins += self._modify_racer_stats(racer_id, 2, racer_stats)
            if racer_stats.wins > 0:
                racer_stats.mean_win_time = total_time_of_wins / racer_stats.wins

            # Get league history
            params = (racer_id, racer_id)
            cursor.execute(
                "SELECT week_number, league "
                "FROM match_data "
                "WHERE racer_1_id=%s OR racer_2_id=%s "
                "ORDER BY week_number ASC",
                params)

            league_history_dict = {}
            for row in cursor:
                league_history_dict[int(row[0])] = CondorLeague.get_from_value(int(row[1]))

            for league in league_history_dict.values():
                racer_stats.league_history.append(league)

            return racer_stats
        finally:
            self._close()

    def set_user_info(self, racer, user_info):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            if user_info == '':
                params = (self._get_racer_id(racer),)
                cursor.execute(
                    "UPDATE user_data "
                    "SET user_info=NULL "
                    "WHERE racer_id=%s",
                    params)
            else:
                params = (user_info, self._get_racer_id(racer),)
                cursor.execute(
                    "UPDATE user_data "
                    "SET user_info=%s "
                    "WHERE racer_id=%s",
                    params)

            self._db_conn.commit()
        finally:
            self._close()

    def get_user_info(self, racer):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            params = (self._get_racer_id(racer),)
            cursor.execute(
                "SELECT user_info "
                "FROM user_data "
                "WHERE racer_id=%s",
                params)
            for row in cursor:
                return row[0]
        finally:
            self._close()

    def drop_racer_from_week(self, racer, week):
        try:
            self._connect()
            cursor = self._db_conn.cursor()
            racer_id = self._get_racer_id(racer)

            params = (racer_id, racer_id, week)
            cursor.execute(
                "DELETE "
                "FROM channel_data "
                "WHERE (racer_1_id=%s OR racer_2_id=%s) AND week_number=%s",
                params)
            cursor.execute(
                "DELETE "
                "FROM race_data "
                "WHERE (racer_1_id=%s OR racer_2_id=%s) AND week_number=%s",
                params)
            cursor.execute(
                "DELETE "
                "FROM match_data "
                "WHERE (racer_1_id=%s OR racer_2_id=%s) AND week_number=%s",
                params)

            self._db_conn.commit()
        finally:
            self._close()

    def number_of_wins_of_leader(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            num_wins_r1 = 0
            num_wins_r2 = 0
            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT flags,winner "
                "FROM race_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
                if not row[0] & CondorDB.RACE_CANCELLED_FLAG:
                    if int(row[1]) == 1:
                        num_wins_r1 += 1
                    elif int(row[1]) == 2:
                        num_wins_r2 += 1

            return max(num_wins_r1, num_wins_r2)
        finally:
            self._close()
    
    def number_of_finished_races(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            num_finished = 0
            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT flags "
                "FROM race_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
                if not row[0] & CondorDB.RACE_CANCELLED_FLAG:
                    num_finished += 1

            return num_finished
        finally:
            self._close()

    def number_of_wins(self, match, racer, count_draws=False):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            num_wins = 0
            racer_number = match.racer_number(racer)
            if racer_number == 1 or racer_number == 2:
                params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2),
                          match.week, racer_number)
                cursor.execute(
                    "SELECT flags "
                    "FROM race_data "
                    "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s AND winner=%s",
                    params)
                for row in cursor:
                    if not (int(row[0]) & CondorDB.RACE_CANCELLED_FLAG):
                        num_wins += 1

                if count_draws:
                    params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week, 0)
                    cursor.execute(
                        "SELECT flags "
                        "FROM race_data "
                        "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s AND winner=%s",
                        params)
                    for row in cursor:
                        if not (int(row[0]) & CondorDB.RACE_CANCELLED_FLAG):
                            num_wins += 0.5
            else:
                self._log_warning('Error: called CondorDB.number_of_wins on a racer not in a match '
                                  '(racer {0}, match {1} v {2}).'.format(
                                    racer.twitch_name, match.racer_1.twitch_name, match.racer_2.twitch_name))

            return num_wins
        finally:
            self._close()

    def largest_recorded_race_number(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT race_number "
                "FROM race_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s "
                "ORDER BY race_number DESC",
                params)
            for row in cursor:
                return int(row[0])

            return 0
        finally:
            self._close()

    def finished_race_number(self, match, finished_number):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT race_number,flags "
                "FROM race_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s "
                "ORDER BY race_number ASC",
                params)
            for row in cursor:
                if not (int(row[1]) & CondorDB.RACE_CANCELLED_FLAG):
                    finished_number -= 1
                    if finished_number == 0:
                        return int(row[0])

        finally:
            self._close()
                
    def record_match(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            num_cancelled = 0
            r1_wins = 0
            r2_wins = 0
            draws = 0
            noplays = config.RACE_NUMBER_OF_RACES
            flags = match.flags | CondorMatch.FLAG_PLAYED
            number_of_races = match.number_of_races

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT winner,contested,flags "
                "FROM race_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
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

            params = (r1_wins, r2_wins, draws, noplays, num_cancelled, flags, number_of_races,
                      self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "UPDATE match_data "
                "SET racer_1_wins=%s, racer_2_wins=%s, draws=%s, noplays=%s, cancels=%s, flags=%s, number_of_races=%s "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            self._db_conn.commit()
        finally:
            self._close()

    # Returns the list [racer_1_score, racer_2_score, draws]
    def get_score(self, match):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1), self._get_racer_id(match.racer_2), match.week,)
            cursor.execute(
                "SELECT racer_1_wins,racer_2_wins,draws "
                "FROM match_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s",
                params)
            for row in cursor:
                try:
                    r1wins = int(row[0])
                    r2wins = int(row[1])
                    draws = int(row[2])
                    return [r1wins, r2wins, draws]
                except ValueError:
                    self._log_warning('Error parsing an argument in CondorDB.get_score with '
                                      'racer_1_id = <{0}>, racer_2_id = <{1}>, week_number = <{2}>.'.format(
                                        self._get_racer_id(match.racer_1),
                                        self._get_racer_id(match.racer_2),
                                        match.week))

        finally:
            self._close()
                
    def record_race(self, match, racer_1_time, racer_2_time, winner, seed, timestamp, cancelled, force_recorded=False):
        try:
            self._connect()

            race_number = self.largest_recorded_race_number(match) + 1
            flags = 0
            if cancelled:
                flags |= CondorDB.RACE_CANCELLED_FLAG
            if force_recorded:
                flags |= CondorDB.RACE_FORCE_RECORDED_FLAG

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

            cursor = self._db_conn.cursor()
            cursor.execute(
                "REPLACE INTO race_data "
                "(racer_1_id, racer_2_id, week_number, race_number, timestamp, "
                "seed, racer_1_time, racer_2_time, winner, contested, flags) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", params)

            self._db_conn.commit()

        finally:
            self._close()

    def cancel_race(self, match, race_number):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            flags = self.get_race_flags(match, race_number) | CondorDB.RACE_CANCELLED_FLAG
            params = (0,
                      flags,
                      self._get_racer_id(match.racer_1),
                      self._get_racer_id(match.racer_2),
                      match.week,
                      race_number,)

            cursor.execute(
                "UPDATE race_data "
                "SET winner=%s, flags=%s "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s AND race_number=%s",
                params)
            self._db_conn.commit()
        finally:
            self._close()

    def change_winner(self, match, race_number, winner_number):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (winner_number,
                      self._get_racer_id(match.racer_1),
                      self._get_racer_id(match.racer_2),
                      match.week,
                      race_number,)
            cursor.execute(
                "UPDATE race_data "
                "SET winner=%s "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s AND race_number=%s", params)
            self._db_conn.commit()
        finally:
            self._close()

    def get_race_flags(self, match, race_number):
        try:
            self._connect()
            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1),
                      self._get_racer_id(match.racer_2),
                      match.week,
                      race_number,)

            cursor.execute(
                "SELECT flags "
                "FROM race_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s AND race_number=%s",
                params)
            for row in cursor:
                return int(row[0])

        finally:
            self._close()
    
    def set_contested(self, match, race_number, contesting_user):
        try:
            self._connect()
            R1_CONTESTED_FLAG = int(1) << 0
            R2_CONTESTED_FLAG = int(1) << 1
            OTHER_CONTESTED_FLAG = int(1) << 2

            cursor = self._db_conn.cursor()

            params = (self._get_racer_id(match.racer_1),
                      self._get_racer_id(match.racer_2),
                      match.week,
                      race_number,)
            found = False
            contested = 0
            cursor.execute(
                "SELECT contested "
                "FROM race_data "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s AND race_number=%s",
                params)
            for row in cursor:
                found = True
                contested = int(row[0])
            if not found:
                self._log_warning(
                    'Couldn\'t set a race contested, because I couldn\'t find it. Racers: {0} v {1}.'.format(
                        match.racer_1.twitch_name, match.racer_2.twitch_name))
                return

            if int(contesting_user.id) == int(match.racer_1.discord_id):
                contested |= R1_CONTESTED_FLAG
            elif int(contesting_user.id) == int(match.racer_2.discord_id):
                contested |= R2_CONTESTED_FLAG
            else:
                contested |= OTHER_CONTESTED_FLAG

            params = (contested,
                      self._get_racer_id(match.racer_1),
                      self._get_racer_id(match.racer_2),
                      match.week,
                      race_number,)
            cursor.execute(
                "UPDATE race_data "
                "SET contested=%s "
                "WHERE racer_1_id=%s AND racer_2_id=%s AND week_number=%s AND race_number=%s",
                params)
            self._db_conn.commit()
        finally:
            self._close()
