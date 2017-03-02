import asyncio
import textwrap

import config

from adminmodule import AdminModule


class Necrobot(object):

    # Barebones constructor
    def __init__(self, client):
        self.client = client
        self.server = None
        self.prefs = None
        self.modules = []
        self.admin_id = None
        self._main_channel = None
        self._notifications_channel = None
        self._schedule_channel = None
        self._wants_to_quit = False

    # Initializes object; call after client has been logged in to discord
    def post_login_init(self, server_id, admin_id=0):
        for module in self.modules:
            module.close()

        self.server = None
        self.prefs = None
        self.modules.clear()
        self._main_channel = None
        self._notifications_channel = None
        self._schedule_channel = None
        self._wants_to_quit = False

        self.admin_id = admin_id if admin_id else None
       
        # set up server
        try:
            int(server_id)
            id_is_int = True
        except ValueError:
            id_is_int = False
            
        if self.client.servers:
            for s in self.client.servers:
                if id_is_int and s.id == server_id:
                    print("Server id: {}".format(s.id))
                    self.server = s
                elif s.name == server_id:
                    print("Server id: {}".format(s.id))
                    self.server = s
        else:
            print('Error: Could not find the server.')
            exit(1)

        self._main_channel = self.find_channel(config.MAIN_CHANNEL_NAME)
        self._notifications_channel = self.find_channel(config.NOTIFICATIONS_CHANNEL_NAME)
        self._schedule_channel = self.find_channel(config.SCHEDULE_CHANNEL_NAME)
        self.load_module(AdminModule(self))

    async def init_modules(self):
        for module in self.modules:
            await module.initialize()

    # Causes the Necrobot to use the given module
    # Doesn't check for duplicates
    def load_module(self, module):
        self.modules.append(module)

    # True if the bot wants to quit (and not re-login)
    @property
    def quitting(self):
        return self._wants_to_quit

    # Return the #necrobot_main channel
    @property
    def main_channel(self):
        return self._main_channel

    # Return the #bot_notifications channel
    @property
    def notifications_channel(self):
        return self._notifications_channel
    
    # Return the #schedule channel
    @property
    def schedule_channel(self):
        return self._schedule_channel

    # Return a list of condor staff
    @property
    def condor_staff(self):
        ret_str = ''
        for member in self.server.members:
            for role in member.roles:
                if role.name == 'CoNDOR Staff':
                    ret_str += member.mention + ' '
        if ret_str:
            return ret_str[:-1]
        else:
            return ''
    
    # Get a list of all admin roles on the server
    @property
    def admin_roles(self):
        admin_roles = []
        for rolename in config.ADMIN_ROLE_NAMES:
            for role in self.server.roles:
                if role.name == rolename:
                    admin_roles.append(role)
        return admin_roles

    # Returns true if the user is a server admin
    def is_admin(self, user):
        member = self.get_as_member(user)
        admin_roles = self.admin_roles
        for role in member.roles:
            if role in admin_roles:
                return True
        return False

    # Returns the channel with the given name on the server, if any
    def find_channel(self, channel_name):
        for channel in self.server.channels:
            if channel.name == channel_name:
                return channel
        return None

    def find_channel_with_id(self, channel_id):
        for channel in self.server.channels:
            if int(channel.id) == int(channel_id):
                return channel
        return None        

    # Returns a list of all members with a given username (capitalization ignored)
    def find_members(self, username):
        to_return = []
        for member in self.server.members:
            if member.name == username:
                to_return.append(member)
        return to_return

    def find_member_with_id(self, member_id):
        for member in self.server.members:
            if int(member.id) == member_id:
                return member
        return None

    # Log out of discord
    async def logout(self):
        self._wants_to_quit = True
        await self.client.logout()

    # Reboot our login to discord (log out, but do not set quitting = true)
    async def reboot(self):
        self._wants_to_quit = False
        await self.client.logout()

    async def execute(self, cmd):
        # don't care about bad commands
        if cmd.command is None:
            return
        
        # don't reply to self
        if cmd.author == self.client.user:
            return

        # only reply on-server or to PM
        if not cmd.is_private and cmd.server != self.server:
            return

        # let each module attempt to handle the command in turn
        for module in self.modules:
            asyncio.ensure_future(module.execute(cmd))

    # Send a DM when someone joins
    async def on_member_join(self, member):
        await self.client.send_message(member, textwrap.dedent("""
            Welcome to the CoNDOR Season 5 server! Please register a stream and timezone with the bot. Example:
            ```
            .stream eladdifficult
            .timezone America/Toronto
            ```
            See https://en.wikipedia.org/wiki/List_of_tz_database_time_zones for a list of timezones.
            (Please prefer to choose timezones like "America/Toronto" to timezones like "EDT"; the former should be
             better at taking local daylight-savings rules into account.)"""))

    # Returns the given Discord User as a Member of the server
    def get_as_member(self, user):
        for member in self.server.members:
            if member.id == user.id:
                return member
