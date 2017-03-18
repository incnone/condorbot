import command
import config


class Die(command.CommandType):
    def __init__(self, admin_module):
        command.CommandType.__init__(self, 'die')
        self.help_text = ''
        self.suppress_help = True
        self._am = admin_module

    async def _do_execute(self, cmd):
        if self._am.necrobot.is_admin(cmd.author):
            await self._am.necrobot.logout()

    def recognized_channel(self, channel):
        return channel.is_private or channel == self._am.necrobot.main_channel


class Info(command.CommandType):
    def __init__(self, admin_module):
        command.CommandType.__init__(self, 'info')
        self.help_text = "Necrobot version information."
        self._am = admin_module

    async def _do_execute(self, cmd):
        await self._am.client.send_message(cmd.channel, 'Condorbot v-{0} (alpha).'.format(config.BOT_VERSION))

    def recognized_channel(self, channel):
        return channel.is_private or channel == self._am.necrobot.main_channel


class RebootEverything(command.CommandType):
    def __init__(self, admin_module):
        command.CommandType.__init__(self, 'rebooteverything')
        self.help_text = "Reset all internal data. WARNING: Bot will lose track of all ongoing races!"
        self._am = admin_module

    async def _do_execute(self, cmd):
        if self._am.necrobot.is_admin(cmd.author):
            await self._am.necrobot.client.send_message(
                cmd.channel,
                'Rebooting all internal data...')
            await self._am.necrobot.reboot_modules()
            await self._am.necrobot.client.send_message(
                cmd.channel,
                'Done.')

    def recognized_channel(self, channel):
        return channel.is_private or channel == self._am.necrobot.admin_channel


class ThrowException(command.CommandType):
    def __init__(self, admin_module):
        command.CommandType.__init__(self, 'throwexception')
        self.help_text = "Throw an exception. (Testing purposes.)"
        self._am = admin_module

    async def _do_execute(self, cmd):
        if self._am.necrobot.is_admin(cmd.author):
            raise RuntimeError('Thrown by ThrowException.')

    def recognized_channel(self, channel):
        return channel.is_private or channel == self._am.necrobot.main_channel


class AdminModule(command.Module):
    def __init__(self, necrobot):
        command.Module.__init__(self, necrobot)
        self.command_types = [Die(self),
                              RebootEverything(self),
                              ThrowException(self),
                              Info(self)]

    @property
    def infostr(self):
        return 'Admin commands'
