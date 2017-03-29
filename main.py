import asyncio
import discord
import logging

import command
import config
import datetime
import os
import seedgen
import sys

from necrobot import Necrobot
from vodrecord import VodRecorder


class LoginData(object):
    token = ''
    admin_id = None
    server_id = None

config.init('data/bot_config.txt')


# Prepend timestamps to stdout and stderr
class StampedOutput(object):
    def __init__(self, out_str):
        self._out_str = out_str
        self._logger = logging.getLogger('discord')
        self._warning_level = out_str == sys.stderr

    new_line = True

    def _do_logging(self, s):
        self._logger.warning(s)
        # if self._warning_level:
        #     self._logger.warning(s)
        # else:
        #     self._logger.info(s)

    def flush(self):
        self._out_str.flush()

    def write(self, s):
        if s == '\n':
            self._out_str.write(s)
            self.new_line = True
        elif self.new_line:
            self._out_str.write(s)
            self._do_logging('[{0}]: {1}'.format(datetime.datetime.utcnow().strftime("%H-%M-%S"), s))
            self.new_line = False
        else:
            self._out_str.write(s)
            self._do_logging(s)


sys.stdout = StampedOutput(sys.stdout)
sys.stderr = StampedOutput(sys.stderr)

# -Logging-------------------------------
LOG_LEVEL = logging.WARNING

file_format_str = '%b%d'
utc_today = datetime.datetime.utcnow().date()
utc_yesterday = utc_today - datetime.timedelta(days=1)
utc_today_str = utc_today.strftime(file_format_str)
utc_yesterday_str = utc_yesterday.strftime(file_format_str)

filenames_in_dir = os.listdir('logging')

# get log output filename
filename_rider = 0
log_output_filename = ''
while True:
    filename_rider += 1
    log_output_filename = '{0}-{1}.log'.format(utc_today_str, filename_rider)
    if not (log_output_filename in filenames_in_dir):
        break

log_output_filename = 'logging/{0}'.format(log_output_filename)

# set up logger
logger = logging.getLogger('discord')
logger.setLevel(LOG_LEVEL)
handler = logging.FileHandler(filename=log_output_filename, encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
# --------------------------------------

# General init----------------------------------------------------
client = discord.Client()                                                       # the client for discord
necrobot = Necrobot(client)
seedgen.init_seed()

# Get login data from file----------------------------------------
login_data = LoginData()                                                        # data to be read from the login file
login_info = open('data/login_info.txt', 'r')
login_data.token = login_info.readline().rstrip('\n')
login_data.admin_id = login_info.readline().rstrip('\n')
login_data.server_id = login_info.readline().rstrip('\n')
login_info.close()


# Define client events
@client.event
async def on_ready():
    await necrobot.post_login_init(login_data.server_id, login_data.admin_id)


@client.event
async def on_message(message):
    cmd = command.Command(message)
    await necrobot.execute(cmd)


@client.event
async def on_member_join(member):
    await necrobot.on_member_join(member)

# Run client-------------------------------------------------------
loop = asyncio.get_event_loop()
try:
    loop.run_until_complete(client.login(login_data.token))
    loop.run_until_complete(client.connect())
except Exception as e:
    print('Exception: {}'.format(e))
    loop.run_until_complete(client.close())
finally:
    # for task in asyncio.Task.all_tasks(loop):
    #     task.print_stack()
    loop.close()
    VodRecorder().end_all()
