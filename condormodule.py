import asyncio
import codecs
import datetime
import discord
import logging

import calendar
import pytz

import clparse
import command
import condortimestr
import config
import racetime

from condordb import CondorDB
from condormatch import CondorRacer
from condormatch import CondorLeague
from condorraceroom import RaceRoom
from condorsheet import CondorSheet
from events import Events


def parse_schedule_args(cmd):
    if not len(cmd.args) == 3:
        return None

    parsed_args = []

    month_name = cmd.args[0].capitalize()
    cmd_len = len(month_name)
    month_found = False
    if cmd_len >= 3:
        for actual_month in calendar.month_name:
            if actual_month[:cmd_len] == month_name:
                month_found = True
                parsed_args.append(list(calendar.month_name).index(actual_month))
                break

    if not month_found:
        parsed_args.append(None)
    
    try:            
        parsed_args.append(int(cmd.args[1]))
    except ValueError:
        parsed_args.append(None)
        
    time_args = cmd.args[2].split(':')
    if len(time_args) == 1:
        try:
            time_hr = int(time_args[0].rstrip('apm'))
            if (time_args[0].endswith('p') or time_args[0].endswith('pm')) and not time_hr == 12:
                time_hr += 12
            elif (time_args[0].endswith('a') or time_args[0].endswith('am')) and time_hr == 12:
                time_hr = 0
                
            parsed_args.append(int(0))        
            parsed_args.append(time_hr)
        except ValueError:
            parsed_args.append(None)
            parsed_args.append(None)
            
    elif len(time_args) == 2:
        try:
            time_min = int(time_args[1].rstrip('apm'))
            parsed_args.append(time_min)
        except ValueError:
            parsed_args.append(None)

        try:
            time_hr = int(time_args[0])
            if (time_args[1].endswith('p') or time_args[1].endswith('pm')) and not time_hr == 12:
                time_hr += 12
            elif (time_args[1].endswith('a') or time_args[1].endswith('am')) and time_hr == 12:
                time_hr = 0
            
            parsed_args.append(time_hr)
        except ValueError:
            parsed_args.append(None)
            
    else:
        parsed_args.append(None)
        parsed_args.append(None)
        return parsed_args

    return parsed_args


class UpdateGSheetSchedule(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'updategsheetschedule')
        self.help_text = 'Posts all scheduled matches to the GSheet. This is for correcting errors and shouldn\'t ' \
                         'need to be called normally.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        await self._cm.necrobot.client.send_message(
            cmd.channel,
            'Updating the GSheet schedule...')
        try:
            for match in self._cm.condordb.get_all_matches():
                if match.confirmed:
                    await self._cm.condorsheet.schedule_match(match)
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Done.')
        except Exception as e:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'An error occurred.')
            raise e


class UpdateCawmentary(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'updatecawmentary')
        self.help_text = 'Update the database cawmentators from the GSheet. Warning: _very slow_.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel.is_private or channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            await self._cm.necrobot.client.send_message(cmd.channel, 'Updating cawmentary...')
            for match in self._cm.condordb.get_all_matches():
                cawmentator = await self._cm.condorsheet.get_cawmentary(match)
                if cawmentator is not None:
                    racer = self._cm.condordb.get_from_twitch_name(cawmentator)
                    if racer is not None:
                        self._cm.condordb.add_cawmentary(match, racer.discord_id)
            await self._cm.necrobot.client.send_message(cmd.channel, 'Done.')


class Vod(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'vod')
        self.help_text = 'Add a link to a vod to the GSheet for a given match. Usage is `.vod <racer1> ' \
                         '<racer2> <vod URL>`, where `<racer1>` and `<racer2>` are the RTMP names of the racers in ' \
                         'the match, and `<vod URL>` is the full URL to the vod.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    async def _do_execute(self, cmd):
        if len(cmd.args) != 3:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: Wrong number of arguments for `.vod`.')
        else:
            # find the match
            racer_1 = self._cm.condordb.get_from_rtmp_name(cmd.args[0])
            racer_2 = self._cm.condordb.get_from_rtmp_name(cmd.args[1])
            match = self._cm.condordb.get_match(racer_1, racer_2)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t find a match between {0} and {1}.'.format(cmd.args[0], cmd.args[1]))
                return

            url_link = cmd.args[2]
            await self._cm.condorsheet.add_vod_link(match, url_link)
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Added a vod for the match {0}-{1}.'.format(
                    racer_1.escaped_unique_name, racer_2.escaped_unique_name))


class Cawmentate(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'cawmentate')
        self.help_text = 'Register yourself for Cawmentary for a given match. Usage is `.cawmentate <racer1> ' \
                         '<racer2>`, where `<racer1>` and `<racer2>` are the RTMP names of the racers in the match.' \
                         ' (See the Google Doc or `.userinfo` for RTMP names.) If there is already a Cawmentator for ' \
                         'the match, this command will fail -- consider talking to the person who has already ' \
                         'registered about co-cawmentary. (You can use `.uncawmentate <racer1> <racer2>` to ' \
                         'de-register yourself for a match.)'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    async def _do_execute(self, cmd):
        if len(cmd.args) != 2:
            print('Error in cawmentate: wrong command arg length.')
        else:
            # find the match
            racer_1 = self._cm.condordb.get_from_rtmp_name(cmd.args[0])
            racer_2 = self._cm.condordb.get_from_rtmp_name(cmd.args[1])
            match = self._cm.condordb.get_match(racer_1, racer_2)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t find a match between {0} and {1}.'.format(cmd.args[0], cmd.args[1]))
                return

            # check for already having a cawmentator
            cawmentator = await self._cm.condorsheet.get_cawmentary(match)
            if cawmentator:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'This match already has a cawmentator ({0}).'.format(cawmentator))
                return
            
            # register the cawmentary in the db and also on the gsheet
            cawmentator = self._cm.condordb.get_from_discord_id(cmd.author.id)
            if not cawmentator or not cawmentator.twitch_name:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: You need to register a twitch stream before you can be assigned cawmentary. '
                    '(Use `.stream`.)'.format(cmd.author.mention))
                return
            
            self._cm.condordb.add_cawmentary(match, cawmentator.discord_id)
            await self._cm.condorsheet.add_cawmentary(match, cawmentator.twitch_name)
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Added {0} as cawmentary for the match {1}-{2}.'.format(
                    cmd.author.mention, racer_1.escaped_unique_name, racer_2.escaped_unique_name))


class Confirm(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'confirm')
        self.help_text = 'Confirm that you agree to the suggested time for this match.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
        if not match:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: This match wasn\'t found in the database. Please contact CoNDOR Staff.')
            return        

        if not match.scheduled:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: A scheduled time for this match has not been suggested. Use `.suggest` to suggest a time.')
            return

        racer = self._cm.condordb.get_from_discord_id(cmd.author.id)
        if not racer:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: {0} is not registered. Please register with `.register` in the main channel. '
                'If the problem persists, contact CoNDOR Staff.'.format(cmd.author.mention))
            return  

        if match.is_confirmed_by(racer):
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: You\'ve already confirmed this time.'.format(cmd.author.mention))
            await self._cm.update_match_channel(match)
            return              

        match.confirm(racer)
        self._cm.condordb.update_match(match)

        racer_dt = racer.utc_to_local(match.time)
        if not racer_dt:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: {0}: I have your timezone stored as "{1}", but I can\'t parse this as a timezone. '
                'Please register a valid timezone with `.timezone`. If this problem persists, contact '
                'CoNDOR Staff.'.format(cmd.author.mention, racer.timezone))
            return

        await self._cm.necrobot.client.send_message(
            cmd.channel,
            '{0}: Confirmed acceptance of match time {1}.'.format(
                cmd.author.mention, condortimestr.get_time_str(racer_dt)))

        if match.confirmed:
            await self._cm.condorsheet.schedule_match(match)
            await self._cm.necrobot.client.send_message(
                cmd.channel, 
                'The match has been officially scheduled.')

            await self._cm.update_match_channel(match)
            await self._cm.update_schedule_channel()
    
    
