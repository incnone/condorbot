def init(config_filename):
    global BOT_COMMAND_PREFIX
    global BOT_VERSION

    #admin
    global ADMIN_ROLE_NAMES                     #list of names of roles to give admin access

    #channels
    global MAIN_CHANNEL_NAME
    global ADMIN_CHANNEL_NAME

    #race
    global COUNTDOWN_LENGTH                        #number of seconds between the final .ready and race start
    global INCREMENTAL_COUNTDOWN_START             #number of seconds at which to start counting down each second in chat
    global FINALIZE_TIME_SEC                       #seconds after race end to finalize+record race
    global CLEANUP_TIME_SEC                        #minutes of no chatting until the room may be cleaned (only applies if race has been finalized)
    global NO_ENTRANTS_CLEANUP_SEC                 #room is cleaned if there are no race entrants for this duration of time
    global NO_ENTRANTS_CLEANUP_WARNING_SEC         #give a warning re: cleaning race room if no entrants for this duration of time
    global REQUIRE_AT_LEAST_TWO_FOR_RACE           #if True, then races with only one entrant cannot be started
    global RACE_POKE_DELAY                         #number of seconds to wait between allowing pokes 

    #database
    global DB_FILENAME

    #gsheets
    global GSHEET_CREDENTIALS_FILENAME
    global GSHEET_DOC_NAME
    
    defaults = {
        'bot_command_prefix':'.',
        'bot_version':'0.1.0',
        'channel_main':'season4',
        'channel_admin':'adminchat',
        'channel_schedule':'schedule',
        'race_countdown_time_seconds':'10',
        'race_begin_counting_down_at':'5',
        'race_record_after_seconds':'30',
        'race_cleanup_after_room_is_silent_for_seconds':'180',
        'race_cleanup_after_no_entrants_for_seconds':'120',
        'race_give_cleanup_warning_after_no_entrants_for_seconds':'90', 
        'race_require_at_least_two':'0',
        'race_poke_delay':'10',
        'db_filename':'data/necrobot.db',
        'gsheet_credentials_filename':'data/gsheet_credentials.json',
        'gsheet_doc_name':'CoNDOR Season 4',
        }

    admin_roles = []
            
    file = open(config_filename, 'r')
    if file:
        for line in file:
            args = line.split('=')
            if len(args) == 2:
                if args[0] in defaults:
                    defaults[args[0]] = args[1].rstrip('\n')
                elif args[0] == 'admin_roles':
                    arglist = args[1].rstrip('\n').split(',')
                    for arg in arglist:
                        admin_roles.append(arg)
                else:
                    print("Error in {0}: variable {1} isn't recognized.".format(config_filename, args[0]))

    BOT_COMMAND_PREFIX = defaults['bot_command_prefix']
    BOT_VERSION = defaults['bot_version']
    MAIN_CHANNEL_NAME = defaults['channel_main']
    ADMIN_CHANNEL_NAME = defaults['channel_admin']
    SCHEDULE_CHANNEL_NAME = defaults['channel_schedule']

    ADMIN_ROLE_NAMES = admin_roles

    COUNTDOWN_LENGTH = int(defaults['race_countdown_time_seconds'])
    INCREMENTAL_COUNTDOWN_START = int(defaults['race_begin_counting_down_at'])
    FINALIZE_TIME_SEC = int(defaults['race_record_after_seconds'])
    CLEANUP_TIME_SEC = int(defaults['race_cleanup_after_room_is_silent_for_seconds'])
    NO_ENTRANTS_CLEANUP_SEC = int(defaults['race_cleanup_after_no_entrants_for_seconds'])
    NO_ENTRANTS_CLEANUP_WARNING_SEC = int(defaults['race_give_cleanup_warning_after_no_entrants_for_seconds'])
    REQUIRE_AT_LEAST_TWO_FOR_RACE = bool(int(defaults['race_require_at_least_two']))
    RACE_POKE_DELAY = int(defaults['race_poke_delay'])

    DB_FILENAME = defaults['db_filename']
    GSHEET_CREDENTIALS_FILENAME = defaults['gsheet_credentials_filename']
    GSHEET_DOC_NAME = defaults['gsheet_doc_name']
