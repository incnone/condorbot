import certifi
import pycurl
from xml.etree import ElementTree
from io import BytesIO


# Returns a list of those names from the list that are still running RTMP streams
def get_streamers(list_of_rtmp_names):
    buffer = BytesIO()
    curl = pycurl.Curl()
    try:
        curl.setopt(pycurl.CAINFO, certifi.where())
        curl.setopt(pycurl.URL, 'https://condor.host/stat')
        curl.setopt(pycurl.WRITEDATA, buffer)
        curl.perform()
    except pycurl.error:
        return []
    finally:
        curl.close()

    names_to_return = []

    etree = ElementTree.fromstring(buffer.getvalue().decode('utf-8'))
    for app in etree.find('server').findall('application'):
        name = app.find('name').text
        if name in list_of_rtmp_names and int(app.find('live').find('nclients').text) > 0:
            names_to_return.append(name)

    return names_to_return