class MakeWeek(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'makeweek')
        self.help_text = 'Make the race rooms for a week. Usage is `.makeweek <week_number>`, e.g., `.makeweek 1`. ' \
                         'This will look on the GSheet for the worksheet titled "Week 1", look in the "Racer 1" ' \
                         'column between the heading "Racer 1" and the special character "--------" (eight hyphens), ' \
                         'and make matchup channels for each matchup it finds (reading the Racer 1 column as the ' \
                         'twitch name of the first racer, and the column to its right as the twitch name of the ' \
                         'second racer). This will make private channels visible to only the racers in that race; ' \
                         'note that racers will have to register (with `.stream <twitchname>`) in order to be able to' \
                         ' see the channel for their race.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        if len(cmd.args) != 1:
            print('Error in makeweek: wrong cmd arg length.')
        else:
            try:
                week = int(cmd.args[0])
            except ValueError:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error in makeweek: couldn\'t parse arg <{}> as a week number.'.format(cmd.args[0]))
                return

            if week != -1:
                await self._cm.necrobot.client.send_message(
                    cmd.channel, 
                    'Making race rooms for week {0}...'.format(week))
                try:
                    matches = await self._cm.condorsheet.get_matches(week)
                    if matches:
                        matches = sorted(matches, key=lambda m: m.channel_name)
                        for match in matches:
                            await self._cm.make_match_channel(match)
                    await self._cm.necrobot.client.send_message(cmd.channel, 'All matches made.')
                except Exception as e:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel, 
                        'An error occurred. Please call `.makeweek` again.')
                    raise e


class CloseWeek(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'closeweek')
        self.help_text = 'Close the race rooms for a week. Saves text in their channels to a .log file.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        if len(cmd.args) != 1:
            print('Error in closeweek: wrong command arg length.')
        else:
            try:
                week = int(cmd.args[0])
            except ValueError:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error in makeweek: couldn\'t parse arg <{}> as a week number.'.format(cmd.args[0]))
                return

            if week != -1:
                await self._cm.necrobot.client.send_message(
                    cmd.channel, 'Closing race rooms for week {0}...'.format(week))
                try:
                    channel_ids = self._cm.condordb.get_race_channels_from_week(week)
                    if channel_ids:
                        for channel_id in channel_ids:
                            channel = self._cm.necrobot.find_channel_with_id(channel_id)
                            if channel:
                                await self._cm.save_and_delete(channel)
                                await asyncio.sleep(0.5)
                    await self._cm.necrobot.client.send_message(
                        cmd.channel, 'All racerooms closed.')
                except Exception as e:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel, 'An error occurred. Please call `.closeweek` again.')
                    raise e        


class NextRace(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'next', 'nextrace', 'nextmatch')
        self.help_text = 'Give information about the next upcoming race(s).'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    async def _do_execute(self, cmd):
        utcnow = pytz.utc.localize(datetime.datetime.utcnow())
        matches = self._cm.get_upcoming_and_current_matches(utcnow)
        if not matches:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Didn\'t find any scheduled matches!')
            return

        next_match = matches[0]
        upcoming_matches = []
        for match in matches:
            if match.time - next_match.time < datetime.timedelta(hours=1, minutes=5):
                upcoming_matches.append(match)

        infobox = await self._cm.get_nextrace_displaytext(upcoming_matches)
        await self._cm.necrobot.client.send_message(cmd.channel, infobox)


class Register(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'register')
        self.help_text = 'Register your current discord name in the bot\'s database.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel or channel.is_private

    async def _do_execute(self, cmd):
        self._cm.condordb.register(cmd.author)
        await self._cm.necrobot.client.send_message(
            cmd.channel,
            '{0}: Registered your current discord name.'.format(
                cmd.author.mention))


class RTMP(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'rtmp')
        self.help_text = 'Register an RTMP stream. Usage is `.rtmp <discord_name> <rtmp_name>`, ' \
                         'e.g., `.rtmp mac macRTMP`. Discord name should be enclosed in quotes if it contains a space.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel or channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        if not self._cm.necrobot.is_admin(cmd.author):
            return

        if len(cmd.args) != 2:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'I was unable to parse your RTMP command because you gave the wrong number of arguments. '
                'Use `.rtmp <discord_name> <rtmp_name>`.')
            return

        discord_name = cmd.args[0]
        # Find the discord memeber
        discord_members = self._cm.necrobot.find_members(discord_name)
        if len(discord_members) == 0:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: Couldn\'t find any users with username <{0}>. '
                'Note this is case-sensitive.'.format(discord_name))
            return
        elif len(discord_members) == 2:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: Found several users with username <{0}>. '
                'I can\'t handle this; contact incnone and make him fix me.'.format(discord_name))
            return

        # Register in the database
        discord_member = discord_members[0]
        rtmp_name = cmd.args[1]

        success = self._cm.condordb.register_rtmp(discord_member, rtmp_name)
        if success:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Registered RTMP for user {0} as `{1}`.'.format(discord_member.name, rtmp_name))
        else:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Unable to register the RTMP stream `{0}`, because that name is already '
                'registered to a different discord account.'.format(rtmp_name))

        # Set channel permissions
        member_as_condor_racer = CondorRacer(discord_member.id)
        channel_ids = self._cm.condordb.find_channel_ids_with(member_as_condor_racer)
        for channel_id in channel_ids:
            channel = self._cm.necrobot.find_channel_with_id(channel_id)
            if channel is not None:
                permit_read = discord.PermissionOverwrite()
                permit_read.read_messages = True
                await self._cm.necrobot.client.edit_channel_permissions(channel, discord_member, permit_read)


class Staff(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'staff')
        self.help_text = 'Alert the CoNDOR Staff to a problem.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return not channel.is_private

    async def _do_execute(self, cmd):
        await self._cm.necrobot.client.send_message(
            self._cm.necrobot.notifications_channel,
            'Alert: `.staff` called by {0} in channel {1}.'.format(cmd.author.mention, cmd.channel.mention))
        condor_staff_role = self._cm.necrobot.condor_staff
        if condor_staff_role is not None:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: Alerting CoNDOR Staff: {1}.'.format(
                    cmd.author.mention,
                    condor_staff_role.mention))


class Stream(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'stream')
        self.help_text = 'Register a twitch stream. Usage is `.stream <twitchname>`, e.g., `.stream incnone`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel or channel.is_private

    async def _do_execute(self, cmd):
        if len(cmd.args) != 1:
            await self._cm.necrobot.client.send_message(
                cmd.channel, 
                '{0}: I was unable to parse your stream name because you gave too many arguments. '
                'Use `.stream <twitchname>`.'.format(cmd.author.mention))
        else:
            twitch_name = cmd.args[0]
            if '/' in twitch_name:
                await self._cm.necrobot.client.send_message(
                    cmd.channel, 
                    '{0}: Error: your stream name cannot contain the character /. (Maybe you accidentally '
                    'included the "twitch.tv/" part of your stream name?)'.format(cmd.author.mention))
            else:
                success = self._cm.condordb.register_twitch(cmd.author, twitch_name)
                if success:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        '{0}: Registered your twitch as `twitch.tv/{1}`'.format(
                            cmd.author.mention, twitch_name))
                else:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        '{0}: Unable to register the twitch stream `twitch.tv/{1}`, because that name is already '
                        'registered to a different discord account.'.format(
                            cmd.author.mention, twitch_name))


