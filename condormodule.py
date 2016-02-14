import asyncio
import datetime
import discord

import calendar
from pytz import timezone
import pytz

import command
import condortimestr
import config

from condordb import CondorDB
from condormatch import CondorMatch
from condormatch import CondorRacer
from condorraceroom import RaceRoom
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

class Confirm(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'confirm')
        self.help_text = 'Confirm that you agree to the suggested time for this match.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    @asyncio.coroutine
    def _do_execute(self, command):
        match = self._cm.condordb.get_match_from_channel_id(command.channel.id)
        if not match:
            yield from self._cm.necrobot.client.send_message(command.channel,
                'Error: This match wasn\'t found in the database. Please contact CoNDOR Staff.')
            return        

        if not match.scheduled:
            yield from self._cm.necrobot.client.send_message(command.channel,
                'Error: A scheduled time for this match has not been suggested. Use `.suggest` to suggest a time.')
            return

        racer = self._cm.condordb.get_from_discord_id(command.author.id)
        if not racer:
            yield from self._cm.necrobot.client.send_message(command.channel,
                'Error: {0} is not registered. Please register with `.stream` in the main channel. ' \
                'If the problem persists, contact CoNDOR Staff.'.format(command.author.mention))
            return  

        if match.is_confirmed_by(racer):
            yield from self._cm.necrobot.client.send_message(command.channel,
                '{0}: You\'ve already confirmed this time.'.format(command.author.mention))
            return              

        match.confirm(racer)
        self._cm.condordb.update_match(match)

        racer_dt = racer.utc_to_local(match.time)
        if not racer_dt:
            yield from self._cm.necrobot.client.send_message(command.channel,
                'Error: {0}: I have your timezone stored as "{1}", but I can\'t parse this as a timezone. ' \
                'Please register a valid timezone with `.timezone`. If this problem persists, contact ' \
                'CoNDOR Staff.'.format(command.author.mention, racer.timezone))
            return
    
        yield from self._cm.necrobot.client.send_message(command.channel,
            '{0}: Confirmed acceptance of match time {1}.'.format(command.author.mention, condortimestr.get_time_str(racer_dt)))

        if match.confirmed:
            self._cm.condorsheet.schedule_match(match)
            yield from self._cm.necrobot.client.send_message(command.channel, 'The match has been officially scheduled.')
            yield from self._cm.necrobot.client.send_message(self._cm.necrobot.schedule_channel,
                '{0} v {1}: {2}.'.format(match.racer_1.twitch_name, match.racer_2.twitch_name, condortimestr.get_time_str(match.time)))
            
        yield from self._cm.update_match_channel(match)
        asyncio.ensure_future(self._cm.channel_alert(command.channel.id))
    
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
            week = -1
            try:
                week = int(command.args[0])
            except ValueError:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error in makeweek: couldn\'t parse arg <{}> as a week number.'.format(command.args[0]))
                return

            if week != -1:
                yield from self._cm.necrobot.client.send_message(command.channel, 'Making race rooms for week {0}...'.format(week))
                try:
                    matches = self._cm.condorsheet.get_matches(week)
                    if matches:
                        for match in matches:
                            yield from self._cm.make_match_channel(match)
                            yield from asyncio.sleep(1)
                    yield from self._cm.necrobot.client.send_message(command.channel, 'All matches made.')
                except Exception as e:
                    yield from self._cm.necrobot.client.send_message(command.channel, 'An error occurred. Please call `.makeweek` again.')
                    raise e

class Staff(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'staff')
        self.help_text = 'Alert the CoNDOR Staff to a problem.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return not channel.is_private

    @asyncio.coroutine
    def _do_execute(self, command):
        yield from self._cm.necrobot.client.send_message(self._cm.necrobot.notifications_channel,
            'Alert: `.staff` called by {0} in channel {1}.'.format(command.author.mention, command.channel.mention))
        yield from self._cm.necrobot.client.send_message(command.channel,
            '{0}: CoNDOR Staff has been alerted.'.format(command.author.mention))

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
                success = self._cm.condordb.register_racer(racer)
                if not success:
                    yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Error: unable to register your stream as <twitch.tv/{1}>, because that ' \
                                                                     'stream is already registered to a different account.'.format(command.author.mention, twitch_name))                    
                    return
                
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: Registered your stream as <twitch.tv/{1}>'.format(command.author.mention, twitch_name))

                #look for race channels with this racer, and unhide them if we find any
                channel_ids = self._cm.condordb.find_channel_ids_with(racer)
                for channel in self._cm.necrobot.server.channels:
                    if int(channel.id) in channel_ids:
                        read_permit = discord.Permissions.none()
                        read_permit.read_messages = True
                        yield from self._cm.necrobot.client.edit_channel_permissions(channel, command.author, allow=read_permit)

