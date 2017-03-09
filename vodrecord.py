import config
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
        def _start_url(rtmp_name):
            return 'https://{1}/control/record/start?app={0}&name=live&rec={0}'.format(
                rtmp_name, config.VODRECORD_HOST)

        @staticmethod
        def _end_url(rtmp_name):
            return 'https://{1}/control/record/stop?app={0}&name=live&rec={0}'.format(
                rtmp_name, config.VODRECORD_HOST)

        def start_record(self, rtmp_name):
            rtmp_name = rtmp_name.lower()
            if rtmp_name in self._recording_rtmps:
                return

            curl = pycurl.Curl()
            curl.setopt(
                curl.URL,
                self._start_url(rtmp_name))
            curl.perform()
            curl.close()
            self._recording_rtmps.append(rtmp_name)

        def end_record(self, rtmp_name):
            rtmp_name = rtmp_name.lower()
            if rtmp_name not in self._recording_rtmps:
                return

            curl = pycurl.Curl()
            curl.setopt(
                curl.URL,
                self._end_url(rtmp_name))
            curl.perform()
            curl.close()
            self._recording_rtmps = [r for r in self._recording_rtmps if r != rtmp_name]

        def end_all(self):
            for rtmp_name in self._recording_rtmps:
                try:
                    curl = pycurl.Curl()
                    curl.setopt(
                        curl.URL,
                        self._end_url(rtmp_name))
                    curl.perform()
                    curl.close()
                except pycurl.error:
                    pass

            self._recording_rtmps.clear()
