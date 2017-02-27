import calendar
import datetime


def timedelta_to_string(td):
    if td < datetime.timedelta(seconds=0):
        return 'Right now!'

    hrs = td.seconds // 3600
    mins = (td.seconds - hrs * 3600) // 60

    output_str = ''
    if td.days > 0:
        output_str += '{} days, '.format(td.days)
    if hrs > 0:
        output_str += '{} hours, '.format(hrs)
    if mins > 0:
        output_str += '{} minutes, '.format(mins)

    return output_str[:-2]


def get_time_str(dt):
    if not dt:
        return ''
    
    weekday = calendar.day_name[dt.weekday()]
    day = dt.strftime("%d").lstrip('0')
    hour = dt.strftime("%I").lstrip('0')
    pm_str = dt.strftime("%p").lower()
    datestr = dt.strftime("%b {0} @ {1}:%M{2} %Z".format(day, hour, pm_str))
    return weekday + ', ' + datestr


def get_24h_time_str(dt):
    if not dt:
        return ''
    
    weekday = calendar.day_name[dt.weekday()]
    day = dt.strftime("%d").lstrip('0')
    hour = dt.strftime("%H").lstrip('0')
    if hour == '':
        hour = '00'
    datestr = dt.strftime("%b {0} @ {1}:%M %Z".format(day, hour))
    return weekday + ', ' + datestr    


def get_date_time_str(dt):
    weekday = calendar.day_name[dt.weekday()]
    day = dt.strftime("%d").lstrip('0')
    return dt.strftime("{0}, %b {1}".format(weekday, day))


def get_time_time_str(dt):
    hour = dt.strftime("%I").lstrip('0')
    pm_str = dt.strftime("%p").lower()
    return dt.strftime("{0}:%M{1}".format(hour, pm_str))


def get_gsheet_time_str(dt):
    return dt.strftime("%m/%d/%Y %H:%M:%S")
