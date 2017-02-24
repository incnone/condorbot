import datetime
import pytz
import re

import condortimestr
import config


class CondorRacer(object):
    def __init__(self, discord_id):
        self.discord_id = int(discord_id)
        self.discord_name = None
        self.twitch_name = None
        self.rtmp_name = None
        self.timezone = None

    def __eq__(self, other):
        return self.unique_name.lower() == other.unique_name.lower()

    @staticmethod
    def _escaped(s):
        for char in ['*', '-', '_']:
            s = s.replace(char, '\\' + char)
        return s

    @property
    def infobox(self):
        if self.twitch_name == self.rtmp_name:
            return '```\n' \
                   '{0}\n' \
                   '  Twitch/RTMP: {1}\n' \
                   '     Timezone: {2}```'.format(
                    self.discord_name,
                    self.escaped_rtmp_name,
                    self.timezone)
        else:
            return '```\n' \
                   '{0}\n' \
                   '    Twitch: {1}\n' \
                   '      RTMP: {2}\n' \
                   '  Timezone: {3}\n```'.format(
                    self.discord_name,
                    self.escaped_twitch_name,
                    self.escaped_rtmp_name,
                    self.timezone)

    @property
    def gsheet_regex(self):
        return re.compile( r'(?i)^\s*' + re.escape(self.rtmp_name) + r'\s*$' )

    @property
    def escaped_twitch_name(self):
        return self._escaped(self.twitch_name)

    @property
    def escaped_rtmp_name(self):
        return self._escaped(self.rtmp_name)

    @property
    def unique_name(self):
        return self.rtmp_name

    def utc_to_local(self, utc_dt):
        if self.timezone not in pytz.all_timezones:
            return None
        local_tz = pytz.timezone(self.timezone)

        if utc_dt.tzinfo is not None and utc_dt.tzinfo.utcoffset(utc_dt) is not None:
            return local_tz.normalize(utc_dt.astimezone(local_tz))
        else:
            return local_tz.normalize(pytz.utc.localize(utc_dt))

    def local_to_utc(self, local_dt):
        if self.timezone not in pytz.all_timezones:
            return None
        local_tz = pytz.timezone(self.timezone)

        if local_dt.tzinfo is not None and local_dt.tzinfo.utcoffset(local_dt) is not None:
            return pytz.utc.normalize(local_dt.astimezone(pytz.utc))
        else:
            return pytz.utc.normalize(local_tz.localize(local_dt))


