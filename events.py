from socketIO_client import SocketIO, LoggingNamespace

class Events():

    def racesoon(racer_1, racer_2):
        self._send_event('racesoon', {'racer1': racer_1, 'racer2': racer_2})

    def racestart(racer_1, racer_2):
        self._send_event('racestart', {'racer1': racer_1, 'racer2': racer_2})

    def raceend(racer_1, racer_2, winner):
        self._send_event('raceend', {'racer1': racer_1, 'racer2': racer_2, 'winner': winner})

    def matchend(racer_1, racer_2):
        self._send_event('matchend', {'racer1': racer_1, 'racer2': racer_2})

    def _send_event(self, event, data):
        if(config.EVENTS_ACTIVATED):
            with SocketIO(config.EVENTS_SERVER, config.EVENTS_PORT, LoggingNamespace) as socketIO:
                socketIO.emit(event, data)
