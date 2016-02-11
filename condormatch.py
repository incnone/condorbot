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
    def __init__(self, racer_1, racer_2, week):
        self.racer_1 = racer_1
        self.racer_2 = racer_2
        self.week = week
        self.time = None
