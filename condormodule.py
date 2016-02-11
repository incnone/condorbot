import asyncio
import datetime
import discord

import calendar
from pytz import timezone
import pytz

import command
import config

from condordb import CondorDB
from condormatch import CondorMatch
from condormatch import CondorRacer
from condorsheet import CondorSheet

class Cawmentate(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'cawmentate')
        self.help_text = 'Register yourself for Cawmentary for a given match. Usage is `.cawmentate <racer1> <racer2>`, where `<racer1>` and `<racer2>` ' \
                        'are the twitch names of the racers in the match. (See the Google Doc for official names.) If there is already a Cawmentator for ' \
                        'the match, this command will fail -- consider talking to the person who has already registered about e.g. co-cawmentary. (You ' \
                        'can use `.uncawmentate <racer1> <racer2>` to de-register yourself for a match.)'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        if len(command.args) != 2:
            print('Error in cawmentate: wrong command arg length.')
        else:
            #find the match
            racer_1 = self._cm.condordb.get_from_twitch_name(command.args[0])
            racer_2 = self._cm.condordb.get_from_twitch_name(command.args[1])
            match = self._cm.condordb.get_match(racer_1, racer_2)
            if not match:
                print('Error: Couldn\'t find a match between {0} and {1}.'.format(command.args[0], command.args[1]))
                return

            #check for already having a cawmentator
            cawmentator = self._cm.condordb.get_cawmentator(match)
            if cawmentator:
                print('Error: Match already has cawmentator {0}.'.format(cawmentator.discord_name))
                return
            
            #register the cawmentary in the db and also on the gsheet
            cawmentator = self._cm.condordb.get_from_discord_id(command.author.id)
            if not cawmentator:
                print('Error: User {0} unregistered. (Use `.stream`.)'.format(command.author.name))
                return
            
            self._cm.condordb.add_cawmentary(match, cawmentator.discord_id)
            self._cm.condorsheet.add_cawmentary(match, cawmentator.twitch_name)

class MakeWeek(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'makeweek')
        self.help_text = 'Make the race rooms for a week. Usage is `.makeweek <week_number>`, e.g., `.makeweek 1`. This will look on the GSheet ' \
                        'for the worksheet titled "Week 1", look in the "Racer 1" column between the heading "Racer 1" and the special character ' \
                        '"--------" (eight hyphens), and make matchup channels for each matchup it finds (reading the Racer 1 column as the twitch ' \
                        'name of the first racer, and the column to its right as the twitch name of the second racer). This will make private channels ' \
                        'visible to only the racers in that race; note that racers will have to register (with `.stream <twitchname>`) in order to ' \
                        'be able to see the channel for their race.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        if len(command.args) != 1:
            print('Error in makeweek: wrong command arg length.')
        else:
            try:
                week = int(command.args[0])
                matches = self._cm.condorsheet.get_matches(week)
                if matches:
                    for match in matches:
                        self._cm.make_match_channel(match)
                    
            except ValueError:
                print('Error in makeweek: couldn\'t parse arg <{}> as a week number.'.format(command.args[0]))