class CondorMatch(object):
    OFFSET_DATETIME = datetime.datetime(year=2016, month=1, day=1, tzinfo=pytz.utc)
    
    FLAG_SCHEDULED = int(1) << 0
    FLAG_SCHEDULED_BY_R1 = int(1) << 1
    FLAG_SCHEDULED_BY_R2 = int(1) << 2
    FLAG_CONFIRMED_BY_R1 = int(1) << 3
    FLAG_CONFIRMED_BY_R2 = int(1) << 4
    FLAG_PLAYED = int(1) << 5
    FLAG_CONTESTED = int(1) << 6
    FLAG_UNCONFIRMED_BY_R1 = int(1) << 7
    FLAG_UNCONFIRMED_BY_R2 = int(1) << 8
    FLAG_BEST_OF = int(1) << 9

    @staticmethod
    def notflag(flag):
        FULL_FLAG = (int(1) << 10) - 1
        return FULL_FLAG - flag

    def __init__(self, racer_1, racer_2, week):
        self._racer_1 = racer_1
        self._racer_2 = racer_2
        self._week = week
        self._time = None
        self._number_of_races = config.RACE_NUMBER_OF_RACES
        self.flags = 0

    @property
    def channel_name(self):
        name_1 = self.racer_1.unique_name.lower()
        name_2 = self.racer_2.unique_name.lower()
        racer_name_list = sorted([name_1, name_2])
        return '{0}-{1}'.format(racer_name_list[0], racer_name_list[1])

    @property
    def racers(self):
        return [self.racer_1, self.racer_2]

    @property
    def time_until_match(self):
        if self.time:
            return self.time - pytz.utc.localize(datetime.datetime.utcnow())
        else:
            return None

    @property
    def time_until_alert(self):
        if self.time:
            return self.time_until_match - datetime.timedelta(minutes=config.RACE_ALERT_AT_MINUTES)
        else:
            return None

    @property
    def time(self):
        return self._time

    @property
    def timestamp(self):
        if self.time:
            return (self.time - CondorMatch.OFFSET_DATETIME).total_seconds()
        else:
            return 0

    @property
    def is_best_of(self):
        return self.flags & CondorMatch.FLAG_BEST_OF

    @property
    def number_of_races(self):
        return self._number_of_races

    def set_from_timestamp(self, timestamp):
        td = datetime.timedelta(seconds=timestamp)
        self._time = CondorMatch.OFFSET_DATETIME + td

    def set_best_of(self, out_of_n):
        self.flags |= CondorMatch.FLAG_BEST_OF
        self._number_of_races = out_of_n

    def set_repeat(self, number_of_races):
        self.flags &= CondorMatch.notflag(CondorMatch.FLAG_BEST_OF)
        self._number_of_races = number_of_races

    def set_number_of_races(self, number_of_races):
        self._number_of_races = number_of_races

    def racer_number(self, racer):
        if racer == self.racer_1:
            return 1
        elif racer == self.racer_2:
            return 2
        else:
            return 0

    @property
    def racer_1(self):
        return self._racer_1

    @property
    def racer_2(self):
        return self._racer_2

    @property
    def week(self):
        return self._week

    @property
    def scheduled(self):
        return CondorMatch.FLAG_SCHEDULED & self.flags

    @property
    def confirmed(self):
        return (CondorMatch.FLAG_CONFIRMED_BY_R1 & self.flags) and (CondorMatch.FLAG_CONFIRMED_BY_R2 & self.flags)

    # returns the racer that scheduled this if possible
    @property
    def scheduled_by(self):
        if CondorMatch.FLAG_SCHEDULED_BY_R1 & self.flags:
            return self.racer_1
        elif CondorMatch.FLAG_SCHEDULED_BY_R2 & self.flags:
            return self.racer_2
        else:
            return None

    @property
    def played(self):
        return CondorMatch.FLAG_PLAYED & self.flags

    @property
    def topic_str(self):
        topic = '``` \n'
        if self.played:
            topic += 'The match is over.'           # TODO result information
        elif self.scheduled or self.confirmed:
            if not self.time:
                topic += 'Error: This match is marked as scheduled, but no time is stored.'
            else:
                utc_str = condortimestr.get_time_str(self.time)
                racer_1_str = condortimestr.get_time_str(self.racer_1.utc_to_local(self.time))
                racer_2_str = condortimestr.get_time_str(self.racer_2.utc_to_local(self.time))
                if self.confirmed:
                    topic += 'This match is scheduled for {0}.\n'.format(utc_str)
                elif self.scheduled:
                    topic += 'The following time has been suggested: {0}.\n'.format(utc_str)

                topic += '   {0}\'s local time: {1}\n'.format(self.racer_1.unique_name, racer_1_str)
                topic += '   {0}\'s local time: {1}\n'.format(self.racer_2.unique_name, racer_2_str)

                if self.scheduled and not self.confirmed:
                    conf_racers = ''
                    if not self.is_confirmed_by(self.racer_1):
                        conf_racers += self.racer_1.unique_name + ', '
                    if not self.is_confirmed_by(self.racer_2):
                        conf_racers += self.racer_2.unique_name + ', '
                        
                    if conf_racers:
                        topic += 'Waiting on confirmation from: {0}'.format(conf_racers[:-2])
                    else:
                        topic += 'Error: everyone has confirmed but the race is not marked as scheduled. ' \
                                 'Please contact CoNDOR Staff.'
                else:
                    topic += 'This schedule has been confirmed by both racers.'
        else:
            topic += 'This match has not been scheduled yet. After agreeing on a time,\n' \
                     'have one racer suggest this time by typing, e.g., ".suggest February\n' \
                     '12 5:30p" (use your own local time). Both racers should then confirm\n' \
                     'the suggested time with ".confirm".'

        topic += '```'
        return topic

    # returns True if the racer has already confirmed
    def is_confirmed_by(self, racer):
        if racer == self.racer_1:
            return self.flags & CondorMatch.FLAG_CONFIRMED_BY_R1
        elif racer == self.racer_2:
            return self.flags & CondorMatch.FLAG_CONFIRMED_BY_R2
        else:
            return False

    def schedule(self, time, racer):
        self.flags |= CondorMatch.FLAG_SCHEDULED
        if racer == self.racer_1:
            self.flags = (self.flags | CondorMatch.FLAG_SCHEDULED_BY_R1) \
                         & (CondorMatch.notflag(CondorMatch.FLAG_SCHEDULED_BY_R2))
        elif racer == self.racer_2:
            self.flags = (self.flags | CondorMatch.FLAG_SCHEDULED_BY_R2) \
                         & (CondorMatch.notflag(CondorMatch.FLAG_SCHEDULED_BY_R1))

        if time.tzinfo is not None and time.tzinfo.utcoffset(time) is not None:
            self._time = time.astimezone(pytz.utc)
        else:
            self._time = pytz.utc.localize(time)

        self.flags &= CondorMatch.notflag(CondorMatch.FLAG_CONFIRMED_BY_R1) \
            & CondorMatch.notflag(CondorMatch.FLAG_CONFIRMED_BY_R2)

    def confirm(self, racer):
        if racer == self.racer_1:
            self.flags = (self.flags | CondorMatch.FLAG_CONFIRMED_BY_R1) \
                         & CondorMatch.notflag(CondorMatch.FLAG_UNCONFIRMED_BY_R1)
        elif racer == self.racer_2:
            self.flags = (self.flags | CondorMatch.FLAG_CONFIRMED_BY_R2) \
                         & CondorMatch.notflag(CondorMatch.FLAG_UNCONFIRMED_BY_R2)

    def unconfirm(self, racer):
        if self.played:
            return
        
        if racer == self.racer_1:
            self.flags |= CondorMatch.FLAG_UNCONFIRMED_BY_R1
            if not self.confirmed:
                self.flags &= CondorMatch.notflag(CondorMatch.FLAG_CONFIRMED_BY_R1)
        elif racer == self.racer_2:
            self.flags |= CondorMatch.FLAG_UNCONFIRMED_BY_R2
            if not self.confirmed:
                self.flags &= CondorMatch.notflag(CondorMatch.FLAG_CONFIRMED_BY_R2)
                
        if self.flags & CondorMatch.FLAG_UNCONFIRMED_BY_R1 and self.flags & CondorMatch.FLAG_UNCONFIRMED_BY_R2:
            self.flags = 0
            self._time = None