class Suggest(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'suggest')
        self.help_text = 'Propose a time to schedule a match. Example: `.suggest February 18 17:30` (your local time; choose a local time with `.timezone`). \n \n' \
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
            yield from self._cm.necrobot.client.send_message(command.channel,
                'Error: Couldn\'t parse your arguments as a date and time. Model is, e.g., `.suggest March 9 5:30p`.')
            return
        else:
            match = self._cm.condordb.get_match_from_channel_id(command.channel.id)
            if not match:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: This match wasn\'t found in the database. Please contact CoNDOR Staff.')
                return
            
            racer = self._cm.condordb.get_from_discord_id(command.author.id)
            if not racer:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: {0} is not registered. Please register with `.stream` in the main channel. ' \
                    'If the problem persists, contact CoNDOR Staff.'.format(command.author.mention))
                return                 
            
            cmd_caller_racer_number = 0
            if int(command.author.id) == int(match.racer_1.discord_id):
                cmd_caller_racer_number = 1
            elif int(command.author.id) == int(match.racer_2.discord_id):
                cmd_caller_racer_number = 2
            else:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: {0} does not appear to be one of the racers in this match. ' \
                    'If this is in error, contact CoNDOR Staff.'.format(command.author.mention))
                return
                
            month_name = command.args[0].capitalize()
            if not month_name in calendar.month_name:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: Couldn\'t parse {0} as the name of a month.'.format(command.args[0]))
                return
            month = list(calendar.month_name).index(month_name)

            day = -1
            try:            
                day = int(command.args[1])
            except ValueError:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: Couldn\'t parse {0} as a day of the month.'.format(command.args[1]))
                return                
                
            time_args = command.args[2].split(':')
            if len(time_args) != 2:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: Couldn\'t parse {0} as a time.'.format(command.args[2]))
                return

            try:
                time_min = int(time_args[1].rstrip('apm'))
                time_hr = int(time_args[0])
            except ValueError:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: Couldn\'t parse {0} as a time.'.format(command.args[2]))
                return                

            if (time_args[1].endswith('p') or time_args[1].endswith('pm')) and not time_hr == 12:
                time_hr += 12
            elif (time_args[1].endswith('a') or time_args[1].endswith('am')) and time_hr == 12:
                time_hr = 0

            utc_dt = racer.local_to_utc(datetime.datetime(config.SEASON_YEAR, month, day, time_hr, time_min, 0))
            if not utc_dt:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    'Error: {0}: I have your timezone stored as "{1}", but I can\'t parse this as a timezone. ' \
                    'Please register a valid timezone with `.timezone`. If this problem persists, contact ' \
                    'CoNDOR Staff.'.format(command.author.mention, racer.timezone))
                return

            time_until = utc_dt - pytz.utc.localize(datetime.datetime.utcnow())
            if not time_until.total_seconds() > 0:
                yield from self._cm.necrobot.client.send_message(command.channel,
                    '{0}: Error: The time you are suggesting for the match appears to be in the past.'.format(command.author.mention))
                return                

            match.schedule(utc_dt, racer)

            #update the db
            self._cm.condordb.update_match(match)

            #output what we did
            yield from self._cm.update_match_channel(match)
            racers = [match.racer_1, match.racer_2]
            for racer in racers:
                member = self._cm.necrobot.find_member_with_id(racer.discord_id)
                if member:
                    if racer.timezone:
                        r_tz = pytz.timezone(racer.timezone)
                        r_dt = r_tz.normalize(utc_dt.astimezone(pytz.utc))
                        yield from self._cm.necrobot.client.send_message(command.channel,
                            '{0}: This match is suggested to be scheduled for {1}. Please confirm with `.confirm`.'.format(member.mention, condortimestr.get_time_str(r_dt)))
                    else:
                        yield from self._cm.necrobot.client.send_message(command.channel,
                            '{0}: A match time has been suggested; please confirm with `.confirm`. I also suggest you register a timezone (use `.timezone`), so I can convert to your local time.'.format(member.mention))  

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
        return channel.is_private or channel == self._cm.necrobot.main_channel or self._cm.condordb.is_registered_channel(channel.id)

    @asyncio.coroutine
    def _do_execute(self, command):
        #find the user's discord id
        racer = None
        if len(command.args) == 0:
            racer = self._cm.condordb.get_from_discord_id(command.author.id)
            if not racer:
                yield from self._cm.necrobot.client.send_message(command.channel, '{0}: You haven\'t registered; use `.stream <twitchname>` to register.'.format(command.author.mention))                
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

