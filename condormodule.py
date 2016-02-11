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
                        yield from self._cm.make_match_channel(match)
                    
            except ValueError:
                print('Error in makeweek: couldn\'t parse arg <{}> as a week number.'.format(command.args[0]))

class Schedule(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'schedule')
        self.help_text = 'Schedule a match. Example: `.schedule February 18 17:30` (your local time; choose a local time with `.timezone`). \n \n' \
                        'General usage is `.schedule <localtime>`, where `<localtime>` is a date and time in your registered timezone. ' \
                        '(Use `.timezone` to register a timezone with your account.) `<localtime>` takes the form `<month> <date> <time>`, where `<month>` ' \
                        'is the English month name (February, March, April), `<date>` is the date number, and `<time>` is a time `[h]h:mm`. Times can be given ' \
                        'an am/pm rider or this can be left off, e.g., `7:30a` and `7:30` are interpreted as the same time, as are `15:45` and `3:45p`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    @asyncio.coroutine
    def _do_execute(self, command):
        if len(command.args) != 3:
            print('Error in schedule: wrong command arg length.')
        else:
            try:
                month_name = command.args[0].capitalize()
                if not month_name in calendar.month_name:
                    print('Error parsing month name.')
                    return
                month = list(calendar.month_name).index(month_name)
                
                day = int(command.args[1])
                time_args = command.args[2].split(':')
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
                
                racer_dt = racer_tz.localize(datetime.datetime(config.SEASON_YEAR, month, day, time_hr, time_min, 0))
                utc_dt = pytz.utc.normalize(racer_dt.astimezone(racer_tz))

                fmt = '%Y-%m-%d %H:%M:%S %Z'
                print('Racer time: {}'.format(racer_dt.strftime(fmt)))
                print('UTC time: {}'.format(utc_dt.strftime(fmt)))
                # TODO output both racer's times for confirmation

                self._cm.condordb.schedule_match(command.channel.id, utc_dt)
                match = self._cm.condordb.get_match_from_channel_id(command.channel.id)
                if match:
                    self._cm.condorsheet.schedule_match(match)

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
                racer = CondorRacer(twitch_name)
                racer.discord_id = command.author.id
                racer.discord_name = command.author.name
                self._cm.condordb.register_racer(racer)
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Registered your stream as <twitch.tv/{1}>'.format(command.author.mention, twitch_name))

                #look for race channels with this racer, and unhide them if we find any
                channel_ids = self._cm.condordb.find_channel_ids_with(racer)
                for channel in self._cm.necrobot.server.channels:
                    if int(channel.id) in channel_ids:
                        read_permit = discord.Permissions.none()
                        read_permit.read_messages = True
                        yield from self._cm.necrobot.client.edit_channel_permissions(channel, command.author, allow=read_permit)

class Timezone(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'timezone')
        self.timezone_loc = 'https://github.com/incnone/condorbot/blob/master/data/tz_list.txt'
        self.help_text = 'Register a time zone with your account. Usage is `.timezone <zonename>`. See {0} for a ' \
                        'list of recognized time zones; these strings should be input exactly as-is, e.g., `.timezone US/Eastern`.'.format(self.timezone_loc)
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

class UserInfo(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'userinfo')
        self.help_text = 'Get stream name and timezone info for the given user (or yourself, if no user provided). Usage is `.userinfo <username>`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel.is_private or channel == self._cm.necrobot.main_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        #find the user's discord id
        racer = None
        if len(command.args) == 0:
            racer = self._cm.condordb.get_from_discord_id(command.author.id)
            if not racer:
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: You haven\'t registered; use `.stream <twitchname` to register.'.format(command.author.mention))                
        elif len(command.args) == 1:
            racer = self._cm.condordb.get_from_discord_name(command.args[0])
            if not racer:
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Error: User {1} isn\'t registered.'.format(command.author.mention, command.args[0]))                                
        else:
            yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Error: Too many arguments for `.userinfo`.'.format(command.author.mention))
            return

        if racer:
            yield from self._cm.necrobot.client.send_message(command.channel, 'User info: {0}.'.format(racer.infostr))

