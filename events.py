import asyncio
import config
from socketIO_client import SocketIO, LoggingNamespace


class Events:

    def racesoon(self, racer_1, racer_2):
        asyncio.ensure_future(self._send_event('racesoon', {'racer1': racer_1, 'racer2': racer_2}))

    def racestart(self, racer_1, racer_2):
        asyncio.ensure_future(self._send_event('racestart', {'racer1': racer_1, 'racer2': racer_2}))

    def raceend(self, racer_1, racer_2, winner):
        asyncio.ensure_future(self._send_event('raceend', {'racer1': racer_1, 'racer2': racer_2, 'winner': winner}))

    def matchend(self, racer_1, racer_2):
        asyncio.ensure_future(self._send_event('matchend', {'racer1': racer_1, 'racer2': racer_2}))

    async def _send_event(self, event, data):
        if(config.EVENTS_ACTIVATED):
            try:
                with SocketIO(config.EVENTS_SERVER, config.EVENTS_PORT, LoggingNamespace, False) as socketIO:
                    socketIO.emit(event, data)
            except Exception as e:
                print('Error sending event', event, data, repr(e))