##class PurgeChannel(command.CommandType):
##    def __init__(self, condor_module):
##        command.CommandType.__init__(self, 'purgechannel')
##        self.help_text = 'Delete all commands in this channel.'
##        self.suppress_help = True
##        self._cm = condor_module
##
##    def recognized_channel(self, channel):
##        return channel == self._cm.necrobot.main_channel
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if command.author == self._cm.necrobot.server.owner:
##            logs = yield from self._cm.client.logs_from(command.channel, limit=1000)
##            for message in logs:
##                yield from self._cm.client.delete_message(message)

class CondorModule(command.Module):
    def __init__(self, necrobot, db_connection):
        command.Module.__init__(self, necrobot)
        self.condordb = CondorDB(db_connection)
        self.condorsheet = CondorSheet(self.condordb)
        self._racerooms = []

        self.command_types = [command.DefaultHelp(self),
                              Confirm(self),
                              MakeWeek(self),
                              Staff(self),
                              Stream(self),
                              Suggest(self),
                              Timezone(self),
                              UserInfo(self),
                              CloseAllRaceChannels(self),
                              ]

    @asyncio.coroutine
    def initialize(self):
        yield from self.run_channel_alerts()

    @property
    def infostr(self):
        return 'CoNDOR'

    @property
    def client(self):
        return self.necrobot.client

    @property
    def admin_channel(self):
        return self.necrobot.find_channel(config.ADMIN_CHANNEL_NAME)

    # Attempts to execute the given command (if a command of its type is in command_types)
    # Overrides
    @asyncio.coroutine
    def execute(self, command):
        for cmd_type in self.command_types:
            yield from cmd_type.execute(command)
        for room in self._racerooms:
            if command.channel == room.channel:
                yield from room.execute(command)

    def get_match_channel_name(self, match):
        return '{0}-{1}'.format(match.racer_1.twitch_name, match.racer_2.twitch_name)

    @asyncio.coroutine
    def make_match_channel(self, match):
        already_made_id = self.condordb.find_match_channel_id(match)
        if already_made_id:
            for ch in self.necrobot.server.channels:
                if int(ch.id) == int(already_made_id):
                    return
        
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

        yield from self.update_match_channel(match)
    
    # makes a new "race room" in the match channel if not already made
    @asyncio.coroutine
    def make_race_room(self, match):
        channel = self.necrobot.find_channel_with_id(self.condordb.find_match_channel_id(match))
        if channel:
            #if we already have a room for this channel, return
            for room in self._racerooms:
                if int(room.channel.id) == int(channel.id):
                    return  
            room = RaceRoom(self, match, channel)
            self._racerooms.append(room)
            asyncio.ensure_future(room.initialize())

    @asyncio.coroutine
    def update_match_channel(self, match):
        if match.confirmed and match.time_until_alert < datetime.timedelta(seconds=1):
            yield from self.make_race_room(match)
        else:
            channel = self.necrobot.find_channel_with_id(self.condordb.find_match_channel_id(match))
            if channel:
                #if we have a RaceRoom attached to this channel, return; print an error, since this shouldn't be happening
                for room in self._racerooms:
                    if int(room.channel.id) == int(channel.id):
                        print('Error: Unconfirmed match with a RaceRoom attached to it in channel #{0}.'.format(channel.name))
                        return 
                
                yield from self.necrobot.client.edit_channel(channel, topic=match.topic_str)

    @asyncio.coroutine
    def channel_alert(self, channel_id):
        match = self.condordb.get_match_from_channel_id(channel_id)
        if match and match.confirmed:
            if match.time_until_alert.total_seconds() > 0:
                yield from asyncio.sleep(match.time_until_alert.total_seconds())
            yield from self.update_match_channel(self.condordb.get_match_from_channel_id(channel_id))

    @asyncio.coroutine
    def run_channel_alerts(self):
        for channel_id in self.condordb.get_all_race_channel_ids():
            asyncio.ensure_future(self.channel_alert(channel_id))
        
            
        
