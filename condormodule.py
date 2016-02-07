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

        sheet_name = command.args[0]
        matches = self._cm.condorsheet.get_matches(sheet_name)
        if matches:
            

class CondorModule(command.Module):
    def __init__(self, necrobot, db_connection):
        command.Module.__init__(self, necrobot)
        self.condordb = CondorDB(db_connection)
        self.condorsheet = CondorSheet(self.condordb)

        self.command_types = [command.DefaultHelp(self),
                              MakeWeek(self)]

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
        channel_id = self.condordb.get_open_match_channel_id()
        channel = None

        if channel_id:
            for ch in self.necrobot.server.channels:
                if int(ch.id) == int(channel_id):
                    channel = ch
            if not channel:
                print('Error: couldn\'t find a registered channel.')
                channel_id = 0
        
        # if there was no open channel, make one
        if not channel_id:
            channel = yield from self.client.create_channel(self.necrobot.server, self.get_match_channel_name(match))
            channel_id = channel.id
        # otherwise, change the name of the channel we got
        else:
            yield from self.client.edit_channel(channel, name=self.get_match_channel_name(match))

        