class Suggest(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'suggest')
        self.help_text = 'Propose a time to schedule a match. Example: `.suggest February 18 17:30` (your local ' \
                         'time; choose a local time with `.timezone`). \n \n' \
                         'General usage is `.schedule <localtime>`, where `<localtime>` is a date and time in your ' \
                         'registered timezone. (Use `.timezone` to register a timezone with your account.) ' \
                         '`<localtime>` takes the form `<month> <date> <time>`, where `<month>` is the English month ' \
                         'name (February, March, April), `<date>` is the date number, and `<time>` is a time ' \
                         '`[h]h:mm`. Times can be given an am/pm rider or this can be left off, e.g., `7:30a` and ' \
                         '`7:30` are interpreted as the same time, as are `15:45` and `3:45p`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if len(cmd.args) != 3:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: Couldn\'t parse your arguments as a date and time. Model is, e.g., `.suggest March 9 5:30p`.')
            return
        else:
            match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match wasn\'t found in the database. Please contact CoNDOR Staff.')
                return

            if match.confirmed:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'The scheduled time for this match has already been confirmed by both racers. To reschedule, '
                    'both racers should first call `.unconfirm`; you will then be able to `.suggest` a new time.')
                return
            
            racer = self._cm.condordb.get_from_discord_id(cmd.author.id)
            if not racer:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: {0} is not registered. Please register with `.stream` in the main channel. '
                    'If the problem persists, contact CoNDOR Staff.'.format(cmd.author.mention))
                return                 

            if not match.racer_1 or not match.racer_2 \
                    or not match.racer_1.discord_id or not match.racer_2.discord_id:
                await self._cm.necrobot.client.send_messate(
                    cmd.channel,
                    'Error: At least one of the racers in this match is not registered, and needs to call '
                    '`.register` in the main channel. (To check if you are registered, you can call `.userinfo '
                    '<discord name>`. Use quotes around your discord name if it contains a space.)')
                return

            if not int(cmd.author.id) == int(match.racer_1.discord_id) \
                    and not int(cmd.author.id) == int(match.racer_2.discord_id):
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: {0} does not appear to be one of the racers in this match. '
                    'If this is in error, contact CoNDOR Staff.'.format(cmd.author.mention))
                return

            # Parse the inputs as a datetime
            schedule_args = parse_schedule_args(cmd)
            if not schedule_args:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t parse your arguments as a date and time. Model is, e.g., '
                    '`.suggest March 9 5:30p`.')
                return
            elif schedule_args[0] is None:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t parse {0} as the name of a month.'.format(cmd.args[0]))
                return
            elif schedule_args[1] is None:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t parse {0} as a day of the month.'.format(cmd.args[1]))
                return
            elif schedule_args[2] is None or schedule_args[3] is None:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t parse {0} as a time.'.format(cmd.args[2]))
                return

            month = schedule_args[0]
            day = schedule_args[1]
            time_min = schedule_args[2]
            time_hr = schedule_args[3]            

            try:
                utc_dt = racer.local_to_utc(datetime.datetime(config.SEASON_YEAR, month, day, time_hr, time_min, 0))
            except ValueError as e:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error parsing your date: {0}.'.format(str(e)))
                return

            # Check if the racer has stored a valid timezone
            if not utc_dt:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: {0}: I have your timezone stored as "{1}", but I can\'t parse this as a timezone. '
                    'Please register a valid timezone with `.timezone`. If this problem persists, contact '
                    'CoNDOR Staff.'.format(cmd.author.mention, racer.timezone))
                return

            # Check if the scheduled time is in the past
            utcnow = pytz.utc.localize(datetime.datetime.utcnow())
            time_until = utc_dt - utcnow
            if not time_until.total_seconds() > 0:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: Error: The time you are suggesting for the match appears to be in the past.'.format(
                        cmd.author.mention))
                return                

            # Check if the scheduled time is before friday at noon
            today_date = datetime.date.today()
            friday_date = today_date + datetime.timedelta(days=((4-today_date.weekday()) % 7))
            friday_midnight_eastern = pytz.timezone('US/Eastern').localize(
                datetime.datetime.combine(friday_date, datetime.time(hour=0)))
            time_until_friday = utc_dt - friday_midnight_eastern
            if time_until_friday.total_seconds() > 0:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: Error: Matches must be scheduled before next Thursday at midnight US/Eastern.'.format(
                        cmd.author.mention))
                return

            # Schedule the match
            match.schedule(utc_dt, racer)

            # Automatically confirm
            match.confirm(racer)

            # update the db
            self._cm.condordb.update_match(match)

            # output what we did
            await self._cm.update_match_channel(match)
            racers = [match.racer_1, match.racer_2]
            for match_racer in racers:
                member = self._cm.necrobot.find_member_with_id(match_racer.discord_id)
                if member:
                    if match_racer.timezone:
                        r_tz = pytz.timezone(match_racer.timezone)
                        r_dt = r_tz.normalize(utc_dt.astimezone(pytz.utc))
                        if match_racer == racer:
                            await self._cm.necrobot.client.send_message(
                                cmd.channel,
                                '{0}: You\'ve suggested the match be scheduled for {1}. Waiting for the other '
                                'racer to `confirm.`'.format(member.mention, condortimestr.get_time_str(r_dt)))
                        else:
                            await self._cm.necrobot.client.send_message(
                                cmd.channel,
                                '{0}: This match is suggested to be scheduled for {1}. Please confirm with '
                                '`.confirm`.'.format(member.mention, condortimestr.get_time_str(r_dt)))
                    else:
                        await self._cm.necrobot.client.send_message(
                            cmd.channel,
                            '{0}: A match time has been suggested; please confirm with `.confirm`. I also suggest '
                            'you register a timezone (use `.timezone`), so I can convert to your local time.'.format(
                                member.mention))


class Timezone(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'timezone')
        self.timezone_loc = 'https://github.com/incnone/condorbot/blob/master/data/tz_list.txt'
        self.help_text = 'Register a time zone with your account. Usage is `.timezone <zonename>`. See <{0}> for a ' \
                         'list of recognized time zones; these strings should be input exactly as-is, e.g., ' \
                         '`.timezone US/Eastern`.'.format(self.timezone_loc)
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel or channel.is_private

    async def _do_execute(self, cmd):
        if len(cmd.args) != 1:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: I was unable to parse your timezone because you gave too many arguments. '
                'See <{1}> for a list of timezones.'.format(cmd.author.mention, self.timezone_loc))
        else:
            tz_name = cmd.args[0]
            if tz_name in pytz.common_timezones:
                self._cm.condordb.register_timezone(cmd.author, tz_name)
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: Timezone set as {1}.'.format(cmd.author.mention, tz_name))
            else:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: I was unable to parse your timezone. See <{1}> for a list of timezones.'.format(
                        cmd.author.mention, self.timezone_loc))


