# Class representing a channel in which a race (or several races) will occur.
# The list of all race rooms is managed by CondorModule.

import asyncio
import command
import config
import datetime
import racetime
import seedgen

from race import Race
from raceinfo import RaceInfo
from events import Events

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
        self.help_text = 'Lets the bot know you\'re here for the race. When it\'s time for the race, use `.ready` ' \
                         'to indicate you are ready to begin.'
        self._room = race_room

    async def _do_execute(self, cmd):
        await self._room.enter_racer(cmd.author)


class Ready(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'ready', 'r')
        self.help_text = 'Indicates that you are ready to begin the race. The race begins when all entrants are ready.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if not self._room.race or not self._room.race.is_before_race:
            return
        
        racer = self._room.race.get_racer(cmd.author)
        if racer:
            success = await self._room.race.ready_racer(racer)   # True if the racer was unready and now is ready
            if success:
                if len(self._room.race.racers) == 1 and config.REQUIRE_AT_LEAST_TWO_FOR_RACE:
                    await self._room.write('Waiting on at least one other person to join the race.')
                else:
                    await self._room.write('{0} is ready! {1} remaining.'.format(
                        cmd.author.mention, self._room.race.num_not_ready))

                await self._room.begin_if_ready()

            elif racer.is_ready:
                await self._room.write('{0} is already ready!'.format(cmd.author.mention))
        else:
            await self._room.write('{}: Please type `.here` before readying.'.format(cmd.author.mention))
               
                    
class Unready(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'unready')
        self.help_text = 'Undoes `.ready`.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if not self._room.race or not self._room.race.is_before_race:
            return
        
        racer = self._room.race.get_racer(cmd.author)
        if racer:
            success = await self._room.race.unready_racer(racer)  # True if the racer was ready and now is unready
            # NB: success might be False even in reasonable-use contexts, e.g., if the countdown fails to cancel
            if success:
                await self._room.write('{0} is no longer ready.'.format(cmd.author.mention))
        else:
            await self._room.write(
                '{}: Warning: You have not yet said you\'re `.here` for the race.'.format(cmd.author.mention))


class Done(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'done', 'finish', 'd')
        self.help_text = 'Indicates you have finished the race goal, and gets your final time. ' \
                         'You may instead use `.d` if preferred.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if not self._room.race or self._room.race.is_before_race:
            return

        racer = self._room.race.get_racer(cmd.author)
        if racer:
            success = await self._room.race.finish_racer(racer)  # true if the racer was racing and is now finished
            if success:
                num_finished = self._room.race.num_finished
                await self._room.write('{0} has finished in {1} place with a time of {2}.'.format(
                    cmd.author.mention, ordinal(num_finished), racer.time_str))


class Undone(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'undone', 'unfinish')
        self.help_text = 'Undoes an earlier `.done`.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if not self._room.race or self._room.race.is_before_race:
            return

        success = await self._room.race.unfinish_racer(self._room.race.get_racer(cmd.author)) 
        # success is true if the racer was finished and now is not
        # NB: success might be False even in reasonable-use contexts, e.g., if the race became finalized
        if success: 
            await self._room.write('{} is no longer done and continues to race.'.format(cmd.author.mention))


class Cancel(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'cancel')
        self.help_text = 'Indicates a desire to cancel the race. If both racers type `.cancel`, ' \
                         'the race will be cancelled.'
        self._room = race_room

    async def _do_execute(self, cmd):
        success = await self._room.wants_to_cancel(cmd.author)
        if not success:
            await self._room.write(
                '{0} wishes to cancel the race. Both racers must type `.cancel` for the race '
                'to be cancelled.'.format(cmd.author.mention))


