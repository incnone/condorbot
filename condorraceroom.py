# Class representing a channel in which a race (or several races) will occur.
# The list of all race rooms is managed by CondorModule.

import asyncio
import command
import config
import datetime
import discord
import level
import racetime
import seedgen
import textwrap
import time

from condormatch import CondorMatch
from race import Race
from racer import Racer
from raceinfo import RaceInfo

SUFFIXES = {1: 'st', 2: 'nd', 3: 'rd'}
def ordinal(num):
    if 10 <= num % 100 <= 20:
        suffix = 'th'
    else:
        suffix = SUFFIXES.get(num % 10, 'th')
    return str(num) + suffix

class Here(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'here')
        self.help_text = 'Lets the bot know you\'re here for the race. When it\'s time for the race, use `.ready` to indicate you are ready to begin.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
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
            yield from self._room.write('{}: Please type `.here` before readying.'.format(command.author.mention))
                    
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
            yield from self._room.write('{}: Warning: You have not yet said you\'re `.here` for the race.'.format(command.author.mention))

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

class Cancel(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'cancel')
        self.help_text = 'Indicates a desire to cancel the race. If both racers type `.cancel`, the race will be cancelled.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        success = yield from self._room.wants_to_cancel(command.author)
        if not success:
            yield from self._room.write('{0} wishes to cancel the race. Both racers must type `.cancel` for the race to be cancelled.'.format(command.author.mention))

##class Forfeit(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'forfeit', 'quit')
##        self.help_text = 'Forfeits from the race. You may use `.quit` instead of `.forfeit` if preferred.'
##        self._room = race_room
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if not self._room.race or self._room.race.is_before_race:
##            return
##
##        success = yield from self._room.race.forfeit_racer(self._room.race.get_racer(command.author)) #success is True if the racer was racing and is now forfeit
##        if success:
##            yield from self._room.write('{} has forfeit the race.'.format(command.author.mention))
##
##        if len(command.args) > 0:
##            racer = self._room.race.get_racer(command.author)
##            if racer:
##                cut_length = len(command.command) + len(config.BOT_COMMAND_PREFIX) + 1
##                end_length = 255 + cut_length
##                racer.add_comment(command.message.content[cut_length:end_length])
##                asyncio.ensure_future(self._room.update_leaderboard())            
##
##class Unforfeit(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'unforfeit', 'unquit')
##        self.help_text = 'Undoes an earlier `.forfeit`.'
##        self._room = race_room
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if not self._room.race or self._room.race.is_before_race:
##            return
##
##        success = yield from self._room.race.unforfeit_racer(self._room.race.get_racer(command.author)) #success is true if the racer was forfeit and now is not
##        #NB: success might be False even in reasonable-use contexts, e.g., if the race became finalized
##        if success: 
##            yield from self._room.write('{} is no longer forfeit and continues to race.'.format(command.author.mention))
                    
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
        race_to_contest = self._room.condordb.largest_recorded_race_number(self._room.match)
        if self._room.race and not self._room.race.is_before_race:
            race_to_contest += + 1

        if race_to_contest == 0:
            yield from self._room.write('{0}: No race has begun, so there is no race to contest. Use `.staff` if you need to alert CoNDOR Staff for some other reason.'.format(command.author.mention))
        else:
            self._room.condordb.set_contested(self._room.match, race_to_contest, command.author)
            yield from self._room.write('{0} has contested the result of race number {1}.'.format(command.author.mention, race_to_contest))
            yield from self._room.client.send_message(self._room.necrobot.notifications_channel, '{0} has contested the result of race number {1} in the match {2}.'.format(command.author.mention, race_to_contest, command.channel.mention))            
        
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
            yield from self._room.cancel_race()

##class ForceClose(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'forceclose')
##        self.help_text = 'Cancel the race, and close the channel.'
##        self.suppress_help = True
##        self._room = race_room
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if self._room.race and self._room.is_race_admin(command.author):
##            yield from self._room.close()