class Uncawmentate(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'uncawmentate')
        self.help_text = 'Unregister for match cawmentary. Usage is `.uncawmentate <racer1> <racer2>`, where ' \
                         '`<racer1>` and `<racer2>` are the RTMP names of the racers in the match you want to ' \
                         'de-register for. (See the Google Doc or `.userinfo` for RTMP names.)'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel

    async def _do_execute(self, cmd):
        if len(cmd.args) != 2:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: Wrong arg length for `.uncawmentate` (please specify the RTMP names '
                'of the racers in the match).'.format(cmd.author))
        else:
            # find the match
            racer_1 = self._cm.condordb.get_from_rtmp_name(cmd.args[0])
            racer_2 = self._cm.condordb.get_from_rtmp_name(cmd.args[1])
            match = self._cm.condordb.get_match(racer_1, racer_2)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t find a match between {0} and {1}.'.format(cmd.args[0], cmd.args[1]))
                return

            # find the cawmentator
            cawmentator = self._cm.condordb.get_from_discord_id(cmd.author.id)
            if not cawmentator:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: You need to register a twitch stream before you can be assigned cawmentary. '
                    '(Use `.stream`.)'.format(cmd.author.mention))
                return

            # check for already having a cawmentator
            match_cawmentator = await self._cm.condorsheet.get_cawmentary(match)
            if not match_cawmentator:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: This match has no cawmentator.'.format(cmd.author.mention, match_cawmentator))
                return
            
            if match_cawmentator.lower() != cawmentator.twitch_name.lower():
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: This match is being cawmentated by {1}.'.format(cmd.author.mention, match_cawmentator))
                return
            
            # register the cawmentary in the db and also on the gsheet
            self._cm.condordb.remove_cawmentary(match)
            await self._cm.condorsheet.remove_cawmentary(match)
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Removed {0} as cawmentary for the match {1}-{2}.'.format(
                    cmd.author.mention, racer_1.escaped_unique_name, racer_2.escaped_unique_name))


class Postpone(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'postpone')
        self.help_text = 'Postpones the match. An admin can resume with `.forcebeginmatch`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match wasn\'t found in the database.')
                return

            if not match.confirmed:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match hasn\'t been scheduled.')
                return

            match.force_unconfirm()
            self._cm.condordb.update_match(match)

            await self._cm.condorsheet.unschedule_match(match)
            await self._cm.delete_race_room(match)
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'The match has been postponed. An admin can resume with `.forcebeginmatch`, or the racers can '
                '`.suggest` a new time as usual.')

            await self._cm.update_match_channel(match)


class Unconfirm(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'unconfirm')
        self.help_text = 'If the schedule has not yet been confirmed by both racers, undoes an earlier `.confirm`. ' \
                         'If the schedule has been confirmed by both racers, then both racers need to call ' \
                         '`.unconfirm` to unschedule the match.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
        if not match:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: This match wasn\'t found in the database. Please contact CoNDOR Staff.')
            return

        racer = self._cm.condordb.get_from_discord_id(cmd.author.id)
        if not racer:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                'Error: {0} is not registered. Please register with `.stream` in the main channel. '
                'If the problem persists, contact CoNDOR Staff.'.format(cmd.author.mention))
            return          

        if not match.is_confirmed_by(racer):
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: You haven\'t yet confirmed the suggested time.'.format(cmd.author.mention))
            return 

        match_confirmed = match.confirmed
        match.unconfirm(racer)
        self._cm.condordb.update_match(match)

        # if match was scheduled...
        if match_confirmed:
            # ...and still is
            if match.confirmed:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0} wishes to remove the current scheduled time. The other racer must also '
                    '`.unconfirm`.'.format(cmd.author))
            # ...and now is not
            else:
                await self._cm.condorsheet.unschedule_match(match)
                await self._cm.delete_race_room(match)
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'The match has been unscheduled. Please `.suggest` a new time when one has been agreed upon.')
        # if match was not scheduled
        else:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0} has unconfirmed the current suggested time.'.format(cmd.author))

        await self._cm.update_match_channel(match)


class Fastest(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'fastest')
        self.help_text = 'Get a list of the fastest clears.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel or channel.is_private

    async def _do_execute(self, cmd):
        fastest_list = self._cm.condordb.get_fastest_clears(15)
        list_text = '```Fastest wins:'
        for clear in fastest_list:
            list_text += '\n{0:>9} - {1} (vs {2}, week {3})'.format(
                racetime.to_str(clear[0]),
                clear[1],
                clear[2],
                clear[3])
        list_text += '```'
        await self._cm.necrobot.client.send_message(cmd.channel, list_text)


class Stats(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'stats')
        self.help_text = 'Display racer stats. Usage is `.stats <rtmp_name>`. If no racer is given, will display ' \
                         'stats for the command caller.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel or channel.is_private

    async def _do_execute(self, cmd):
        if len(cmd.args) == 0:
            racer = self._cm.condordb.get_from_discord_id(cmd.author.id)
            if racer is None:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: Error: Couldn\'t find you in the database. Please register with `.register`.'.format(
                        cmd.author.mention))
                return
        elif len(cmd.args) == 1:
            racer = self._cm.condordb.get_from_rtmp_name(cmd.args[0])
            if racer is None:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: Error: Couldn\'t find RTMP name `{1}` in the database.'.format(
                        cmd.author.mention, cmd.args[0]))
                return
        else:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: Error: Too many arguments for `.stats`.'.format(
                    cmd.author.mention))
            return

        racer_stats = self._cm.condordb.get_racer_stats(racer)
        await self._cm.necrobot.client.send_message(cmd.channel, racer_stats.infobox)


class SetInfo(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'setinfo')
        self.help_text = 'Add additional information to be displayed on `.userinfo`. Usage is `.setinfo <text>`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.necrobot.main_channel or channel.is_private

    async def _do_execute(self, cmd):
        MAX_INFO_LEN = 255
        cut_length = len(cmd.command) + len(config.BOT_COMMAND_PREFIX) + 1
        info = cmd.message.content[cut_length:]

        if len(info) > MAX_INFO_LEN:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: Error: `.setinfo` is limited to {1} characters.'.format(cmd.author.mention, MAX_INFO_LEN))
            return

        if '\n' in info or '`' in info:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: Error: `.setinfo` cannot contain newlines or backticks.'.format(cmd.author.mention))
            return

        racer = self._cm.condordb.get_from_discord_id(cmd.author.id)
        if racer is None:
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0}: Error: couldn\'t find you in the database. Please register with `.register`.'.format(
                    cmd.author.mention))
            return

        self._cm.condordb.set_user_info(racer, info)
        await self._cm.necrobot.client.send_message(
            cmd.channel,
            '{0}: Updated your user info.'.format(cmd.author.mention))


class UserInfo(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'userinfo')
        self.help_text = 'Get stream and timezone info for the given user (or yourself, if no user provided). ' \
                         'Usage is `.userinfo <username>`.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return True

    async def _do_execute(self, cmd):
        # find the user's discord id
        if len(cmd.args) == 0:
            racer = self._cm.condordb.get_from_discord_id(cmd.author.id)
            if not racer:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    '{0}: You haven\'t registered; use `.register` to register.'.format(
                        cmd.author.mention))
        elif len(cmd.args) == 1:
            racer = self._cm.condordb.get_from_discord_name(cmd.args[0])
            if not racer:
                await self._cm.necrobot.client.send_message(
                    cmd.channel, '{0}: Error: User {1} isn\'t registered.'.format(
                        cmd.author.mention, cmd.args[0]))
        else:
            await self._cm.necrobot.client.send_message(
                cmd.channel, '{0}: Error: Too many arguments for `.userinfo`.'.format(cmd.author.mention))
            return

        if racer:
            await self._cm.necrobot.client.send_message(cmd.channel, racer.infobox)


