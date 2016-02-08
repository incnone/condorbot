import asyncio
import datetime
import discord

import command
import config
from condordb import CondorDB
from condorsheet import CondorSheet
from condorsheet import CondorMatch

class MakeWeek(command.CommandType):
    def __init__(self, condor_module):
        command.CommandType.__init__(self, 'makeweek')
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
            print('Error in stream: wrong command arg length.')
        else:
            twitch_name = command.args[0]
            self._cm.condordb.register_user(command.author, twitch_name)

class CondorModule(command.Module):
    def __init__(self, necrobot, db_connection):
        command.Module.__init__(self, necrobot)
        self.condordb = CondorDB(db_connection)
        self.condorsheet = CondorSheet(self.condordb)

        self.command_types = [command.DefaultHelp(self),
                              MakeWeek(self),
                              Stream(self)]

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
        