class Schedule(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'schedule')
        self.help_text = 'Schedule a match. Usage is `.schedule <localtime>`, where `<localtime>` is a date and time in your registered timezone. ' \
                        '(Use `.timezone` to register a timezone with your account.) `<localtime>` takes the form `<month> <date> <time>`, where `<month>` ' \
                        'is the English month name (February, March, April), `<date>` is the date number, and `<time>` is a time `[h]h:mm`. Times can be given ' \
                        'an am/pm rider or this can be left off, e.g., `7:30a` and `7:30` are interpreted as the same time, as are `15:45` and `3:45p`. Thus a ' \
                        'call to this command might look like: `.schedule February 18 17:30`, which schedules the match for 5:30 pm in the command caller\'s ' \
                        'local time. (The bot will output the time this corresponds to for the second racer.)'

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    @asyncio.coroutine
    def _do_execute(self, command):
        if len(command.args) != 3:
            print('Error in schedule: wrong command arg length.')
        else:
            try:
                month_name = args[0].capitalize()
                if not month_name in calendar.month_names:
                    print('Error parsing month name.')
                    return
                month = calendar.month_names.index(month_name)
                
                day = int(args[1])
                time_args = args[2].split(':')
                if len(time_args) != 2:
                    print('Error parsing time in schedule command.')
                    return

                add_for_pm = time_args[1].endswith('p') or time_args[1].endswith('pm')
                time_min = int(time_args[1].rstrip('apm'))
                time_hr = int(time_args[0]) + (int(12) if add_for_pm else 0)

                racer = self._cm.condordb.get_from_discord_id(command.author.id)
                if not racer:
                    print ('Error: tried to schedule but not yet registered.')
                    return

                timezone_name = racer.timezone
                if not timezone_name in pytz.all_timezones:
                    timezone_name = 'UTC'
                racer_tz = pytz.timezone(timezone_name)
                
                racer_dt = racer_tz.localize(datetime.datetime(config.THIS_YEAR, month, day, time_hr, time_min, 0))
                utc_dt = pytz.utc.normalize(racer_dt.astimezone(racer_tz))

                fmt = '%Y-%m-%d %H:%M:%S %Z'
                print('Racer time: {}'.format(racer_dt.strftime(fmt)))
                print('UTC time: {}'.format(utc_dt.strftime(fmt)))
                # TODO output both racer's times for confirmation

                self._cm.condordb.schedule_match(command.channel.id, utc_dt)

            except ValueError:
                print('Error parsing schedule args: couldn\'t interpret something as an int.')            

class Stream(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'stream')
        self.help_text = 'Register a twitch stream. Usage is `.stream <twitchname>`, e.g., `.stream incnone`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        if len(command.args) != 1:
            yield from self._cm.necrobot.client.send_message(command.channel, '{0}: I was unable to parse your stream name because you gave too many arguments. ' \
                                                             'Use `.stream <twitchname>`.'.format(command.author.mention))
        else:
            twitch_name = command.args[0]
            if '/' in twitch_name:
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Error: your stream name cannot contain the character /. (Maybe you accidentally ' \
                                                                 'included the "twitch.tv/" part of your stream name?)'.format(command.author.mention))
            else:
                racer = CondorRacer(command.author.id, twitch_name)
                racer.discord_name = command.author.name
                self._cm.condordb.register_racer(racer)
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Registered your stream as <twitch.tv/{1}>'.format(command.author.mention, twitch_name))
                #TODO check room permissions (if a raceroom has been created, allow this user to see it)

class Timezone(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'timezone')
        self.timezone_loc = 'https://github.com/incnone/condorbot/blob/master/data/tz_list.txt'
        self.help_text = 'Register a time zone with your account. Usage is `.timezone <zonename>`. See {0} for a ' \
                        'list of recognized time zones; these strings should be input exactly as-is, e.g., `.timezone US\Eastern`.'.format(self.timezone_loc)
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._cm.condordb.is_registered_user(command.author.id):
            yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Please register a twitch stream first (use `.stream <twitchname>`).'.format(command.author.mention))
        elif len(command.args) != 1:
            yield from self._cm.necrobot.client.send_message(command.channel, '{0}: I was unable to parse your timezone because you gave too many arguments. See {1} for a list of timezones.'.format(command.author.mention, self.timezone_loc))
        else:
            tz_name = command.args[0]
            if tz_name in pytz.all_timezones:
                self._cm.condordb.register_timezone(command.author.id, tz_name)
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Timezone set as {1}.'.format(command.author.mention, tz_name))
            else:
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: I was unable to parse your timezone. See {1} for a list of timezones.'.format(command.author.mention, self.timezone_loc))

