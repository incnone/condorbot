class CondorRacer(object):
    def __init__(self, twitch_name):
        self.discord_id = None
        self.discord_name = None
        self.twitch_name = twitch_name
        self.steam_id = None
        self.timezone = None

    @property
    def infostr(self):
        return '{0} (twitch.tv/{1}), timezone {2}'.format(self.discord_name, self.twitch_name, self.timezone)

    @property
    def gsheet_name(self):
        return self.twitch_name

class CondorMatch(object):
    FLAG_SCHEDULED = int(1) << 0
    FLAG_SCHEDULED_BY_R1 = int(1) << 1
    FLAG_SCHEDULED_BY_R2 = int(1) << 2
    FLAG_CONFIRMED_BY_R1 = int(1) << 3
    FLAG_CONFIRMED_BY_R2 = int(1) << 4
    FLAG_PLAYED = int(1) << 5

    def __init__(self, racer_1, racer_2, week):
        self._racer_1 = racer_1
        self._racer_2 = racer_2
        self._week = week
        self.time = None
        self.flags = 0

    @property
    def racer_1(self):
        return self._racer_1

    @property
    def racer_2(self):
        return self._racer_2

    @property
    def week(self):
        return self._week

    @property
    def is_scheduled(self):
        return FLAG_SCHEDULED & self.flags

    @property
    def confirmed(self):
        return (FLAG_CONFIRMED_BY_R1 & self.flags) and (FLAG_CONFIRMED_BY_R2 & self.flags)

    #returns the racer that scheduled this if possible
    @property
    def scheduled_by(self):
        if FLAG_SCHEDULED_BY_R1 & self.flags:
            return self.racer_1
        elif FLAG_SCHEDULED_BY_R2 & self.flags:
            return self.racer_2
        else:
            return None

    @property
    def played(self):
        return FLAG_PLAYED & self.flags

    def schedule(self, time, racer):
        self.flags = self.flags | FLAG_SCHEDULED
        if racer.twitch_name == self.racer_1.twitch_name:
            self.flags = self.flags | FLAG_SCHEDULED_BY_R1 | FLAG_CONFIRMED_BY_R1
        elif racer.twitch_name == self.racer_2.twitch_name:
            self.flags = self.flags | FLAG_SCHEDULED_BY_R2 | FLAG_CONFIRMED_BY_R2

    def confirm(self, racer):
        if racer.twitch_name == self.racer_1.twitch_name:
            self.flags = self.flags | FLAG_CONFIRMED_BY_R1
        elif racer.twitch_name == self.racer_2.twitch_name:
            self.flags = self.flags | FLAG_CONFIRMED_BY_R2        

    
