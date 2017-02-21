import asyncio
import discord
import logging

import command
import config
import datetime
import os
import seedgen

from necrobot import Necrobot
from condormodule import CondorModule

class LoginData(object):
    token = ''
    admin_id = None
    server_id = None

##-Logging-------------------------------
LOG_LEVEL = logging.WARNING

file_format_str = '%b%d'
utc_today = datetime.datetime.utcnow().date()
utc_yesterday = utc_today - datetime.timedelta(days=1)
utc_today_str = utc_today.strftime(file_format_str)
utc_yesterday_str = utc_yesterday.strftime(file_format_str)

filenames_in_dir = os.listdir('logging')

## get log output filename
filename_rider = 0
while True:
    filename_rider += 1
    log_output_filename = '{0}-{1}.log'.format(utc_today_str, filename_rider)
    if not (log_output_filename in filenames_in_dir):
        break
log_output_filename = 'logging/{0}'.format(log_output_filename)

## set up logger
logger = logging.getLogger('discord')
logger.setLevel(LOG_LEVEL)
handler = logging.FileHandler(filename=log_output_filename, encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)
##--------------------------------------

#-General init----------------------------------------------------
config.init('data/bot_config.txt')
client = discord.Client()                                                       # the client for discord
necrobot = Necrobot(client)
seedgen.init_seed()

#-Get login data from file----------------------------------------
login_data = LoginData()                                                        # data to be read from the login file
login_info = open('data/login_info.txt', 'r')
login_data.token = login_info.readline().rstrip('\n')
login_data.admin_id = login_info.readline().rstrip('\n')
login_data.server_id = login_info.readline().rstrip('\n')
login_info.close()
     
# Define client events
@client.event
@asyncio.coroutine
def on_ready():
    print('-Logged in---------------')
    print('User name: {0}'.format(client.user.name))
    print('User id  : {0}'.format(client.user.id))
    print('-------------------------')
    print(' ')
    necrobot.post_login_init(login_data.server_id, login_data.admin_id)

    necrobot.load_module(CondorModule(necrobot))

    yield from necrobot.init_modules()

    print('...done.')

@client.event
@asyncio.coroutine
def on_message(message):
    cmd = command.Command(message)
    yield from necrobot.execute(cmd)

@client.event
@asyncio.coroutine
def on_member_join(member):
    yield from necrobot.on_member_join(member)

#-Run client-------------------------------------------------------
try:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(client.login(login_data.token))
    loop.run_until_complete(client.connect())
except Exception as e:
    print('Exception: {}'.format(e))
    loop.run_until_complete(client.close())
finally:
    loop.close()