class CloseAllRaceChannels(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'closeallracechannels')
        self.help_text = 'Closes _all_ private race channels.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        channel_ids = self._cm.condordb.get_all_race_channel_ids()
        channels_to_del = []
        for channel in self._cm.necrobot.server.channels:
            if int(channel.id) in channel_ids:
                channels_to_del.append(channel)

        for channel in channels_to_del:
            self._cm.condordb.delete_channel(channel.id)
            await self._cm.necrobot.client.delete_channel(channel)


class Remind(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'remind')
        self.help_text = 'Sends "@racer_1, @racer_2: Please remember to schedule your races!" to all racers in ' \
                         'unscheduled matches. `.remind` <text> instead sends "@racer_1, @racer_2: <text>".'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            if cmd.channel == self._cm.admin_channel:
                text = cmd.content if cmd.content else None
                await self._cm.remind_all(text, lambda m: not m.confirmed)
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Reminders sent.')


class ForceBeginMatch(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'forcebeginmatch')
        self.help_text = 'Force the match to begin now.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match wasn\'t found in the database.')
                return            
            else:
                match.schedule(datetime.datetime.utcnow(), None)
                for racer in match.racers:
                    match.confirm(racer)                
                self._cm.condordb.update_match(match)

                await self._cm.make_race_room(match)
                await self._cm.update_match_channel(match)
                await self._cm.update_schedule_channel()


class ForceConfirm(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'forceconfirm')
        self.help_text = 'Force all racers to confirm the suggested time. You should probably try `.forceupdate` first.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match wasn\'t found in the database.')
                return        

            if not match.scheduled:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: A scheduled time for this match has not been suggested. '
                    'One of the racers should use `.suggest` to suggest a time.')
                return           

            for racer in match.racers:
                match.confirm(racer)

            self._cm.condordb.update_match(match)
            await self._cm.necrobot.client.send_message(
                cmd.channel,
                '{0} has forced confirmation of match time: {1}.'.format(
                    cmd.author.mention, condortimestr.get_time_str(match.time)))

            if match.confirmed:
                await self._cm.condorsheet.schedule_match(match)
                
            await self._cm.update_match_channel(match)
            await self._cm.update_schedule_channel()


class ForceReboot(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'forcereboot')
        self.help_text = 'Reboots the race room.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match wasn\'t found in the database.')
                return            
            else:
                await self._cm.reboot_race_room(match)
                await self._cm.update_match_channel(match)


class ForceRescheduleUTC(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'forcerescheduleutc')
        self.help_text = 'Forces the race to be rescheduled for a specific UTC time. Usage same as `.suggest`, e.g., ' \
                         '`.forcereschedule February 18 2:30p`, except that the timezone is always taken to be UTC. ' \
                         'This command unschedules the match and `.suggests` a new time. Use `.forceconfirm` after ' \
                         'if you wish to automatically have the racers confirm this new time.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            if len(cmd.args) != 3:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: Couldn\'t parse your arguments as a date and time. '
                    'Model is, e.g., `.suggest March 9 5:30p`.')
                return
            else:
                match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
                if not match:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        'Error: This match wasn\'t found in the database. Please contact CoNDOR Staff.')
                    return          

                schedule_args = parse_schedule_args(cmd)
                if not schedule_args:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        'Error: Couldn\'t parse your arguments as a date and time. '
                        'Model is, e.g., `.suggest March 9 5:30p`.')
                    return
                elif schedule_args[0] is None:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        'Error: Couldn\'t parse {0} as the name of a month.'.format(cmd.args[0]))
                    return
                elif schedule_args[1] is None:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        'Error: Couldn\'t parse {0} as a day of the month.'.format(cmd.args[1]))
                    return
                elif schedule_args[2] is None or schedule_args[3] is None:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        'Error: Couldn\'t parse {0} as a time.'.format(cmd.args[2]))
                    return

                month = schedule_args[0]
                day = schedule_args[1]
                time_min = schedule_args[2]
                time_hr = schedule_args[3]            

                utc_dt = pytz.utc.localize(datetime.datetime(config.SEASON_YEAR, month, day, time_hr, time_min, 0))

                time_until = utc_dt - pytz.utc.localize(datetime.datetime.utcnow())
                if not time_until.total_seconds() > 0:
                    await self._cm.necrobot.client.send_message(
                        cmd.channel,
                        '{0}: Error: The time you are suggesting for the match appears to be in the past.'.format(
                            cmd.author.mention))
                    return                

                match.schedule(utc_dt, None)

                # update the db
                self._cm.condordb.update_match(match)

                # output what we did
                await self._cm.update_match_channel(match)
                racers = [match.racer_1, match.racer_2]
                for racer in racers:
                    member = self._cm.necrobot.find_member_with_id(racer.discord_id)
                    if member:
                        if racer.timezone:
                            r_tz = pytz.timezone(racer.timezone)
                            r_dt = r_tz.normalize(utc_dt.astimezone(pytz.utc))
                            await self._cm.necrobot.client.send_message(
                                cmd.channel,
                                '{0}: This match is suggested to be scheduled for {1}. '
                                'Please confirm with `.confirm`.'.format(
                                    member.mention, condortimestr.get_time_str(r_dt)))
                        else:
                            await self._cm.necrobot.client.send_message(
                                cmd.channel,
                                '{0}: A match time has been suggested; please confirm with `.confirm`. '
                                'I also suggest you register a timezone (use `.timezone`), so I can convert '
                                'to your local time.'.format(member.mention))  


class ForceUpdate(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'forceupdate')
        self.help_text = 'Updates the raceroom topic, gsheet, etc. for this race.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match wasn\'t found in the database.')
                return        

            if not match.scheduled:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: A scheduled time for this match has not been suggested. '
                    'One of the racers should use `.suggest` to suggest a time.')
                return

            if match.confirmed:
                await self._cm.condorsheet.schedule_match(match)

            if match.played:
                await self._cm.condorsheet.record_match(match)
                
            await self._cm.update_match_channel(match)
            await self._cm.update_schedule_channel()
            await self._cm.necrobot.client.send_message(cmd.channel, 'Updated.')


class ForceUnschedule(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'forceunschedule')
        self.help_text = 'Forces the match to be unscheduled.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return self._cm.condordb.is_registered_channel(channel.id)

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            match = self._cm.condordb.get_match_from_channel_id(cmd.channel.id)
            if not match:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Error: This match wasn\'t found in the database. Please contact CoNDOR Staff.')
                return

            for racer in match.racers:
                match.unconfirm(racer)

            self._cm.condordb.update_match(match)

            if match.confirmed:
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'Failed to unconfirm match.')
            else:
                await self._cm.condorsheet.unschedule_match(match)
                await self._cm.necrobot.client.send_message(
                    cmd.channel,
                    'The match has been unscheduled. Please `.suggest` a new time when one has been agreed upon.')

            await self._cm.update_match_channel(match)    


