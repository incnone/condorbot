# Represents a user-entered command

import config
import logging
import shlex


# Represents a full user command input (e.g. `.make -c Cadence -seed 12345 -custom 4-shrine`)
class Command(object):
    def __init__(self, message):   
        self.command = None
        self.args = []      
        self.message = None

        if message.content.startswith(config.BOT_COMMAND_PREFIX):
            try:
                self.args = shlex.split(message.content)
            except ValueError:
                self.args = message.content.split()
            prefix_len = len(config.BOT_COMMAND_PREFIX)
            self.command = (self.args.pop(0)[prefix_len:]).lower()
            self.message = message

    @property
    def author(self):
        return self.message.author if self.message else None

    @property
    def server(self):
        return self.message.server if self.message else None

    @property
    def channel(self):
        return self.message.channel if self.message else None

    @property
    def is_private(self):
        return self.message.channel.is_private if self.message else None

    @property
    def content(self):
        cmd_len = len(config.BOT_COMMAND_PREFIX) + len(self.command) + 1
        return self.message.content[cmd_len:]


# Abstract base class; a particular command that the bot can interpret, and how to interpret it
# (For instance, racemodule has a CommandType object called make, for the `.make` command.)
class CommandType(object):
    def __init__(self, *args):
        self.command_name_list = args             # the string that calls this command (e.g. 'make')
        self.help_text = 'This command has no help text.'
        self.suppress_help = False              # If true, will not show this command on .help requests
        
    @property
    def mention(self):
        return config.BOT_COMMAND_PREFIX + self.command_name_list[0]

    # Returns True if the name can be used to call this command
    def called_by(self, name):
        return name in self.command_name_list

    # Returns true if the command is "recognized" in the given channel
    def recognized_channel(self, channel):
        return True

    # If the Command object's command is this object's command, calls the (virtual) method _do_execute on it
    async def execute(self, command):
        if command.command in self.command_name_list and self.recognized_channel(command.channel):
            await self._do_execute(command)

    # Overwrite this to determine what this CommandType should do with a given Command
    async def _do_execute(self, command):
        logging.getLogger('discord').warning('Error: called CommandType._do_execute in the abstract base class.')
        pass


class DefaultHelp(CommandType):
    def __init__(self, module):
        CommandType.__init__(self, 'help')
        self.help_text = 'Help.'
        self.suppress_help = True
        self.module = module

    async def _do_execute(self, command):
        if len(command.args) == 0:
            command_list_text = self.module.infostr + ": "
            found_any = False
            for cmd_type in self.module.command_types:
                if not cmd_type.suppress_help and cmd_type.recognized_channel(command.channel):
                    found_any = True
                    command_list_text += '`' + cmd_type.mention + '`, '
            if found_any:
                command_list_text = command_list_text[:-2]
                await self.module.client.send_message(command.channel, command_list_text)
            await self.module.client.send_message(
                command.channel,
                'Documentation at <https://github.com/incnone/condorbot/blob/master/documentation.md> .')
        elif len(command.args) == 1:
            for cmd_type in self.module.command_types:
                if cmd_type.called_by(command.args[0]) and cmd_type.recognized_channel(command.channel):
                    await self.module.client.send_message(
                        command.channel,
                        '`{0}`: {1}'.format(cmd_type.mention, cmd_type.help_text))
            return None


# Abstract base class; a module that can be attached to the Necrobot
class Module(object):
    def __init__(self, necrobot):
        self.necrobot = necrobot
        self.command_types = []

    async def initialize(self):
        pass

    async def close(self):
        pass

    @property
    def client(self):
        return self.necrobot.client

    @property
    def server(self):
        return self.necrobot.server

    # Brief information string on what kind of module this is.
    # Overwrite this
    @property
    def infostr(self):
        return 'Unknown module'   

    # Attempts to execute the given command (if a command of its type is in command_types)
    async def execute(self, command):
        for cmd_type in self.command_types:
            await cmd_type.execute(command)

    # Called when a user updates their preferences with the given UserPrefs
    # Base method does nothing; override for functionality
    async def on_update_prefs(self, prefs, member):
        pass
