import asyncio
import calendar
import datetime
import gspread
import json
import pytz

from itertools import zip_longest
from oauth2client.client import SignedJwtAssertionCredentials

import config

from condordb import CondorDB
from condormatch import CondorMatch

def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

class CondorSheet(object):
    def _get_match_time_str(utc_datetime):
        gsheet_tz = pytz.timezone(config.GSHEET_TIMEZONE)
        gsheet_dt = gsheet_tz.normalize(utc_datetime.replace(tzinfo=pytz.utc).astimezone(gsheet_tz))
        weekday = calendar.day_name[gsheet_dt.weekday()]
        day = gsheet_dt.strftime("%d").lstrip('0')
        hour = gsheet_dt.strftime("%I").lstrip('0')
        pm_str = gsheet_dt.strftime("%p").lower()
        datestr = gsheet_dt.strftime("%b {0} @ {1}:%M{2} %Z".format(day, hour, pm_str))
        return weekday + ', ' + datestr

    def __init__(self, condor_db):
        self._db = condor_db
##        json_key = json.load(open(config.GSHEET_CREDENTIALS_FILENAME))
##        scope = ['https://spreadsheets.google.com/feeds']
##        credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'].encode(), scope)
##        gc = gspread.authorize(credentials)
##        self._gsheet = gc.open(config.GSHEET_DOC_NAME)

    def _get_wks(self, week):
        worksheet_name = "Week {}".format(week)
        return self._gsheet.worksheet(worksheet_name)
        
    def _get_row(self, match, wks):
        racer_1_cells = wks.findall(match.racer_1.gsheet_name)
        racer_2_cells = wks.findall(match.racer_2.gsheet_name)
        for cell_1 in racer_1_cells:
            for cell_2 in racer_2_cells:
                if cell_1.row == cell_2.row:
                    return cell_1.row
                
    def get_matches(self, week):       
        wks = self._get_wks(week)
        if wks:
            matches = []
            racer_1_headcell = wks.find("Racer 1")
            racer_1_footcell = wks.find("--------")

            ul_addr = wks.get_addr_int(racer_1_headcell.row+1, racer_1_headcell.col)
            lr_addr = wks.get_addr_int(racer_1_footcell.row-1, racer_1_footcell.col+1)
            racers = wks.range('{0}:{1}'.format(ul_addr, lr_addr))

            for cell in grouper(racers, 2, None):
                racer_1 = self._db.get_from_twitch_name(cell[0].value, register=True)
                racer_2 = self._db.get_from_twitch_name(cell[1].value, register=True)
                if racer_1 and racer_2:
                    matches.append(CondorMatch(racer_1, racer_2, week))

            return matches
        else:
            print('Couldn\'t find worksheet <{}>.'.worksheet_name)

    def schedule_match(self, match):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                scheduled_column = wks.find('Scheduled:')
                if scheduled_column:
                    wks.update_cell(match_row, scheduled_column.col, CondorSheet._get_match_time_str(match.time))
                else:
                    print('Couldn\'t find the "Scheduled:" column on the GSheet.')
            else:
                print('Couldn\'t find match between <{0}> and <{1}> on the GSheet.'.format(match.racer_1.gsheet_name, match.racer_2.gsheet_name))
        else:
            print('Couldn\'t find worksheet <{}>.'.worksheet_name)

    def get_cawmentary(self, match):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                cawmentary_column = wks.find('Cawmentary')
                cawmentary_cell = wks.cell(match_row, cawmentary_column)
                return cawmentary_cell.value

    def add_cawmentary(self, match, cawmentator_twitchname):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                cawmentary_column = wks.find('Cawmentary')
                cawmentary_cell = wks.cell(match_row, cawmentary_column)
                if cawmentary_cell.value:
                    print('Error: tried to add cawmentary to a match that already had it.')
                else:
                    wks.update_cell(match_row, cawmentary_column, 'twitch.tv/{}'.format(cawmentator))

    def remove_cawmentary(self, match):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                cawmentary_column = wks.find('Cawmentary')
                cawmentary_cell = wks.update_cell(match_row, cawmentary_column, '')