class ForceTransferAccount(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'forcetransferaccount')
        self.help_text = 'Transfers a user account from one Discord user to another. Usage is ' \
                         '`.forcetransferaccount @from @to`. These must be Discord mentions.'
        self._cm = condor_module

    def recognized_channel(self, channel): 
        return not channel.is_private

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            if len(cmd.args) != 2:
                await self._cm.client.send_message(
                    cmd.channel, 
                    '{0}: Error: Wrong number of args for `.forcetransferaccount`.'.format(cmd.author.mention))
                return

            from_id = clparse.get_id_from_discord_mention(cmd.args[0])
            to_id = clparse.get_id_from_discord_mention(cmd.args[1])
            if not from_id:
                await self._cm.client.send_message(
                    cmd.channel, 
                    '{0}: Error parsing first argument as a discord mention.'.format(cmd.author.mention))
                return
            if not to_id:
                await self._cm.client.send_message(
                    cmd.channel, 
                    '{0}: Error parsing second argument as a discord mention.'.format(cmd.author.mention))
                return                

            to_member = self._cm.necrobot.find_member_with_id(to_id)
            if not to_member:
                await self._cm.client.send_message(
                    cmd.channel, 
                    '{0}: Error finding member with id {1} on the server.'.format(cmd.author.mention, to_id))
                return  

            from_racer = self._cm.condordb.get_from_discord_id(from_id)
            if not from_racer:
                await self._cm.client.send_message(
                    cmd.channel, 
                    '{0}: Error finding member with id {1} in the database.'.format(cmd.author.mention, from_id))
                return

            self._cm.condordb.transfer_racer_to(from_racer.twitch_name, to_member)
            await self._cm.client.send_message(
                cmd.channel, 
                '{0}: Transfered racer account {1} to member {2}.'.format(
                    cmd.author.mention, from_racer.escaped_twitch_name, to_member.mention))


class TimezoneAlert(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'timezonealert')
        self.help_text = 'Sends an alert to all users with uncommon timezone registrations.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel.is_private

    async def _do_execute(self, cmd):
        if not self._cm.necrobot.is_admin(cmd.author):
            return

        racer_list = self._cm.condordb.get_all_racers()
        for racer in racer_list:
            if racer.timezone not in pytz.common_timezones:
                racer_member = self._cm.necrobot.find_member_with_id(racer.discord_id)
                if racer_member is not None:
                    timezone_page = 'https://github.com/incnone/condorbot/blob/master/data/tz_list.txt'
                    await self._cm.client.send_message(
                        racer_member,
                        'You are receiving this automated alert because your selected timezone, `{0}`, is no '
                        'longer registered in my timezone database. This probably means that '
                        'it does not properly account for your local Daylight Savings Time. \n\n'
                        'I suggest you re-register your timezone with `.timezone`. (This can be done via PM.) \n\n'
                        'See <{1}> for a list of supported timezones; your timezone should look like '
                        '`Continent/Nearby City`. \n\n'
                        'Sorry for the extra trouble!'.format(
                            racer.timezone,
                            timezone_page))

        await self._cm.client.send_message(
            cmd.channel,
            'Alerted users with out-of-date timezone info.')


class DropRacer(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'dropracer')
        self.help_text = 'Drop a racer from a specified week. Usage is `.dropracer <rtmp_name> -week <week_number>.'
        self._cm = condor_module

    def recognized_channel(self, channel):
        return channel == self._cm.admin_channel

    async def _do_execute(self, cmd):
        if self._cm.necrobot.is_admin(cmd.author):
            if len(cmd.args) != 3:
                await self._cm.client.send_message(
                    cmd.channel,
                    '{0}: Error: Wrong number of args for `.dropracer`.'.format(cmd.author.mention))
                return

            if cmd.args[1] != '-week':
                await self._cm.client.send_message(
                    cmd.channel,
                    '{0}: Error: Specify week to drop from with `-week`.'.format(cmd.author.mention))
                return

            rtmp_name = cmd.args[0]
            racer = self._cm.condordb.get_from_rtmp_name(rtmp_name)
            if racer is None:
                await self._cm.client.send_message(
                    cmd.channel,
                    '{0}: Error: Couldn\'t find racer with RTMP name {1}.'.format(cmd.author.mention, rtmp_name))
                return

            try:
                week = int(cmd.args[2])
                await self._cm.drop_racer_from_week(racer, week)
                await self._cm.client.send_message(
                    cmd.channel,
                    '{0}: Dropped racer `{1}` from week {2}.'.format(cmd.author.mention, rtmp_name, week))
            except ValueError:
                await self._cm.client.send_message(
                    cmd.channel,
                    '{0}: Error: Couldn\'t parse {1} as a week..'.format(cmd.author.mention, cmd.args[2]))
                return