class Uncawmentate(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'uncawmentate')
        self.help_text = 'Unregister for match cawmentary. Usage is `.uncawmentate <racer1> <racer2>`, where `<racer1>` and `<racer2>` ' \
                        'are the twitch names of the racers in the match you want to de-register for. (See the Google Doc for official names.)'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        if len(command.args) != 2:
            print('Error in uncawmentate: wrong command arg length.')
        else:
            #find the match
            racer_1 = self._cm.condordb.get_from_twitch_name(command.args[0])
            racer_2 = self._cm.condordb.get_from_twitch_name(command.args[1])
            match = self._cm.condordb.get_match(racer_1, racer_2)
            if not match:
                print('Error: Couldn\'t find a match between {0} and {1}.'.format(command.args[0], command.args[1]))
                return

            #check for already having a cawmentator
            cawmentator = self._cm.condordb.get_cawmentator(match)
            if cawmentator.discord_id != command.author.id:
                print('Error: Match has cawmentator {0}.'.format(cawmentator.discord_name))
                return
            
            #register the cawmentary in the db and also on the gsheet           
            self._cm.condordb.remove_cawmentary(match)
            self._cm.condorsheet.remove_cawmentary(match)

class CondorModule(command.Module):
    def __init__(self, necrobot, db_connection):
        command.Module.__init__(self, necrobot)
        self.condordb = CondorDB(db_connection)
        self.condorsheet = CondorSheet(self.condordb)

        self.command_types = [command.DefaultHelp(self),
                              Stream(self),
                              Timezone(self)]

    @property
    def client(self):
        return self.necrobot.client

    @property
    def admin_channel(self):
        return self.necrobot.find_channel(config.ADMIN_CHANNEL_NAME)

    def get_match_channel_name(self, match):
        racer_1_name = self.condordb.get_name(match.racer_1_id)
        racer_2_name = self.condordb.get_name(match.racer_2_id)
        return '{0}-{1}'.format(racer_1_name, racer_2_name)

    @asyncio.coroutine
    def make_match_channel(self, match):
        already_made_id = self.condordb.find_match_channel_id(condor_match)
        if already_made_id:
            for ch in self.necrobot.server.channels:
                if int(ch.id) == int(already_made_id):
                    return ch
        
        open_match_info = self.condordb.get_open_match_channel_info(week)
        channel = None

        if open_match_info:
            for ch in self.necrobot.server.channels:
                if int(ch.id) == int(open_match_info[0]):
                    channel = ch
            if not channel:
                print('Error: couldn\'t find a registered channel.')
                open_match_info = None
                
        # if there was no open channel, make one
        if not open_match_info:
            channel = yield from self.client.create_channel(self.necrobot.server, self.get_match_channel_name(match))
            channel_id = channel.id
        # otherwise, change the name of the channel we got, and remove permissions from it
        else:
            match = open_match_info[1]
            yield from self.client.edit_channel(channel, name=self.get_match_channel_name(match))
            read_permit = discord.Permissions.none()
            read_permit.read_messages = True
            racer_1 = self.necrobot.find_member_with_id(match.racer_1_id)
            racer_2 = self.necrobot.find_member_with_id(match.racer_2_id)
            yield from self.client.edit_channel_permissions(channel, racer_1, deny=read_permit)
            yield from self.client.edit_channel_permissions(channel, racer_2, deny=read_permit)

        self.condordb.register_channel(match, channel.id)

        read_permit = discord.Permissions.none()
        read_permit.read_messages = True
        yield from self.client.edit_channel_permissions(channel, self.necrobot.server.default_role, deny=read_permit)
        racer_1 = self.necrobot.find_member_with_id(match.racer_1_id)
        racer_2 = self.necrobot.find_member_with_id(match.racer_2_id)
        yield from self.client.edit_channel_permissions(channel, racer_1, allow=read_permit)
        yield from self.client.edit_channel_permissions(channel, racer_2, allow=read_permit)
        for role in self.necrobot.admin_roles():
            yield from self.client.edit_channel_permissions(channel, role, allow=read_permit)
        