class Contest(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'contest')
        self.help_text = 'Mark the most recent race as contested. CoNDOR Staff will look into the race and ' \
                         'discuss with you.'
        self._room = race_room

    async def _do_execute(self, cmd):
        race_to_contest = self._room.condordb.largest_recorded_race_number(self._room.match)
        if self._room.race and not self._room.race.is_before_race:
            race_to_contest += + 1

        if race_to_contest == 0:
            await self._room.write(
                '{0}: No race has begun, so there is no race to contest. Use `.staff` if you '
                'need to alert CoNDOR Staff for some other reason.'.format(cmd.author.mention))
        else:
            self._room.condordb.set_contested(self._room.match, race_to_contest, cmd.author)
            await self._room.write(
                '{0} has contested the result of race number {1}.'.format(cmd.author.mention, race_to_contest))
            await self._room.client.send_message(
                self._room.necrobot.notifications_channel, 
                '{0} has contested the result of race number {1} in the match {2}.'.format(
                    cmd.author.mention, race_to_contest, cmd.channel.mention))            


class Time(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'time')
        self.help_text = 'Get the current race time.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if not self._room.race or self._room.race.is_before_race:
            await self._room.write('The race hasn\'t started.')
        elif self._room.race.complete:
            await self._room.write('The race is over.')
        else:
            await self._room.write('The current race time is {}.'.format(self._room.race.current_time_str))


class Pause(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'pause')
        self.help_text = 'Pause the race, and alert the racers.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.race and self._room.is_race_admin(cmd.author):
            mention_str = ''
            for _, racer in self._room.race.racers.items():
                mention_str += racer.member.mention + ', '
            if mention_str == '':
                mention_str = ', '
            await self._room.write('{0}: Please pause.'.format(mention_str[:-2]))
            await self._room.race.pause()


class Unpause(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'unpause')
        self.help_text = 'Unpause the race.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.race and self._room.is_race_admin(cmd.author):
            if not self._room.race.is_paused:
                await self._room.write('The race is not paused.')
                return

            await self._room.write('The race will continue in 5 seconds.')
            await asyncio.sleep(2)
            await self._room.write('3')
            await asyncio.sleep(1)
            await self._room.write('2')
            await asyncio.sleep(1)
            await self._room.write('1')
            await asyncio.sleep(1)
            await self._room.write('GO!')

            await self._room.race.unpause()


