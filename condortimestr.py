import calendar
import datetime

def get_time_str(dt):
    weekday = calendar.day_name[dt.weekday()]
    day = dt.strftime("%d").lstrip('0')
    hour = dt.strftime("%I").lstrip('0')
    pm_str = dt.strftime("%p").lower()
    datestr = dt.strftime("%b {0} @ {1}:%M{2} %Z".format(day, hour, pm_str))
    return weekday + ', ' + datestr
