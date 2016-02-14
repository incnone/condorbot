# Class representing a channel in which a race (or several races) will occur.
# The list of all race rooms is managed by CondorModule.

import asyncio
import command
import config
import datetime
import discord
import level
import racetime
import textwrap
import time

from condormatch import CondorMatch
from race import Race
from racer import Racer

SUFFIXES = {1: 'st', 2: 'nd', 3: 'rd'}
def ordinal(num):
    if 10 <= num % 100 <= 20:
        suffix = 'th'
    else:
        suffix = SUFFIXES.get(num % 10, 'th')
    return str(num) + suffix

class Enter(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'enter', 'join')
        self.help_text = 'Enters (registers for) the match. When it\'s time for the race, use `.ready` to indicate you are ready to begin. You may use `.join` instead of `.enter` if preferred.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.before_races:
            return
        
        yield from self._room.enter_racer(command.author)

class Ready(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'ready')
        self.help_text = 'Indicates that you are ready to begin the race. The race begins when all entrants are ready.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.race or not self._room.race.is_before_race:
            return
        
        racer = self._room.race.get_racer(command.author)
        if racer:
            success = yield from self._room.race.ready_racer(racer)    #success is True if the racer was unready and now is ready
            if success:
                if len(self._room.race.racers) == 1 and config.REQUIRE_AT_LEAST_TWO_FOR_RACE:
                    yield from self._room.write('Waiting on at least one other person to join the race.')
                else:
                    yield from self._room.write('{0} is ready! {1} remaining.'.format(command.author.mention, self._room.race.num_not_ready))

                yield from self._room.begin_if_ready()

            elif racer.is_ready:
                yield from self._room.write('{0} is already ready!'.format(command.author.mention))
        else:
            yield from self._room.write('{}: Please `.enter` the race before readying.'.format(command.author.mention))
                    
class Unready(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'unready')
        self.help_text = 'Undoes `.ready`.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.race or not self._room.race.is_before_race:
            return
        
        racer = self._room.race.get_racer(command.author)
        if racer:
            success = yield from self._room.race.unready_racer(racer)  #success is True if the racer was ready and now is unready
            #NB: success might be False even in reasonable-use contexts, e.g., if the countdown fails to cancel
            if success:
                yield from self._room.write('{0} is no longer ready.'.format(command.author.mention))
        else:
            yield from self._room.write('{}: Warning: You have not yet entered the race.'.format(command.author.mention))

class Done(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'done', 'finish', 'd')
        self.help_text = 'Indicates you have finished the race goal, and gets your final time. You may instead use `.d` if preferred.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.race or self._room.race.is_before_race:
            return

        racer = self._room.race.get_racer(command.author)
        if racer:
            success = yield from self._room.race.finish_racer(racer) #success is true if the racer was racing and is now finished
            if success:
                num_finished = self._room.race.num_finished
                yield from self._room.write('{0} has finished in {1} place with a time of {2}.'.format(command.author.mention, ordinal(num_finished), racer.time_str))

class Undone(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'undone', 'unfinish')
        self.help_text = 'Undoes an earlier `.done`.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.race or self._room.race.is_before_race:
            return

        success = yield from self._room.race.unfinish_racer(self._room.race.get_racer(command.author)) #success is true if the racer was finished and now is not
        #NB: success might be False even in reasonable-use contexts, e.g., if the race became finalized
        if success: 
            yield from self._room.write('{} is no longer done and continues to race.'.format(command.author.mention))