class ForceForfeit(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forceforfeit')
        self.help_text = 'Force the given racer to forfeit the race (even if they have finished).'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.race and self._room.is_race_admin(cmd.author) and not self._room.race.is_before_race:
            for name in cmd.args:
                for racer in self._room.race.racers.values():
                    if racer.name.lower() == name.lower():
                        asyncio.ensure_future(self._room.race.forfeit_racer(racer))


class ForceChangeWinner(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcechangewinner')
        self.help_text = 'Change the winner of a specified race. Usage is `.forcechangewinner <race number> ' \
                         '<winner\'s RTMP name>`.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.is_race_admin(cmd.author):
            if len(cmd.args) != 2:
                await self._room.write('Wrong number of arguments for `.forcechangewinner`.')
                return

            try:
                race_int = int(cmd.args[0])
            except ValueError:
                await self._room.write('Error: couldn\'t parse {0} as a race number.'.format(cmd.args[0]))
                return

            winner_name = cmd.args[1].lower()
            if winner_name == self._room.match.racer_1.unique_name.lower():
                winner_int = 1
            elif winner_name == self._room.match.racer_2.unique_name.lower():
                winner_int = 2
            else:
                await self._room.write('I don\'t recognize the twitch name {}.'.format(winner_name))
                return

            self._room.condordb.change_winner(self._room.match, race_int, winner_int)
            await self._room.write('Recorded {0} as the winner of race {1}.'.format(cmd.args[1], race_int))
            await self._room.update_leaderboard()


class ForceRecordRace(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcerecordrace')
        self.help_text = 'Record a race that the bot did not record (useful if the bot goes down during a race). ' \
                         'Usage is `.forcerecordrace [winner | -draw] [time_winner [time_loser]] ' \
                         '[-seed seed_number]`. Winner names are RTMP names (discord names will not work). ' \
                         'See the channel name for the proper RTMP names of the racers.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.is_race_admin(cmd.author):
            if len(cmd.args) == 0:
                await self._room.write('You must specify a winner, or `-draw`, to record a race.')
                return

            winner_name = cmd.args[0].lower()
            winner_int = 0
            if winner_name == self._room.match.racer_1.unique_name.lower():
                winner_int = 1
            elif winner_name == self._room.match.racer_2.unique_name.lower():
                winner_int = 2
            elif winner_name != '-draw':
                await self._room.write('I don\'t recognize the name {}.'.format(winner_name))
                return

            cmd.args.pop(0)
            parse_seed = False
            parse_loser_time = False
            seed = 0
            racer_1_time = -1
            racer_2_time = -1
            for arg in cmd.args:
                if arg == '-seed':
                    parse_seed = True
                elif parse_seed:
                    try:
                        seed = int(arg)
                        parse_seed = False
                    except ValueError:
                        await self._room.write('Couldn\'t parse {0} as a seed.'.format(arg))
                        return
                else:
                    time = racetime.from_str(arg)
                    if time == -1:
                        await self._room.write('Couldn\'t parse {0} as a time.'.format(arg))
                        return
                    else:
                        if (parse_loser_time and winner_int == 2) or (not parse_loser_time and winner_int == 1):
                            racer_1_time = time
                        elif winner_int != 0:
                            racer_2_time = time
                        else:
                            await self._room.write('I can\'t parse racer times in races with no winner.')
                            return
                
            self._room.condordb.record_race(
                self._room.match, racer_1_time, racer_2_time, winner_int, seed, int(0), False, force_recorded=True)
            await self._room.write('Forced record of a race.')
            await self._room.update_leaderboard()

            if self._room.played_all_races:
                await self._room.record_match()


class ForceNewRace(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcenewrace')
        self.help_text = 'Force the bot to make a new race. If there is a current race and it is not yet recorded, ' \
                         'it will be recorded and cancelled.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.is_race_admin(cmd.author):
            if self._room.race and not self._room.recorded_race:
                await self._room.record_race(cancelled=True)
            else:
                await self._room.begin_new_race()


class ForceCancelRace(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcecancelrace')
        self.help_text = 'Mark a previously recorded race as cancelled. Usage is e.g., `.forcecancelrace 2`, ' \
                         'to cancel the second uncancelled race of a match.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.is_race_admin(cmd.author):
            if len(cmd.args) != 1:
                await self._room.write('Wrong number of arguments for `.forcecancelrace`.')
                return

            try:
                race_number = int(cmd.args[0])
            except ValueError:
                await self._room.write('Error: couldn\'t parse {0} as a race number.'.format(cmd.args[0]))
                return

            finished_number = self._room.condordb.finished_race_number(self._room.match, race_number)
            if finished_number:
                self._room.condordb.cancel_race(self._room.match, finished_number)
                await self._room.write('Race number {0} was cancelled.'.format(race_number))
                await self._room.update_leaderboard()
            else:
                self._room.write('I do not believe there have been {0} finished races.'.format(race_number))


class ForceRecordMatch(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'forcerecordmatch')
        self.help_text = 'Update the current match in the database and the gsheet.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.is_race_admin(cmd.author):
            await self._room.record_match()


class Reseed(command.CommandType):
    def __init__(self, race_room):
        command.CommandType.__init__(self, 'reseed')
        self.help_text = 'Roll a new seed for the current race.'
        self._room = race_room

    async def _do_execute(self, cmd):
        if self._room.is_race_admin(cmd.author):
            if self._room.race is None:
                await self._room.write('Cannot reseed, because there is no active race.')
            elif not self._room.race.is_before_race:
                await self._room.write('Cannot reseed, because we are not in the entry phase of the current race.')
            else:
                self._room.race.reseed()
                await self._room.write('New seed generated: {0}.'.format(self._room.race.race_info.seed))

                                
class RaceRoom(command.Module):

    @staticmethod
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
        command.Module.__init__(self, condor_module.necrobot)
        self.channel = race_channel                                 # The channel in which this race is taking place
        self.is_closed = False                                      # True if room has been closed
        self.match = condor_match

        self.events = Events()

        self.race = None                                            # The current race
        self.recorded_race = False                                  # Whether the current race has been recorded

        self.entered_racers = []                                    # Racers that have typed .here in this channel
        self.before_races = True
        self.cancelling_racers = []                                 # Racers that have typed .cancel

        self._cm = condor_module           

        self.command_types = [command.DefaultHelp(self),
                              Here(self),
                              Ready(self),
                              Unready(self),
                              Done(self),
                              Undone(self),
                              Cancel(self),
                              Time(self),
                              Contest(self),
                              Pause(self),
                              Unpause(self),
                              # ForceCancel(self),
                              ForceChangeWinner(self),
                              ForceForfeit(self),
                              ForceRecordRace(self),
                              ForceNewRace(self),
                              ForceCancelRace(self),
                              ForceRecordMatch(self),
                              Reseed(self)
                              ]

    @property
    def infostr(self):
        return 'Race'

    @property
    def client(self):
        return self.necrobot.client

    @property
    def condordb(self):
        return self._cm.condordb

    # True if the user has admin permissions for this race
    def is_race_admin(self, member):
        admin_roles = self._cm.necrobot.admin_roles
        for role in member.roles:
            if role in admin_roles:
                return True
        
        return False

    # Set up the leaderboard etc. Should be called after creation; code not put into __init__ b/c coroutine
    async def initialize(self):
        await self.update_leaderboard()
        asyncio.ensure_future(self.countdown_to_match_start())

    # Write text to the raceroom. Return a Message for the text written
    async def write(self, text):
        return await self.client.send_message(self.channel, text)

    # Write text to the bot_notifications channel.
    async def alert_staff(self, text):
        return await self.client.send_message(self._cm.necrobot.notifications_channel, text)

    # Register a racer as wanting to cancel
    async def wants_to_cancel(self, member):
        for racer in self.match.racers:
            if int(racer.discord_id) == int(member.id) and racer not in self.cancelling_racers:
                self.cancelling_racers.append(racer)

        if len(self.cancelling_racers) == 2:
            await self.cancel_race()
            return True
        else:
            return False

    # Cancel the race
    async def cancel_race(self):
        if self.race and not self.race.is_before_race:
            self.cancelling_racers = []
            await self.race.cancel()
            await self.record_race(cancelled=True)
            await self.write('The current race was cancelled.')
        else:
            self.cancelling_racers = []
            race_number = int(self._cm.condordb.largest_recorded_race_number(self.match))
            if race_number > 0:
                self.condordb.cancel_race(self.match, race_number)
                await self.write('The previous race was cancelled.'.format(race_number))
                await self.update_leaderboard()                  

    # Updates the leaderboard
    async def update_leaderboard(self):
        return

        if self.race or self.match.time_until_match.total_seconds() < 0:
            topic = '``` \n'
            topic += 'Necrodancer World Cup Match (Cadence Seeded)\n'
            max_name_len = 0
            for racer in self.match.racers:
                max_name_len = max(max_name_len, len(racer.discord_name))
            for racer in self.match.racers:
                wins = self._cm.condordb.number_of_wins(self.match, racer, count_draws=True)
                topic += '     ' + racer.discord_name + (' ' * (max_name_len - len(racer.discord_name))) + \
                         ' --- Wins: {0}\n'.format(str(round(wins, 1) if wins % 1 else int(wins)))

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
            minutes_until_match = int((self.match.time_until_match.total_seconds() + 30) // 60)
            topic_str += 'The race is scheduled to begin in {0} minutes! ' \
                         'Please let the bot know you\'re here by typing .here. \n\n'.format(minutes_until_match)

            waiting_str = ''
            if self.match.racer_1 not in self.entered_racers:
                waiting_str += self.match.racer_1.twitch_name + ', '
            if self.match.racer_2 not in self.entered_racers:
                waiting_str += self.match.racer_2.twitch_name + ', '

            topic_str += 'Still waiting for .here from: {0} \n'.format(waiting_str[:-2]) \
                if waiting_str else 'Both racers are here!\n'

            topic_str += '```'
                
            asyncio.ensure_future(self.client.edit_channel(self.channel, topic=topic_str))

    async def alert_racers(self, send_pm=False):
        member_1 = self._cm.necrobot.find_member_with_id(self.match.racer_1.discord_id)
        member_2 = self._cm.necrobot.find_member_with_id(self.match.racer_2.discord_id)

        alert_str = ''
        if member_1:
            alert_str += member_1.mention + ', '
        if member_2:
            alert_str += member_2.mention + ', '

        minutes_until_match = int((self.match.time_until_match.total_seconds() + 30) // 60)
        if alert_str:
            await self.write('{0}: The match is scheduled to begin in {1} minutes.'.format(
                alert_str[:-2], minutes_until_match))

        if send_pm:
            if member_1:
                await self.client.send_message(
                    member_1, 
                    '{0}: Your match with {1} is scheduled to begin in {2} minutes.'.format(
                        member_1.mention, self.match.racer_2.escaped_unique_name, minutes_until_match))
            if member_2:
                await self.client.send_message(
                    member_2, 
                    '{0}: Your match with {1} is scheduled to begin in {2} minutes.'.format(
                        member_2.mention, self.match.racer_1.escaped_unique_name, minutes_until_match))

    async def countdown_to_match_start(self):
        time_until_match = self.match.time_until_match
        asyncio.ensure_future(self.constantly_update_leaderboard())

        if time_until_match < datetime.timedelta(seconds=0):
            if not self.played_all_races:
                await self.write(
                    'I believe that I was just restarted; an error may have occurred. I am '
                    'beginning a new race and attempting to pick up this match where we left '
                    'off. If this is an error, or if there are unrecorded races, please contact '
                    'CoNDOR Staff (`.staff`).')
                await self.begin_new_race()
        else:
            pm_warning = datetime.timedelta(minutes=30)
            first_warning = datetime.timedelta(minutes=15)
            alert_staff_warning = datetime.timedelta(minutes=5)

            if time_until_match > pm_warning:
                await asyncio.sleep((time_until_match - pm_warning).total_seconds())
                if not self.race:
                    await self.alert_racers(send_pm=True)                

            time_until_match = self.match.time_until_match            
            if time_until_match > first_warning:
                await asyncio.sleep((time_until_match - first_warning).total_seconds())
                if not self.race:
                    await self.alert_racers()

            time_until_match = self.match.time_until_match
            if time_until_match > alert_staff_warning:
                await asyncio.sleep((time_until_match - alert_staff_warning).total_seconds())

            # this is done at the alert_staff_warning, unless this function was called after the alert_staff_warning, 
            # in which case do it immediately

            if not self.race:
                await self.alert_racers()            
                for racer in self.match.racers:
                    if racer not in self.entered_racers:
                        discord_name = ''
                        if racer.discord_name:
                            discord_name = ' (Discord name: {0})'.format(racer.discord_name)
                        minutes_until_race = int((self.match.time_until_match.total_seconds() + 30) // 60)
                        await self.alert_staff(
                            'Alert: {0}{1} has not yet shown up for their match, which is scheduled in '
                            '{2} minutes in {3}.'.format(
                                racer.escaped_unique_name,
                                discord_name,
                                minutes_until_race,
                                self.channel.mention))

                await self._cm.post_match_alert(self.match)

            await asyncio.sleep(self.match.time_until_match.total_seconds())

            if not self.race:
                await self.begin_new_race()

    async def constantly_update_leaderboard(self):
        while self.match.time_until_match.total_seconds() > 0:
            asyncio.ensure_future(self.update_leaderboard())
            await asyncio.sleep(30)

    async def begin_new_race(self):
        self.cancelling_racers = []
        self.before_races = False
        self.race = Race(self, RaceRoom.get_new_raceinfo(), self._cm.condordb)
        await self.race.initialize()
        self.recorded_race = False

        for racer in self.match.racers:
            racer_as_member = self._cm.necrobot.find_member_with_id(racer.discord_id)
            if racer_as_member:
                await self.race.enter_racer(racer_as_member)
            else:
                await self.write(
                    'Error: Couldn\'t find the racer {0}. Please contact CoNDOR Staff (`.staff`).'.format(
                        racer.escaped_unique_name))
                
        await self.update_leaderboard()

        race_number = int(self._cm.condordb.number_of_finished_races(self.match) + 1)
        race_str = '{}th'.format(race_number)
        if race_number == int(1):
            race_str = 'first'
        elif race_number == int(2):
            race_str = 'second'
        elif race_number == int(3):
            race_str = 'third'

        await self.write(
            'Please input the seed ({1}) and type `.ready` when you are ready for the {0} race. '
            'When both racers `.ready`, the race will begin.'.format(race_str, self.race.race_info.seed))

    # Returns true if all racers are ready
    @property
    def all_racers_ready(self):
        return self.race and self.race.num_not_ready == 0

    @property
    def played_all_races(self):
        if self.match.is_best_of:
            return self._cm.condordb.number_of_wins_of_leader(self.match) >= (self.match.number_of_races//2 + 1)
        else:
            return self._cm.condordb.number_of_finished_races(self.match) >= self.match.number_of_races

    @property
    def race_to_contest(self):
        if not self.race:
            return 0

        return int(self._cm.condordb.largest_recorded_race_number(self.match))

    # Begins the race if ready. (Writes a message if all racers are ready but an admin is not.)
    # Returns true on success
    async def begin_if_ready(self):
        if self.race and self.all_racers_ready:
            await self.race.begin_race_countdown()
            return True     

    async def enter_racer(self, member):
        for racer in self.match.racers:
            if int(racer.discord_id) == int(member.id):
                if racer in self.entered_racers:
                    await self.write('{0} is already here.'.format(member.mention))
                    return
                
                self.entered_racers.append(racer)
                    
                await self.write('{0} is here for the race.'.format(member.mention))
                await self.update_leaderboard()

                return

        await self.write(
            '{0}: I do not recognize you as one of the racers in this match. '
            'Contact CoNDOR Staff (`.staff`) if this is in error.'.format(member.mention))

    async def record_race(self, cancelled=False):
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
                await self.client.send_message(
                    self.necrobot.notifications_channel,
                    'Race number {0} has finished within {1} seconds in channel {2}. ({3} -- {4}, {5} -- {6})'.format(
                        race_number, config.RACE_NOTIFY_IF_TIMES_WITHIN_SEC, self.channel.mention,
                        self.match.racer_1.escaped_unique_name, racetime.to_str(racer_1_time),
                        self.match.racer_2.escaped_unique_name, racetime.to_str(racer_2_time)))

            self._cm.condordb.record_race(
                self.match, racer_1_time, racer_2_time, winner, 
                self.race.race_info.seed, self.race.start_time.timestamp(), cancelled)

            if not cancelled:
                racer_1_member = self.necrobot.find_member_with_id(self.match.racer_1.discord_id)
                racer_2_member = self.necrobot.find_member_with_id(self.match.racer_2.discord_id)
                racer_1_mention = racer_1_member.mention if racer_1_member else ''
                racer_2_mention = racer_2_member.mention if racer_2_member else ''
                write_str = '{0}, {1}: The race is over, and has been recorded.'.format(
                    racer_1_mention, racer_2_mention)
            else:
                write_str = 'Race cancelled.'

            await self.write(write_str)
            await self.write(
                'If you wish to contest the previous race\'s result, use the `.contest` command. This marks the '
                'race as contested; CoNDOR Staff will be alerted, and will look into your race.')

            if self.played_all_races:
                # Send match ending event if all races have been played
                self.events.matchend(self.match.racer_1.rtmp_name, self.match.racer_2.rtmp_name)
                await self.record_match()
            else:
                await self.begin_new_race()

    async def record_match(self):
        self._cm.condordb.record_match(self.match)
        await self._cm.condorsheet.record_match(self.match)
        await self.write('Match results recorded.')      
        await self.update_leaderboard()