class CondorModule(command.Module):
    def __init__(self, necrobot):
        command.Module.__init__(self, necrobot)
        self.condordb = CondorDB()
        self.condorsheet = CondorSheet(self.condordb)
        self.events = Events()
        self._racerooms = []
        self._alerted_channels = []
        self._channel_alert_futures = []
        self._schedule_channel_updater_future = None

        self.command_types = [command.DefaultHelp(self),
                              Cawmentate(self),
                              Uncawmentate(self),
                              Confirm(self),
                              CloseWeek(self),
                              Fastest(self),
                              MakeWeek(self),
                              NextRace(self),
                              Postpone(self),
                              Register(self),
                              RTMP(self),
                              SetInfo(self),
                              Staff(self),
                              Stats(self),
                              Stream(self),
                              Suggest(self),
                              Timezone(self),
                              Unconfirm(self),
                              UserInfo(self),
                              Vod(self),
                              Remind(self),
                              ForceBeginMatch(self),
                              ForceConfirm(self),
                              ForceReboot(self),
                              ForceRescheduleUTC(self),
                              ForceUnschedule(self),
                              ForceUpdate(self),
                              ForceTransferAccount(self),
                              UpdateGSheetSchedule(self),
                              TimezoneAlert(self),
                              DropRacer(self),
                              UpdateCawmentary(self)
                              ]

    async def initialize(self):
        await self.run_channel_alerts()
        await self.update_schedule_channel()
        self._schedule_channel_updater_future = asyncio.ensure_future(self.schedule_channel_auto_updater())

    async def close(self):
        for room in self._racerooms:
            await room.close()
        self._racerooms = []
        for alert_future in self._channel_alert_futures:
            alert_future.cancel()
        self._schedule_channel_updater_future.cancel()

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
    async def execute(self, cmd):
        for cmd_type in self.command_types:
            await cmd_type.execute(cmd)
        for room in self._racerooms:
            if cmd.channel == room.channel:
                await room.execute(cmd)

    @staticmethod
    def _log_warning(s):
        logging.getLogger('discord').warning(s)

    @staticmethod
    def get_match_channel_name(match):
        return match.channel_name

    async def make_match_channel(self, match):
        already_made_id = self.condordb.find_match_channel_id(match)
        while already_made_id is not None:
            for ch in self.necrobot.server.channels:
                if int(ch.id) == int(already_made_id):
                    return False

            self.condordb.delete_channel(already_made_id)
            already_made_id = self.condordb.find_match_channel_id(match)

        deny_read = discord.PermissionOverwrite(read_messages=False)
        permit_read = discord.PermissionOverwrite(read_messages=True)
        try:
            channel = await self.client.create_channel(
                self.necrobot.server,
                match.channel_name,
                discord.ChannelPermissions(target=self.necrobot.server.default_role, overwrite=deny_read))
        except discord.errors.HTTPException:
            self._log_warning('HTTPException while trying to create channel <{0}>.'.format(match.channel_name))
            raise

        channel_id = int(channel.id)

        if match.racer_1.discord_id:
            racer_1 = self.necrobot.find_member_with_id(match.racer_1.discord_id)
            if racer_1:
                await self.client.edit_channel_permissions(channel, racer_1, permit_read)

        if match.racer_2.discord_id:
            racer_2 = self.necrobot.find_member_with_id(match.racer_2.discord_id)
            if racer_2:
                await self.client.edit_channel_permissions(channel, racer_2, permit_read)

        for role in self.necrobot.admin_roles:
            await self.client.edit_channel_permissions(channel, role, permit_read)

        self._channel_alert_futures.append(asyncio.ensure_future(self.channel_alert(channel_id)))
        self.condordb.register_channel(match, channel_id)
        await self.update_match_channel(match)
        await self.send_channel_start_text(channel, match)
        return True

    async def save_and_delete(self, channel):
        messages = []
        async for message in self.client.logs_from(channel, 5000):
            messages.insert(0, message)

        outfile = codecs.open('logs/{0}.log'.format(channel.name), 'w', 'utf-8')
        for message in messages:
            try:
                outfile.write('{1} ({0}): {2}\n'.format(
                    message.timestamp.strftime("%m/%d %H:%M:%S"), message.author.name, message.clean_content))
            except UnicodeEncodeError:
                try:
                    outfile.write('{1} ({0}): {2}\n'.format(
                        message.timestamp.strftime("%m/%d %H:%M:%S"), message.author.name, message.content))
                except UnicodeEncodeError:
                    pass

        outfile.close()          

        self.condordb.delete_channel(channel.id)
        await self.client.delete_channel(channel)
            
    # makes a new "race room" in the match channel if not already made
    async def make_race_room(self, match):
        channel = self.necrobot.find_channel_with_id(self.condordb.find_match_channel_id(match))
        if channel:
            # if we already have a room for this channel, return
            for room in self._racerooms:
                if int(room.channel.id) == int(channel.id):
                    return  
            room = RaceRoom(self, match, channel)
            self._racerooms.append(room)
            asyncio.ensure_future(room.initialize())

    async def reboot_race_room(self, match):
        channel = self.necrobot.find_channel_with_id(self.condordb.find_match_channel_id(match))
        if channel:
            for room in self._racerooms:
                if int(room.channel.id) == int(channel.id):
                    await room.close()

            self._racerooms = [room for room in self._racerooms if int(room.channel.id) != int(channel.id)]
            self.make_race_room(match)

    # TODO: the important thing here is to actually get rid of all the Tasks the RaceRoom has made,
    # which means doing this properly requires keeping track of and cleaning up RaceRooms properly
    async def delete_race_room(self, match):
        pass

    async def update_match_channel(self, match):
        if match.confirmed and match.time_until_alert < datetime.timedelta(seconds=1):
            await self.make_race_room(match)
        else:
            channel = self.necrobot.find_channel_with_id(self.condordb.find_match_channel_id(match))
            if channel:
                # if we have a RaceRoom attached to this channel, remove it
                delete_raceroom_id = None
                for room in self._racerooms:
                    if int(room.channel.id) == int(channel.id):
                        delete_raceroom_id = int(channel.id)
                        await room.close()

                if delete_raceroom_id:
                    self._racerooms = [r for r in self._racerooms if not (int(r.channel.id) == delete_raceroom_id)]

                self._channel_alert_futures.append(asyncio.ensure_future(self.channel_alert(channel.id)))
                await self.necrobot.client.edit_channel(channel, topic=match.topic_str)

    async def channel_alert(self, channel_id):
        if channel_id in self._alerted_channels:
            return
        self._alerted_channels.append(channel_id)

        match = self.condordb.get_match_from_channel_id(channel_id)
        if match and match.confirmed:
            if match.time_until_alert.total_seconds() > 0:
                await asyncio.sleep(match.time_until_alert.total_seconds())
            await self.update_match_channel(self.condordb.get_match_from_channel_id(channel_id))

        self._alerted_channels = [c for c in self._alerted_channels if c != channel_id]

    async def run_channel_alerts(self):
        for channel_id in self.condordb.get_all_race_channel_ids():
            self._channel_alert_futures.append(asyncio.ensure_future(self.channel_alert(channel_id)))

    async def send_channel_start_text(self, channel, match):
        await self.necrobot.client.send_message(
            channel,
            '\n \N{BULLET} To suggest a time, enter a command like `.suggest February 20 10:00p`. Give the time in '
            'your own local timezone (which you\'ve registered using `.timezone`).\n'
            '\N{BULLET} Confirm a suggested time with `.confirm`. You may remove a confirmation with `.unconfirm`.\n'
            '\N{BULLET} To reschedule a time both racers have confirmed, both racers must call `.unconfirm`.\n'
            '\N{BULLET} You may alert CoNDOR staff at any time by calling `.staff`.')

        if match.racer_1 and match.racer_2 and match.racer_1.timezone and match.racer_2.timezone:
            r1tz = pytz.timezone(match.racer_1.timezone)
            r2tz = pytz.timezone(match.racer_2.timezone)

            utcnow = pytz.utc.localize(datetime.datetime.utcnow())
            r1off = utcnow.astimezone(r1tz).utcoffset()
            r2off = utcnow.astimezone(r2tz).utcoffset()

            if r1off > r2off:
                ahead_racer_name = match.racer_1.escaped_unique_name
                behind_racer_name = match.racer_2.escaped_unique_name
                diff = r1off - r2off
            elif r1off < r2off:
                ahead_racer_name = match.racer_2.escaped_unique_name
                behind_racer_name = match.racer_1.escaped_unique_name
                diff = r2off - r1off
            else:
                await self.necrobot.client.send_message(
                    channel,
                    'The two racers in this match currently have the same UTC offset.')
                return

            diff_hr = int(diff.total_seconds() // 3600)
            diff_min = int(diff.total_seconds() // 60 - diff_hr*60)

            if diff_hr == 0:
                diff_str = ''
            elif diff_hr == 1:
                diff_str = '1 hour'
            else:
                diff_str = '{} hours'.format(diff_hr)

            if diff_min != 0:
                diff_str += '{} minutes'.format(diff_min)

            tzwebsite = '<http://www.spice-3d.org/time?date={0}&tz1={1}&tz2={2}>'.format(
                utcnow.strftime('%Y-%m-%d'),
                match.racer_1.timezone.replace('/', '%2F'),
                match.racer_2.timezone.replace('/', '%2F'))

            if diff_str:
                await self.necrobot.client.send_message(
                    channel,
                    '{0} is currently {1} ahead of {2}. For a full conversion table, see {3}.'.format(
                        ahead_racer_name, diff_str, behind_racer_name, tzwebsite))

    async def schedule_channel_auto_updater(self):
        while True:
            utcnow = pytz.utc.localize(datetime.datetime.utcnow())
            first_next_try = utcnow.replace(minute=0, second=0, microsecond=0) + datetime.timedelta(minutes=45)
            time_until = first_next_try - utcnow
            if time_until <= datetime.timedelta(seconds=0):
                time_until += datetime.timedelta(minutes=30)

            await asyncio.sleep(time_until.total_seconds())
            await self.update_schedule_channel()
            await asyncio.sleep(60)

    async def get_nextrace_displaytext(self, match_list):
        utcnow = pytz.utc.localize(datetime.datetime.utcnow())
        if len(match_list) > 1:
            display_text = 'Upcoming matches: \n'
        else:
            display_text = 'Next match: \n'

        for match in match_list:
            display_text += '\N{BULLET} **{0}** - **{1}**'.format(
                match.racer_1.unique_name,
                match.racer_2.unique_name)
            if match.league != CondorLeague.NONE:
                display_text += ' ({0})'.format(match.league)
            display_text += ': {0} \n'.format(condortimestr.timedelta_to_string(match.time - utcnow, punctuate=True))
            match_cawmentator = self.condordb.get_cawmentator(match)
            if match_cawmentator:
                display_text += '    Cawmentary: <http://www.twitch.tv/{0}> \n'.format(match_cawmentator.twitch_name)
            else:
                display_text += '    Cawmentary: None registered yet. \n'
        return display_text

    @staticmethod
    def get_matches_infobox(match_list):
        utcnow = pytz.utc.localize(datetime.datetime.utcnow())

        max_r1_len = 0
        max_r2_len = 0
        for match in match_list:
            max_r1_len = max(max_r1_len, len(match.racer_1.unique_name))
            max_r2_len = max(max_r2_len, len(match.racer_2.unique_name))

        schedule_text = '``` \nUpcoming matches: \n'
        for match in match_list:
            schedule_text += '{r1:>{w1}} v {r2:<{w2}} : '.format(
                r1=match.racer_1.unique_name, w1=max_r1_len, r2=match.racer_2.unique_name, w2=max_r2_len)
            if match.time - utcnow < datetime.timedelta(minutes=0):
                schedule_text += 'Right now!'
            else:
                schedule_text += condortimestr.get_24h_time_str(match.time)
            schedule_text += '\n'
        schedule_text += '```'
        return schedule_text

    def get_upcoming_and_current_matches(self, utcnow):
        upcoming_matches = self.condordb.get_upcoming_matches(utcnow)
        to_remove = []
        for room in self._racerooms:
            if room.before_races:
                continue

            already_have_match = False
            for match in upcoming_matches:
                if room.match == match:
                    already_have_match = True

            played_all = room.played_all_races

            if not already_have_match and not played_all:
                upcoming_matches.append(room.match)
            elif already_have_match and played_all:
                to_remove.append(room.match)

        upcoming_matches = [m for m in upcoming_matches if m not in to_remove]
        return sorted(upcoming_matches, key=lambda m: m.time)

    async def update_schedule_channel(self):
        utcnow = pytz.utc.localize(datetime.datetime.utcnow())
        upcoming_matches = self.get_upcoming_and_current_matches(utcnow)
        upcoming_matches = upcoming_matches[:20]
        schedule_text = self.get_matches_infobox(upcoming_matches)

        async for msg in self.necrobot.client.logs_from(self.necrobot.schedule_channel):
            if (msg.author.name == 'condorbot' or msg.author.name == 'condorbot_alpha') \
                    and msg.content.startswith('```'):  # hack for now
                await self.necrobot.client.edit_message(msg, schedule_text)
                return

        await self.necrobot.client.send_message(self.necrobot.schedule_channel, schedule_text)

    async def send_cawmentator_alert(self, match):
        cawmentator = self.condordb.get_cawmentator(match)
        if cawmentator is None:
            return

        minutes_until_match = int((match.time_until_match.total_seconds() + 30) // 60)
        alert_text = 'Reminder: You\'re scheduled to cawmentate **{0}** - **{1}** '.format(
            match.racer_1.escaped_unique_name,
            match.racer_2.escaped_unique_name)
        if match.league != CondorLeague.NONE:
            alert_text += '({0}) '.format(match.league)
        alert_text += ', which is scheduled to begin in {0} minutes. '.format(minutes_until_match)
        racer_1_stats = self.condordb.get_racer_stats(match.racer_1)
        racer_2_stats = self.condordb.get_racer_stats(match.racer_2)
        if racer_1_stats:
            alert_text += racer_1_stats.big_infobox + '\n'
        if racer_2_stats:
            alert_text += racer_2_stats.big_infobox + '\n'
        await self.necrobot.client.send_message(self.necrobot.find_member_with_id(cawmentator.discord_id), alert_text)

    async def post_match_alert(self, match):
        cawmentator = self.condordb.get_cawmentator(match)
        minutes_until_match = int((match.time_until_match.total_seconds() + 30) // 60)
        alert_text = 'The match **{0}** - **{1}** '.format(
            match.racer_1.escaped_unique_name,
            match.racer_2.escaped_unique_name)
        if match.league != CondorLeague.NONE:
            alert_text += '({0}) '.format(match.league)
        alert_text += 'is scheduled to begin in {0} minutes.\n'.format(minutes_until_match)
        if cawmentator:
            alert_text += 'Cawmentary: <http://www.twitch.tv/{0}> \n'.format(cawmentator.twitch_name)
        alert_text += 'RTMP: <http://rtmp.condorleague.tv/#{0}/{1}> \n'.format(
            match.racer_1.rtmp_name.lower(), match.racer_2.rtmp_name.lower())
        await self.necrobot.client.send_message(self.necrobot.main_channel, alert_text)

        # Send race soon event
        self.events.racesoon(match.racer_1.rtmp_name, match.racer_2.rtmp_name)

    async def post_match_results(self, match):
        score = self.condordb.get_score(match)
        await self.necrobot.client.send_message(
            self.necrobot.main_channel,
            'Match completed: **{0}** [{1} - {2}] **{3}**.'.format(
                match.racer_1.escaped_unique_name,
                score[0],
                score[1],
                match.racer_2.escaped_unique_name))
        await self.condorsheet.record_match(match, score)

    async def remind_all(self, text=None, condition=lambda m: True):
        match_list = self.condordb.get_all_matches()
        for match in match_list:
            showcase = await self.condorsheet.is_showcase_match(match)
            if condition(match) and not showcase:
                await self._remind_match(match, text)
            
    async def _remind_match(self, match, text=None):
        channel_id = self.condordb.get_channel_id_from_match(match)
        if not channel_id:
            print('Error: match {0} not found in database.'.format(match.channel_name))
            return            
        else:
            channel = self.necrobot.find_channel_with_id(channel_id)
            if not channel:
                print('Error: Channel not found for match {0}, which has a registered channel id.'.format(
                    match.channel_name))
                return
            
            mention_str = ''
            for racer in match.racers:
                racer_member = self.necrobot.find_member_with_id(racer.discord_id)
                if racer_member:
                    mention_str += racer_member.mention + ', '                      

            if mention_str:
                mention_str = mention_str[:-2]
            else:
                print('Error: couldn\'t find discord user accounts for the racers in match {0}.'.format(
                    match.channel_name))
                return

            if text:
                await self.necrobot.client.send_message(
                    channel,
                    '{0}: {1}'.format(mention_str, text))
            else:
                await self.necrobot.client.send_message(
                    channel,
                    '{0}: Please remember to schedule your races!'.format(mention_str))

    async def drop_racer_from_week(self, racer, week):
        for channel_id in self.condordb.get_all_channel_ids_with_racer(racer):
            channel = self.necrobot.find_channel_with_id(channel_id)
            if channel is not None:
                await self.necrobot.client.delete_channel(channel)
            else:
                self._log_warning('Couldn\'t find channel with id <{0}>.'.format(channel_id))

        self.condordb.drop_racer_from_week(racer, week)
