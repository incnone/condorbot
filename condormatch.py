class CondorRacer(object):
    def __init__(self, discord_id, twitch_name):
        self.discord_id = discord_user.id
        self.discord_name = None
        self.twitch_name = twitch_name
        self.steam_id = None
        self.timezone = None

    @property
    def gsheet_name(self):
        return self.twitch_name

class CondorMatch(object):
    def __init__(self, racer_1, racer_2, week):
        self.racer_1 = racer_1
        self.racer_2 = racer_2
        self.week = week
        self.time = None
