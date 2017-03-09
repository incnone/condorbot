import certifi
import config
import logging
import pycurl


class VodRecorder(object):
    instance = None

    def __init__(self):
        if not VodRecorder.instance:
            VodRecorder.instance = VodRecorder.__VodRecorder()

    def __getattr__(self, name):
        return getattr(self.instance, name)

    class __VodRecorder(object):
        def __init__(self):
            self._recording_rtmps = []

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

        def start_record(self, rtmp_name):
            if not config.RECORDING_ACTIVATED:
                return

            rtmp_name = rtmp_name.lower()
            if rtmp_name in self._recording_rtmps:
                self.end_record(rtmp_name)
            if rtmp_name in self._recording_rtmps:
                self._log_warning(
                    'Error: tried to start a recording of racer <{0}>, but failed to end a previously '
                    'started recording.'.format(rtmp_name))
                return

            curl = pycurl.Curl()
            try:
                curl.setopt(pycurl.CAINFO, certifi.where())
                curl.setopt(curl.URL, self._start_url(rtmp_name))
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

        def end_record(self, rtmp_name):
            if not config.RECORDING_ACTIVATED:
                return

            rtmp_name = rtmp_name.lower()
            if rtmp_name not in self._recording_rtmps:
                return

            curl = pycurl.Curl()
            try:
                curl.setopt(pycurl.CAINFO, certifi.where())
                curl.setopt(curl.URL, self._end_url(rtmp_name))
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

        def end_all(self):
            if not config.RECORDING_ACTIVATED:
                return

            for rtmp_name in self._recording_rtmps:
                curl = pycurl.Curl()
                try:
                    curl.setopt(pycurl.CAINFO, certifi.where())
                    curl.setopt(curl.URL, self._end_url(rtmp_name))
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