class Forfeit(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forfeit', 'quit')
        self.help_text = 'Forfeits from the race. You may use `.quit` instead of `.forfeit` if preferred.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.race or self._room.race.is_before_race:
            return

        success = yield from self._room.race.forfeit_racer(self._room.race.get_racer(command.author)) #success is True if the racer was racing and is now forfeit
        if success:
            yield from self._room.write('{} has forfeit the race.'.format(command.author.mention))

        if len(command.args) > 0:
            racer = self._room.race.get_racer(command.author)
            if racer:
                cut_length = len(command.command) + len(config.BOT_COMMAND_PREFIX) + 1
                end_length = 255 + cut_length
                racer.add_comment(command.message.content[cut_length:end_length])
                asyncio.ensure_future(self._room.update_leaderboard())            

class Unforfeit(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'unforfeit', 'unquit')
        self.help_text = 'Undoes an earlier `.forfeit`.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.race or self._room.race.is_before_race:
            return

        success = yield from self._room.race.unforfeit_racer(self._room.race.get_racer(command.author)) #success is true if the racer was forfeit and now is not
        #NB: success might be False even in reasonable-use contexts, e.g., if the race became finalized
        if success: 
            yield from self._room.write('{} is no longer forfeit and continues to race.'.format(command.author.mention))
                    
##class Comment(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'comment')
##        self.help_text = 'Adds text as a comment to your race.'
##        self._room = race_room
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if not self._room.race or self._room.race.is_before_race:
##            return
##
##        racer = self._room.race.get_racer(command.author)
##        if racer:
##            cut_length = len(command.command) + len(config.BOT_COMMAND_PREFIX) + 1
##            end_length = 255 + cut_length
##            racer.add_comment(command.message.content[cut_length:end_length])
##            asyncio.ensure_future(self._room.update_leaderboard())
##
##class Igt(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'igt')
##        self.help_text = 'Adds an in-game-time to your race, e.g. `{} 12:34.56.`'.format(self.mention)
##        self._room = race_room
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if not self._room.race or self._room.race.is_before_race:
##            return
##
##        if len(command.args) == 1:
##            igt = racetime.from_str(command.args[0])
##            racer = self._room.race.get_racer(command.author)
##            if igt != -1 and racer and racer.is_done_racing:
##                racer.igt = igt
##                asyncio.ensure_future(self._room.update_leaderboard())  

class Contest(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'contest')
        self.help_text = 'Mark the most recent race as contested. CoNDOR Staff will look into the race and discuss with you.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        race_to_contest = self._room.contestable_race_number
        if race_to_contest == 0:
            yield from self._room.write('{0}: No race has begun, so there is no race to contest. Use `.staff` if you need to alert CoNDOR Staff for some other reason.'.format(command.author.mention))
        else:
            self._room.condordb.set_contested(self._room.match, race_to_contest, command.author)
            yield from self._room.write('{0} has contested the result of race number {1}.'.format(command.author.mention, race_to_contest))
        
class Time(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'time')
        self.help_text = 'Get the current race time.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if not self._room.race or self._room.race.is_before_race:
            yield from self._room.write('The race hasn\'t started.')
        elif self._room.race.complete:
            yield from self._room.write('The race is over.')
        else:
            yield from self._room.write('The current race time is {}.'.format(self._room.race.current_time_str))

class ForceCancel(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcecancel')
        self.help_text = 'Cancels the race.'
        self.suppress_help = True
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.race and self._room.is_race_admin(command.author):
            yield from self._room.race.cancel()

class ForceClose(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forceclose')
        self.help_text = 'Cancel the race, and close the channel.'
        self.suppress_help = True
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.race and self._room.is_race_admin(command.author):
            yield from self._room.close()

class ForceForfeit(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forceforfeit')
        self.help_text = 'Force the given racer to forfeit the race (even if they have finished).'
        self.suppress_help = True
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.race and self._room.is_race_admin(command.author) and not self._room.race.is_before_race:
            for name in command.args:
                for racer in self._room.race.racers.values():
                    if racer.name.lower() == name.lower():
                        asyncio.ensure_future(self._room.race.forfeit_racer(racer))

class ForceForfeitAll(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forceforfeitall')
        self.help_text = 'Force all unfinished racers to forfeit the race.'
        self.suppress_help = True
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.race and self._room.is_race_admin(command.author) and not self._room.race.is_before_race:
            for racer in self._room.race.racers.values():
                if racer.is_racing:
                    asyncio.ensure_future(self._room.race.forfeit_racer(racer))
                        
class Kick(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'kick')
        self.help_text = 'Remove a racer from the race. (They can still re-enter with `.enter`.'
        self.suppress_help = True
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.race and self._room.is_race_admin(command.author):
            names_to_kick = [n.lower() for n in command.args]
            for racer in self._room.race.racers.values():
                if racer.name.lower() in names_to_kick:
                    success = yield from self._room.race.unenter_racer(racer)
                    if success:
                        yield from self._room.write('Kicked {} from the race.'.format(racer.name))
                                
class RaceRoom(command.Module):

    def get_new_raceinfo():
        to_return = RaceInfo()
        to_return.seed_fixed = False
        to_return.seeded = True
        to_return.character = 'Cadence'
        to_return.descriptor = 'Condor Race'
        to_return.sudden_death = False
        to_return.flagplant = False
        to_return.seed = seedgen.get_new_seed()

    def __init__(self, condor_module, condor_match, race_channel):
        self.channel = race_channel                                 #The channel in which this race is taking place
        self.is_closed = False                                      #True if room has been closed
        self.match = condor_match

        self.race = None                                            #The current race
        self.race_number = 0                                        #Which race are we on in the match

        self.entered_racers = []                                    #Racers that have typed .enter in this channel
        self.before_races = True

        self._cm = condor_module           

        self.command_types = [command.DefaultHelp(self),
                              Enter(self),
                              Ready(self),
                              Unready(self),
                              Done(self),
                              Undone(self),
                              Forfeit(self),
                              Unforfeit(self),
                              #Comment(self),
                              #Igt(self),
                              Time(self),
                              ForceCancel(self),
                              ForceClose(self),
                              ForceForfeit(self),
                              ForceForfeitAll(self),
                              Kick(self)]

    @property
    def infostr(self):
        return 'Race'

    @property
    def client(self):
        return self._cm.necrobot.client

    @property
    def condordb(self):
        return self._cm.condordb

    # Set up the leaderboard etc. Should be called after creation; code not put into __init__ b/c coroutine
    @asyncio.coroutine
    def initialize(self, users_to_mention=[]):
        yield from self.update_leaderboard()
        yield from self.alert_racers(send_pm=True)
        yield from self.countdown_to_match_start()

    # Write text to the raceroom. Return a Message for the text written
    @asyncio.coroutine
    def write(self, text):
        return self.client.send_message(self.channel, text)

    # Write text to the bot_notifications channel.
    @asyncio.coroutine
    def alert_staff(self, text):
        return self.client.send_message(self.necrobot.notifications_channel, text)

    #Updates the leaderboard
    @asyncio.coroutine
    def update_leaderboard(self):
        if self.race:
            asyncio.ensure_future(self.client.edit_channel(self.channel, topic=self.race.leaderboard))
        else:
            topic_str = '``` \n'
            topic_str += 'The race is scheduled to begin in {0} minutes! Please let the bot know you\'re here by typing .enter. \n\n'

            waiting_str = ''
            if match.racer_1 not in self.entered_racers:
                waiting_str += match.racer_1.twitch_name + ', '
            if match.racer_2 not in self.entered_racers:
                waiting_str += match.racer_2.twitch_name + ', '

            topic_str += 'Still waiting for .enter from: {0}'.format(waiting_str[:-2]) if waiting_str else 'Both racers have entered.'
                
            asyncio.ensure_future(self.client.edit_channel(self.channel, topic=topic_str))

    @asyncio.coroutine
    def alert_racers(self, send_pm=False):
        member_1 = self.necrobot.find_member_with_id(self.match.racer_1.discord_id)
        member_2 = self.necrobot.find_member_with_id(self.match.racer_2.discord_id)

        alert_str = ''
        if member_1:
            alert_str += member_1.mention + ', '
        if member_2:
            alert_str += member_2.mention + ', '

        minutes_until_match = self.match.time_until_match.total_seconds() // 60
        if alert_str:
            yield from self.write('{0}: The match is scheduled to begin in {1} minutes.'.format(alert_str[:-2], minutes_until_match))

        if send_pm:
            if member_1:
                yield from self.client.send_message(member_1, 'Your match with {0} is scheduled to begin in {1} minutes.'.format(member_1.mention, self.match.racer_2.twitch_name))
            if member_2:
                yield from self.client.send_message(member_2, 'Your match with {0} is scheduled to begin in {1} minutes.'.format(member_2.mention, self.match.racer_1.twitch_name))

    @asyncio.coroutine
    def countdown_to_match_start(self):        
        time_until_match = self.match.time_until_match

        if time_until_match < datetime.timedelta(seconds=0):
            print('Error: called RaceRoom.countdown_to_match_start() for match between {0} and {1}, after the scheduled match time.'.format(match.racer_1.twitch_name, match.racer_2.twitch_name))
            return
        
        first_warning = datetime.timedelta(minutes=15)
        alert_staff_warning = datetime.timedelta(minutes=5)
        if time_until_match > first_warning:
            yield from asyncio.sleep( (time_until_match - first_warning).total_seconds() )
            yield from self.alert_racers()

        time_until_match = self.match.time_until_match
        if time_until_match > alert_staff_warning:
            yield from asyncio.sleep( (time_until_match - alert_staff_warning).total_seconds() )

        # this is done at the alert_staff_warning, unless this function was called after the alert_staff_warning, in which case do it immediately
        yield from self.alert_racers()
        for racer in self.match.racers:
            if racer not in self.entered_racers:
                discord_name = ''
                if racer.discord_name:
                    discord_name = ' (Discord name: {0})'.format(racer.discord_name)
                yield from self.alert_staff('Alert: {0}{1} has not yet shown up for their match, which is scheduled in {2} minutes.'.format(racer.twitch_name, discord_name, self.match.time_until_match.total_seconds() // 60))

        yield from asyncio.sleep(self.match.time_until_match)
        yield from self.begin_new_race()

    @asyncio.coroutine
    def begin_new_race(self):
        self.before_races = False
        self.race = Race(self, RaceRoom.get_new_race_info())
        self.race_number += 1
        
        for racer in self.match.racers:
            racer_as_member = self.necrobot.find_member_with_id(racer.discord_id)
            if racer_as_member:
                self.race.enter_racer(racer_as_member)
            else:
                yield from self.write('Error: Couldn\'t find the racer {0}. Please contact CoNDOR Staff (`.staff`).'.format(racer.twitch_name))
                
        yield from self.update_leaderboard()
        yield from self.write('It\'s time for the race! Please type `.ready` when you are ready. When both racers `.ready`, the race will begin!')

    # Returns true if all racers are ready
    @property
    def all_racers_ready(self):
        return self.race and self.race.num_not_ready == 0

    @property
    def played_all_races(self):
        return self.condordb.number_of_finished_races(self.match) >= config.RACE_NUMBER_OF_RACES

    @property
    def race_to_contest(self):
        if not self.race:
            return 0

        if self.race.is_before_race:
            return self.race_number - 1
        else:
            return self.race_number

    # Begins the race if ready. (Writes a message if all racers are ready but an admin is not.)
    # Returns true on success
    @asyncio.coroutine
    def begin_if_ready(self):
        if self.race and self.all_racers_ready:
            yield from self.race.begin_race_countdown()
            return True     

    @asyncio.coroutine
    def enter_racer(self, member):
        for racer in self.match.racers:
            if int(racer.discord_id) == int(member.id):
                self.entered_racers.append(racer)
                yield from self.write('{0} is here for the race.'.format(member.mention))
                return

        yield from self.write('{0}: I do not recognize you as one of the racers in this match. Contact CoNDOR Staff (`.staff`) if this is in error.'.format(member.mention))

    @asyncio.coroutine  
    def record_race(self, cancelled=False):
        if self.race:
            self.condordb.record_race(self.match, self.race_number, self.race.racer_list, self.race.race_info.seed, self.race.start_time.timestamp(), cancelled)
            write_str = 'Race recorded.' if not cancelled else 'Race cancelled.'
            yield from self.write(write_str)
            yield from self.write('If you wish to contest the previous race\'s result, use the `.contest` command. This marks the race as contested; CoNDOR Staff will be alerted, and will '
                                  'look into your race.')

            if self.played_all_races:
                yield from self.record_match()
            else:
                yield from self.begin_new_race()

    @asyncio.coroutine
    def record_match(self):
        self.race_number += 1
        self.condordb.record_match(self.match)
        
