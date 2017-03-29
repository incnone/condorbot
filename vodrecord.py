import asyncio
import certifi
import config
import datetime
import logging
import pycurl
import sys
from io import BytesIO


class VodRecorder(object):
    instance = None

    def __init__(self):
        if not VodRecorder.instance:
            VodRecorder.instance = VodRecorder.__VodRecorder()

    def __getattr__(self, name):
        return getattr(self.instance, name)

    class __VodRecorder(object):
        def __init__(self):
            self._lock = asyncio.Lock()
            self._recording_rtmps = []  # list of rtmp names
            self._vodstart_buffers = {}  # dict from RTMP names to BytesIO() buffers
            self._end_buffer = BytesIO()

        async def get_vodname(self, rtmp_name):
            if rtmp_name not in self._vodstart_buffers:
                return None

            async with self._lock:
                buffer_return = self._vodstart_buffers[rtmp_name].getvalue().decode('utf-8')
                if buffer_return:
                    return self._convert_to_vodlink(rtmp_name, buffer_return)
                else:
                    return None

        def start_record(self, rtmp_name):
            if not config.RECORDING_ACTIVATED:
                return

            with (yield from self._lock):
                self._start_record_nolock(rtmp_name)

        def end_record(self, rtmp_name):
            if not config.RECORDING_ACTIVATED:
                return

            with (yield from self._lock):
                self._end_record_nolock(rtmp_name)

        def end_all(self):
            if not config.RECORDING_ACTIVATED:
                return

            with (yield from self._lock):
                for rtmp_name in self._recording_rtmps:
                    curl = pycurl.Curl()
                    try:
                        curl.setopt(pycurl.CAINFO, certifi.where())
                        curl.setopt(pycurl.URL, self._end_url(rtmp_name))
                        curl.setopt(pycurl.WRITEDATA, self._end_buffer)
                        curl.perform()
                    except pycurl.error as e:
                        self._log_warning(
                            'Pycurl error in end_all() for racer <{0}>: Tried to curl <{1}>. Error {2}.'.format(
                                rtmp_name,
                                self._end_url(rtmp_name),
                                e))
                    finally:
                        curl.close()

                self._recording_rtmps.clear()

        @staticmethod
        def _convert_to_vodlink(rtmp_name, vodname):
            EPOCH = datetime.datetime(year=1970, month=1, day=1)

            if not vodname:
                return None

            try:
                cut_idx = vodname.find('live-') + 5
                seconds_since_epoch = int(vodname[cut_idx:-4])
                vodtime = EPOCH + datetime.timedelta(seconds=seconds_since_epoch)
                return 'https://vod.condor.host/{0}/{0}-vod-{1}%3A{2}.flv'.format(
                    rtmp_name,
                    vodtime.strftime("%Y-%m-%d_%H"),
                    vodtime.strftime("%M"))
            except ValueError as e:
                VodRecorder()._log_warning(
                    'ValueError in VodRecorder._convert_to_vodlink({0}, {1}). Error: {2}'.format(
                        rtmp_name,
                        vodname,
                        e))
                return None

        @staticmethod
        def _log_warning(s):
            logging.getLogger('discord').warning(s)
            print(s)

        @staticmethod
        def _start_url(rtmp_name):
            return 'https://{1}/control/record/start?app={0}&name=live'.format(
                rtmp_name, config.VODRECORD_HOST)

        @staticmethod
        def _end_url(rtmp_name):
            return 'https://{1}/control/record/stop?app={0}&name=live'.format(
                rtmp_name, config.VODRECORD_HOST)

        def _start_record_nolock(self, rtmp_name):
            rtmp_name = rtmp_name.lower()
            if rtmp_name in self._recording_rtmps:
                self._end_record_nolock(rtmp_name)
            if rtmp_name in self._recording_rtmps:
                self._log_warning(
                    'Error: tried to start a recording of racer <{0}>, but failed to end a previously '
                    'started recording.'.format(rtmp_name))
                return None

            curl = pycurl.Curl()
            try:
                new_buffer = BytesIO()
                self._vodstart_buffers[rtmp_name] = new_buffer
                curl.setopt(pycurl.CAINFO, certifi.where())
                curl.setopt(pycurl.URL, self._start_url(rtmp_name))
                curl.setopt(pycurl.WRITEDATA, new_buffer)
                curl.perform()
                self._recording_rtmps.append(rtmp_name)
            except pycurl.error as e:
                self._log_warning(
                    'Pycurl error in start_record({0}): Tried to curl <{1}>. Error: {2}.'.format(
                        rtmp_name,
                        self._start_url(rtmp_name),
                        e))
            finally:
                curl.close()

        def _end_record_nolock(self, rtmp_name):
            rtmp_name = rtmp_name.lower()
            if rtmp_name not in self._recording_rtmps:
                return

            curl = pycurl.Curl()
            try:
                curl.setopt(pycurl.CAINFO, certifi.where())
                curl.setopt(pycurl.URL, self._end_url(rtmp_name))
                curl.setopt(pycurl.WRITEDATA, self._end_buffer)
                curl.perform()
                self._recording_rtmps = [r for r in self._recording_rtmps if r != rtmp_name]
            except pycurl.error as e:
                self._log_warning(
                    'Pycurl error in end_record({0}): Tried to curl <{1}>. Error {2}.'.format(
                        rtmp_name,
                        self._end_url(rtmp_name),
                        e))
            finally:
                curl.close()