class ForceForfeit(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forceforfeit')
        self.help_text = 'Force the given racer to forfeit the race (even if they have finished).'
        #self.suppress_help = True
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.race and self._room.is_race_admin(command.author) and not self._room.race.is_before_race:
            for name in command.args:
                for racer in self._room.race.racers.values():
                    if racer.name.lower() == name.lower():
                        asyncio.ensure_future(self._room.race.forfeit_racer(racer))

##class ForceForfeitAll(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'forceforfeitall')
##        self.help_text = 'Force all unfinished racers to forfeit the race.'
##        self.suppress_help = True
##        self._room = race_room
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if self._room.race and self._room.is_race_admin(command.author) and not self._room.race.is_before_race:
##            for racer in self._room.race.racers.values():
##                if racer.is_racing:
##                    asyncio.ensure_future(self._room.race.forfeit_racer(racer))

class ForceChangeWinner(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcechangewinner')
        self.help_text = 'Change the winner of a specified race. Usage is `.forcechangewinner <race number> <winner\'s twitch name>`.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.is_race_admin(command.author):
            if len(command.args) != 2:
                yield from self._room.write('Wrong number of arguments for `.forcechangewinner`.')
                return

            try:
                race_int = int(command.args[0])
            except ValueError:
                yield from self._room.write('Error: couldn\'t parse {0} as a race number.'.format(command.args[0]))
                return

            winner_name = command.args[1].lower()
            if winner_name == self._room.match.racer_1.twitch_name.lower():
                winner_int = 1
            elif winner_name == self._room.match.racer_2.twitch_name.lower():
                winner_int = 2
            else:
                yield from self._room.write('I don\'t recognize the twitch name {}.'.format(winner_name))
                return

            self._room.condordb.change_winner(self._room.match, race_int, winner_int)
            yield from self._room.write('Recorded {0} as the winner of race {1}.'.format(command.args[1], race_int))
            yield from self._room.update_leaderboard()

class ForceRecordRace(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcerecordrace')
        self.help_text = 'Record a race that the bot did not record (useful if the bot goes down during a race). Usage is `.forcerecordrace [winner | -draw] [time_winner [time_loser]] [-seed seed_number]`. '\
                         'Winner names are twitch names (discord names will not work). See the channel name for the proper twitch names of the racers.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.is_race_admin(command.author):
            if len(command.args) == 0:
                yield from self._room.write('You must specify a winner, or `-draw`, to record a race.')
                return

            winner_name = command.args[0].lower()
            winner_int = 0
            if winner_name == self._room.match.racer_1.twitch_name.lower():
                winner_int = 1
            elif winner_name == self._room.match.racer_2.twitch_name.lower():
                winner_int = 2
            elif winner_name != '-draw':
                yield from self._room.write('I don\'t recognize the twitch name {}.'.format(winner_name))
                return

            command.args.pop(0)
            parse_seed = False
            parse_loser_time = False
            seed = 0
            racer_1_time = -1
            racer_2_time = -1
            for arg in command.args:
                if arg == '-seed':
                    parse_seed = True
                elif parse_seed:
                    try:
                        seed = int(arg)
                        parse_seed = False
                    except ValueError:
                        yield from self._room.write('Couldn\'t parse {0} as a seed.'.format(arg))
                        return
                else:
                    time = racetime.from_str(arg)
                    if time == -1:
                        yield from self._room.write('Couldn\'t parse {0} as a time.'.format(arg))
                        return
                    else:
                        if (parse_loser_time and winner_int == 2) or (not parse_loser_time and winner_int == 1):
                            racer_1_time = time
                        elif winner_int != 0:
                            racer_2_time = time
                        else:
                            yield from self._room.write('I can\'t parse racer times in races with no winner.')
                            return
                
            self._room.condordb.record_race(self._room.match, racer_1_time, racer_2_time, winner_int, seed, int(0), False, force_recorded=True)
            yield from self._room.write('Forced record of a race.')
            yield from self._room.update_leaderboard()

            if self._room.played_all_races:
                yield from self._room.record_match()
            
class ForceNewRace(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcenewrace')
        self.help_text = 'Force the bot to make a new race. If there is a current race and it is not yet recorded, it will be recorded and cancelled.'
        #self.suppress_help = True
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.is_race_admin(command.author):
            if self._room.race and not self._room.recorded_race:
                yield from self._room.record_race(cancelled=True)
            yield from self._room.begin_new_race()

class ForceCancelRace(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcecancelrace')
        self.help_text = 'Mark a previously recorded race as cancelled. Usage is e.g., `.forcecancelrace 2`, to cancel the second uncancelled race of a match.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.is_race_admin(command.author):
            if len(command.args) != 1:
                yield from self._room.write('Wrong number of arguments for `.forcecancelrace`.')
                return

            try:
                race_number = int(command.args[0])
            except ValueError:
                yield from self._room.write('Error: couldn\'t parse {0} as a race number.'.format(command.args[0]))
                return

            finished_number = self._room.condordb.finished_race_number(self._room.match, race_number)
            if finished_number:
                self._room.condordb.cancel_race(self._room.match, finished_number)
                yield from self._room.write('Race number {0} was cancelled.'.format(race_number))
                yield from self._room.update_leaderboard()
            else:
                self._room.write('I do not believe there have been {0} finished races.'.format(race_number))

class ForceRecordMatch(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcerecordmatch')
        self.help_text = 'Update the current match in the database and the gsheet.'
        self._room = race_room

    @asyncio.coroutine
    def _do_execute(self, command):
        if self._room.is_race_admin(command.author):
            yield from self._room.record_match()

##class ForceMatchDraw(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'forcematchdraw')
##        self.help_text = 'Force the match to be recorded as an intentional draw.'
            ## TODO
                        
##class Kick(command.CommandType):
##    def __init__(self, race_room):
##        command.CommandType.__init__(self, 'kick')
##        self.help_text = 'Remove a racer from the race. (They can still re-enter with `.enter`.'
##        self.suppress_help = True
##        self._room = race_room
##
##    @asyncio.coroutine
##    def _do_execute(self, command):
##        if self._room.race and self._room.is_race_admin(command.author):
##            names_to_kick = [n.lower() for n in command.args]
##            for racer in self._room.race.racers.values():
##                if racer.name.lower() in names_to_kick:
##                    success = yield from self._room.race.unenter_racer(racer)
##                    if success:
##                        yield from self._room.write('Kicked {} from the race.'.format(racer.name))
                                
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
        return to_return

    def __init__(self, condor_module, condor_match, race_channel):
        self.channel = race_channel                                 #The channel in which this race is taking place
        self.is_closed = False                                      #True if room has been closed
        self.match = condor_match

        self.race = None                                            #The current race
        self.recorded_race = False                                  #Whether the current race has been recorded

        self.entered_racers = []                                    #Racers that have typed .here in this channel
        self.before_races = True
        self.cancelling_racers = []                                 #Racers that have typed .cancel

        self._cm = condor_module           

        self.command_types = [command.DefaultHelp(self),
                              Here(self),
                              Ready(self),
                              Unready(self),
                              Done(self),
                              Undone(self),
                              Cancel(self),
                              #Forfeit(self),
                              #Unforfeit(self),
                              #Comment(self),
                              #Igt(self),
                              Time(self),
                              Contest(self),
                              ForceCancel(self),
                              ForceChangeWinner(self),
                              #ForceClose(self),
                              ForceForfeit(self),
                              #ForceForfeitAll(self),
                              ForceRecordRace(self),
                              ForceNewRace(self),
                              ForceCancelRace(self),
                              ForceRecordMatch(self),
                              #Kick(self),
                              ]

    @property
    def infostr(self):
        return 'Race'

    @property
    def client(self):
        return self._cm.necrobot.client

    @property
    def necrobot(self):
        return self._cm.necrobot

    @property
    def condordb(self):
        return self._cm.condordb

    #True if the user has admin permissions for this race
    def is_race_admin(self, member):
        admin_roles = self._cm.necrobot.admin_roles
        for role in member.roles:
            if role in admin_roles:
                return True
        
        return False

    # Set up the leaderboard etc. Should be called after creation; code not put into __init__ b/c coroutine
    @asyncio.coroutine
    def initialize(self, users_to_mention=[]):
        yield from self.update_leaderboard()
        asyncio.ensure_future(self.countdown_to_match_start())

    # Write text to the raceroom. Return a Message for the text written
    @asyncio.coroutine
    def write(self, text):
        return self.client.send_message(self.channel, text)

    # Write text to the bot_notifications channel.
    @asyncio.coroutine
    def alert_staff(self, text):
        return self.client.send_message(self._cm.necrobot.notifications_channel, text)

    # Register a racer as wanting to cancel
    @asyncio.coroutine
    def wants_to_cancel(self, member):
        for racer in self.match.racers:
            if int(racer.discord_id) == int(member.id) and not racer in self.cancelling_racers:
                self.cancelling_racers.append(racer)

        if len(self.cancelling_racers) == 2:
            yield from self.cancel_race()
            return True
        else:
            return False

    # Cancel the race
    @asyncio.coroutine
    def cancel_race(self):
        if self.race and not self.race.is_before_race:
            self.cancelling_racers = []
            yield from self.race.cancel()
            yield from self.record_race(cancelled=True)
            yield from self.write('The current race was cancelled.')
        else:
            self.cancelling_racers = []
            race_number = int(self._cm.condordb.largest_recorded_race_number(self.match))
            if race_number > 0:
                self.condordb.cancel_race(self.match, race_number)
                yield from self.write('The previous race was cancelled.'.format(race_number))
                yield from self.update_leaderboard()                  
                

    #Updates the leaderboard
    @asyncio.coroutine
    def update_leaderboard(self):
        if self.race or self.match.time_until_match.total_seconds() < 0:
            topic = '``` \n'
            topic += 'Condor Season 4 Match (Cadence Seeded)\n'
            max_name_len = 0
            for racer in self.match.racers:
                max_name_len = max(max_name_len, len(racer.discord_name))
            for racer in self.match.racers:
                wins = self._cm.condordb.number_of_wins(self.match, racer, count_draws=True)
                topic += '     ' + racer.discord_name + (' ' * (max_name_len - len(racer.discord_name))) + ' --- Wins: {0}\n'.format(str(round(wins,1) if wins % 1 else int(wins)))

            race_number = self._cm.condordb.number_of_finished_races(self.match) + 1
            if race_number > config.RACE_NUMBER_OF_RACES:
                topic += 'Match complete. \n'
            else:
                topic += 'Current race: #{}\n'.format(race_number)
                if self.race:
                    topic += self.race.leaderboard

            topic += '\n ```'
            asyncio.ensure_future(self.client.edit_channel(self.channel, topic=topic))
        else:
            topic_str = '``` \n'
            minutes_until_match = int( (self.match.time_until_match.total_seconds() + 30) // 60 )
            topic_str += 'The race is scheduled to begin in {0} minutes! Please let the bot know you\'re here by typing .here. \n\n'.format(minutes_until_match)

            waiting_str = ''
            if self.match.racer_1 not in self.entered_racers:
                waiting_str += self.match.racer_1.twitch_name + ', '
            if self.match.racer_2 not in self.entered_racers:
                waiting_str += self.match.racer_2.twitch_name + ', '

            topic_str += 'Still waiting for .here from: {0} \n'.format(waiting_str[:-2]) if waiting_str else 'Both racers are here!\n'

            topic_str += '```'
                
            asyncio.ensure_future(self.client.edit_channel(self.channel, topic=topic_str))

    @asyncio.coroutine
    def alert_racers(self, send_pm=False):
        member_1 = self._cm.necrobot.find_member_with_id(self.match.racer_1.discord_id)
        member_2 = self._cm.necrobot.find_member_with_id(self.match.racer_2.discord_id)

        alert_str = ''
        if member_1:
            alert_str += member_1.mention + ', '
        if member_2:
            alert_str += member_2.mention + ', '

        minutes_until_match = int( (self.match.time_until_match.total_seconds() + 30) // 60 )
        if alert_str:
            yield from self.write('{0}: The match is scheduled to begin in {1} minutes.'.format(alert_str[:-2], minutes_until_match))

        if send_pm:
            if member_1:
                yield from self.client.send_message(member_1, '{0}: Your match with {1} is scheduled to begin in {2} minutes.'.format(member_1.mention, self.match.racer_2.escaped_twitch_name, minutes_until_match))
            if member_2:
                yield from self.client.send_message(member_2, '{0}: Your match with {1} is scheduled to begin in {2} minutes.'.format(member_2.mention, self.match.racer_1.escaped_twitch_name, minutes_until_match))

    @asyncio.coroutine
    def countdown_to_match_start(self):        
        time_until_match = self.match.time_until_match
        asyncio.ensure_future(self.constantly_update_leaderboard())

        if time_until_match < datetime.timedelta(seconds=0):
            if not self.played_all_races:
                yield from self.write('I believe that I was just restarted; an error may have occurred. I am beginning a new race and attempting to pick up this ' \
                                      'match where we left off. If this is an error, or if there are unrecorded races, please contact CoNDOR Staff (`.staff`).')
                yield from self.begin_new_race()
        else:
            pm_warning = datetime.timedelta(minutes=30)
            first_warning = datetime.timedelta(minutes=15)
            alert_staff_warning = datetime.timedelta(minutes=5)

            if time_until_match > pm_warning:
                yield from asyncio.sleep( (time_until_match - pm_warning).total_seconds() )
                if not self.race:
                    yield from self.alert_racers(send_pm=True)                

            time_until_match = self.match.time_until_match            
            if time_until_match > first_warning:
                yield from asyncio.sleep( (time_until_match - first_warning).total_seconds() )
                if not self.race:
                    yield from self.alert_racers()

            time_until_match = self.match.time_until_match
            if time_until_match > alert_staff_warning:
                yield from asyncio.sleep( (time_until_match - alert_staff_warning).total_seconds() )

            # this is done at the alert_staff_warning, unless this function was called after the alert_staff_warning, in which case do it immediately
            if not self.race:
                yield from self.alert_racers()            
                for racer in self.match.racers:
                    if racer not in self.entered_racers:
                        discord_name = ''
                        if racer.discord_name:
                            discord_name = ' (Discord name: {0})'.format(racer.discord_name)
                        minutes_until_race = int( (self.match.time_until_match.total_seconds() + 30) // 60)
                        yield from self.alert_staff('Alert: {0}{1} has not yet shown up for their match, which is scheduled in {2} minutes.'.format(racer.escaped_twitch_name, discord_name, minutes_until_race))

                yield from self._cm.post_match_alert(self.match)

            yield from asyncio.sleep(self.match.time_until_match.total_seconds())

            if not self.race:
                yield from self.begin_new_race()

    @asyncio.coroutine
    def constantly_update_leaderboard(self):
        while self.match.time_until_match.total_seconds() > 0:
            asyncio.ensure_future(self.update_leaderboard())
            yield from asyncio.sleep(30)

    @asyncio.coroutine
    def begin_new_race(self):
        self.cancelling_racers = []
        self.before_races = False
        self.race = Race(self, RaceRoom.get_new_raceinfo())
        yield from self.race.initialize()
        self.recorded_race = False
        
        for racer in self.match.racers:
            racer_as_member = self._cm.necrobot.find_member_with_id(racer.discord_id)
            if racer_as_member:
                yield from self.race.enter_racer(racer_as_member)
            else:
                yield from self.write('Error: Couldn\'t find the racer {0}. Please contact CoNDOR Staff (`.staff`).'.format(racer.escaped_twitch_name))
                
        yield from self.update_leaderboard()

        race_number = int(self._cm.condordb.number_of_finished_races(self.match) + 1)
        race_str = '{}th'.format(race_number)
        if race_number == int(1):
            race_str = 'first'
        elif race_number == int(2):
            race_str = 'second'
        elif race_number == int(3):
            race_str = 'third'
            
        yield from self.write('Please input the seed ({1}) and type `.ready` when you are ready for the {0} race. '\
                              'When both racers `.ready`, the race will begin.'.format(race_str, self.race.race_info.seed))

    # Returns true if all racers are ready
    @property
    def all_racers_ready(self):
        return self.race and self.race.num_not_ready == 0

    @property
    def played_all_races(self):
        return self._cm.condordb.number_of_finished_races(self.match) >= config.RACE_NUMBER_OF_RACES

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
                if racer in self.entered_racers:
                    yield from self.write('{0} is already here.'.format(member.mention))
                    return
                
                self.entered_racers.append(racer)
                    
                yield from self.write('{0} is here for the race.'.format(member.mention))
                yield from self.update_leaderboard()

                return

        yield from self.write('{0}: I do not recognize you as one of the racers in this match. Contact CoNDOR Staff (`.staff`) if this is in error.'.format(member.mention))

    @asyncio.coroutine  
    def record_race(self, cancelled=False):
        if self.race and self.race.start_time:
            self.recorded_race = True
            racer_1_time = -1
            racer_2_time = -1
            racer_1_finished = False
            racer_2_finished = False
            for racer in self.race.racer_list:
                if int(racer.id) == int(self.match.racer_1.discord_id):
                    if racer.is_finished:
                        racer_1_time = racer.time
                        racer_1_finished = True
                elif int(racer.id) == int(self.match.racer_2.discord_id):
                    if racer.is_finished:
                        racer_2_time = racer.time
                        racer_2_finished = True

            winner = 0
            if racer_1_finished and not racer_2_finished:
                winner = 1
            elif not racer_1_finished and racer_2_finished:
                winner = 2
            elif racer_1_finished and racer_2_finished:
                if racer_1_time < racer_2_time:
                    winner = 1
                elif racer_2_time < racer_1_time:
                    winner = 2

            if abs(racer_1_time - racer_2_time) <= (config.RACE_NOTIFY_IF_TIMES_WITHIN_SEC*100):
                race_number = self._cm.condordb.number_of_finished_races(self.match) + 1
                yield from self.client.send_message(self.necrobot.notifications_channel,
                    'Race number {0} has finished within {1} seconds in channel {2}. ({3} -- {4}, {5} -- {6})'.format(
                        race_number, config.RACE_NOTIFY_IF_TIMES_WITHIN_SEC, self.channel.mention,
                        self.match.racer_1.escaped_twitch_name, racetime.to_str(racer_1_time),
                        self.match.racer_2.escaped_twitch_name, racetime.to_str(racer_2_time)))

            self._cm.condordb.record_race(self.match, racer_1_time, racer_2_time, winner, self.race.race_info.seed, self.race.start_time.timestamp(), cancelled)

            if not cancelled:
                racer_1_member = self.necrobot.find_member_with_id(self.match.racer_1.discord_id)
                racer_2_member = self.necrobot.find_member_with_id(self.match.racer_2.discord_id)
                racer_1_mention = racer_1_member.mention if racer_1_member else ''
                racer_2_mention = racer_2_member.mention if racer_2_member else ''
                write_str = '{0}, {1}: The race is over, and has been recorded.'.format(racer_1_mention, racer_2_mention)
            else:
                write_str = 'Race cancelled.'
                
            yield from self.write(write_str)
            yield from self.write('If you wish to contest the previous race\'s result, use the `.contest` command. This marks the race as contested; CoNDOR Staff will be alerted, and will '
                                  'look into your race.')

            if self.played_all_races:
                yield from self.record_match()
            else:
                yield from self.begin_new_race()

    @asyncio.coroutine
    def record_match(self):
        self._cm.condordb.record_match(self.match)
        yield from self._cm.condorsheet.record_match(self.match)
        yield from self.write('Match results recorded.')      
        yield from self.update_leaderboard()
