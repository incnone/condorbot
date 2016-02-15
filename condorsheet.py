import asyncio
import calendar
import datetime
import gspread
import json
import pytz
import re

from itertools import zip_longest
from oauth2client.client import SignedJwtAssertionCredentials

import condortimestr
import config

from condordb import CondorDB
from condormatch import CondorMatch

def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

class CondorSheet(object):
    def _get_match_str(utc_datetime):
        gsheet_tz = pytz.timezone(config.GSHEET_TIMEZONE)
        gsheet_dt = gsheet_tz.normalize(utc_datetime.replace(tzinfo=pytz.utc).astimezone(gsheet_tz))
        return condortimestr.get_gsheet_time_str(gsheet_dt)
    
    def __init__(self, condor_db):
        self._db = condor_db
        json_key = json.load(open(config.GSHEET_CREDENTIALS_FILENAME))
        scope = ['https://spreadsheets.google.com/feeds']
        credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'].encode(), scope)
        gc = gspread.authorize(credentials)
        self._gsheet = gc.open(config.GSHEET_DOC_NAME)

    def _get_wks(self, week):
        worksheet_name = "Week {}".format(week)
        return self._gsheet.worksheet(worksheet_name)
        
    def _get_row(self, match, wks):
        racer_1_cells = wks.findall(match.racer_1.gsheet_regex)
        racer_2_cells = wks.findall(match.racer_2.gsheet_regex)
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
                date_col = None
                sched_col = None
                try:
                    date_col = wks.find('Date:')
                except gspread.exceptions.CellNotFound:
                    date_col = None
                try:
                    sched_col = wks.find('Scheduled:')
                except gspread.exceptions.CellNotFound:
                    sched_col = None
                    
                the_col = date_col if date_col else (sched_col if sched_col else None)
                if the_col:
                    wks.update_cell(match_row, the_col.col, CondorSheet._get_match_str(match.time))
                else:
                    print('Couldn\'t find either the "Date:" or "Scheduled:" column on the GSheet.')

##                time_col = wks.find('Time:')
##                if time_col:
##                    wks.update_cell(match_row, time_col.col, CondorSheet._get_match_time_str(match.time))
##                else:
##                    print('Couldn\'t find the "Time:" column on the GSheet.')
            else:
                print('Couldn\'t find match between <{0}> and <{1}> on the GSheet.'.format(match.racer_1.twitch_name, match.racer_2.twitch_name))
        else:
            print('Couldn\'t find worksheet <{}>.'.worksheet_name)

    def record_match(self, match):
        match_results = self._db.get_score(match)
        if not match_results:
            return
        
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                winner = 'Draw'
                if match_results[0] > match_results[1]:
                    winner = match.racer_1.twitch_name
                elif match_results[0] < match_results[1]:
                    winner = match.racer_2.twitch_name

                score_list = [match_results[0], match_results[1]]
                score_list = list(sorted(score_list, reverse=True))
                score_str = '=("{0}-{1}")'.format(score_list[0], score_list[1])
                
                winner_column = wks.find('Winner:')
                if winner_column:
                    wks.update_cell(match_row, winner_column.col, winner)
                else:
                    print('Couldn\'t find the "Winner:" column on the GSheet.')

                score_column = wks.find('Game Score:')
                if score_column:
                    wks.update_cell(match_row, score_column.col, score_str)
                else:
                    print('Couldn\'t find the "Game Score:" column on the GSheet.')
            else:
                print('Couldn\'t find match between <{0}> and <{1}> on the GSheet.'.format(match.racer_1.twitch_name, match.racer_2.twitch_name))
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