class CloseAllRaceChannels(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'closeallracechannels')
        self.help_text = 'Closes _all_ private race channels.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        channel_ids = self._cm.condordb.get_all_race_channel_ids()
        channels_to_del = []
        for channel in self._cm.necrobot.server.channels:
            if int(channel.id) in channel_ids:
                channels_to_del.append(channel)

        for channel in channels_to_del:
            self._cm.condordb.delete_channel(channel.id)
            yield from self._cm.necrobot.client.delete_channel(channel)

class PurgeChannel(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'purgechannel')
        self.help_text = 'Delete all commands in this channel.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.main_channel

    @asyncio.coroutine
    def _do_execute(self, command):
        if command.author == self._cm.necrobot.server.owner:
            logs = yield from self._cm.client.logs_from(channel, limit=1000)
            for message in logs:
                yield from self._cm.client.delete_message(message)

class CondorModule(command.Module):
    def __init__(self, necrobot, db_connection):
        command.Module.__init__(self, necrobot)
        self.condordb = CondorDB(db_connection)
        self.condorsheet = CondorSheet(self.condordb)

        self.command_types = [command.DefaultHelp(self),
                              #MakeWeek(self),
                              PurgeChannel(self),
                              #Schedule(self),
                              Stream(self),
                              Timezone(self),
                              UserInfo(self),
                              #CloseAllRaceChannels(self),
                              ]

    @property
    def infostr(self):
        return 'CoNDOR'

    @property
    def client(self):
        return self.necrobot.client

    @property
    def admin_channel(self):
        return self.necrobot.find_channel(config.ADMIN_CHANNEL_NAME)

    def get_match_channel_name(self, match):
##        racer_1_name = match.racer_1.discord_name if match.racer_1.discord_name else match.racer_1.twitch_name
##        racer_2_name = match.racer_2.discord_name if match.racer_2.discord_name else match.racer_2.twitch_name        
##        return '{0}-{1}'.format(racer_1_name, racer_2_name)
        return '{0}-{1}'.format(match.racer_1.twitch_name, match.racer_2.twitch_name)

    @asyncio.coroutine
    def make_match_channel(self, match):
        already_made_id = self.condordb.find_match_channel_id(match)
        if already_made_id:
            for ch in self.necrobot.server.channels:
                if int(ch.id) == int(already_made_id):
                    return ch
        
        open_match_info = self.condordb.get_open_match_channel_info(match.week)
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

            read_permit = discord.Permissions.none()
            read_permit.read_messages = True
            yield from self.client.edit_channel_permissions(channel, self.necrobot.server.default_role, deny=read_permit)
            
        # otherwise, change the name of the channel we got, and remove permissions from it
        else:
            old_match = open_match_info[1]
            yield from self.client.edit_channel(channel, name=self.get_match_channel_name(match))
            read_permit = discord.Permissions.none()
            read_permit.read_messages = True

            if old_match.racer_1.discord_id:
                racer_1 = self.necrobot.find_member_with_id(old_match.racer_1.discord_id)
                yield from self.client.delete_channel_permissions(channel, racer_1)

            if old_match.racer_2.discord_id:
                racer_2 = self.necrobot.find_member_with_id(old_match.racer_2.discord_id)
                yield from self.client.delete_channel_permissions(channel, racer_2)

            #TODO purge the channel and save the text

        self.condordb.register_channel(match, channel.id)

        if match.racer_1.discord_id:
            racer_1 = self.necrobot.find_member_with_id(match.racer_1.discord_id)
            yield from self.client.edit_channel_permissions(channel, racer_1, allow=read_permit)

        if match.racer_2.discord_id:
            racer_2 = self.necrobot.find_member_with_id(match.racer_2.discord_id)
            yield from self.client.edit_channel_permissions(channel, racer_2, allow=read_permit)

        for role in self.necrobot.admin_roles:
            yield from self.client.edit_channel_permissions(channel, role, allow=read_permit)
        
