import asyncio
import datetime
import gspread
import json
import logging
import pytz
import xml
import traceback

from itertools import zip_longest
from oauth2client.client import SignedJwtAssertionCredentials

import condortimestr
import config

from condormatch import CondorMatch


def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)


class CondorSheet(object):
    @staticmethod
    def _log_warning(warning_str):
        logging.getLogger('discord').warning(warning_str)

    @staticmethod
    def _get_match_str(utc_datetime):
        gsheet_tz = pytz.timezone(config.GSHEET_TIMEZONE)
        gsheet_dt = gsheet_tz.normalize(utc_datetime.replace(tzinfo=pytz.utc).astimezone(gsheet_tz))
        return condortimestr.get_gsheet_time_str(gsheet_dt)
    
    def __init__(self, condor_db):
        self._lock = asyncio.Lock()
        self._db = condor_db
        json_key = json.load(open(config.GSHEET_CREDENTIALS_FILENAME))
        scope = ['https://spreadsheets.google.com/feeds']
        self._credentials = SignedJwtAssertionCredentials(
            json_key['client_email'], json_key['private_key'].encode(), scope)
        gc = gspread.authorize(self._credentials)
        self._gsheet = gc.open(config.GSHEET_DOC_NAME)

    def _get_wks(self, week):
        worksheet_name = "Week {}".format(week)
        return self._gsheet.worksheet(worksheet_name)
    
    def _get_standings(self):
        return self._gsheet.worksheet('Standings')

    @staticmethod
    def _get_row(match, wks):
        racer_1_regex = match.racer_1.gsheet_regex
        racer_2_regex = match.racer_2.gsheet_regex
        try:
            racer_1_cells = wks.findall(racer_1_regex)
            racer_2_cells = wks.findall(racer_2_regex)
        except xml.etree.ElementTree.ParseError as e:
            timestamp = datetime.datetime.utcnow()
            print('{0}: XML parse error when looking up racer names in week sheet: {1}, {2}.'.format(
                timestamp.strftime("%Y/%m/%d %H:%M:%S"), match.racer_1.unique_name, match.racer_2.unique_name))
            print(e)
            traceback.print_exc()
            raise
        
        for cell_1 in racer_1_cells:
            for cell_2 in racer_2_cells:
                if cell_1.row == cell_2.row:
                    return cell_1.row

    def _reauthorize(self):
        gc = gspread.authorize(self._credentials)
        self._gsheet = gc.open(config.GSHEET_DOC_NAME)

    @staticmethod
    def _set_best_of_info(match, bestof_str):
        if bestof_str.startswith('bo'):
            try:
                bestof_num = int(bestof_str.lstrip('bo'))
                match.set_best_of(bestof_num)
            except ValueError:
                print('Error parsing <{}> as best-of-N information.'.format(bestof_str))            
        elif bestof_str.startswith('r'):
            try:
                repeat_num = int(bestof_str.lstrip('r'))
                match.set_repeat(repeat_num)
            except ValueError:
                print('Error parsing <{}> as repeat-N information.'.format(bestof_str))
        elif not bestof_str == '':
            print('Error parsing <{}> as best-of-N or repeat-N information.'.format(bestof_str))

    async def _do_with_lock(self, function, *args, **kwargs):
        await self._lock
        try:
            to_return = await function(*args, **kwargs)
            return to_return
        except (xml.etree.ElementTree.ParseError,
                gspread.exceptions.RequestError):
            self._reauthorize()
            to_return = await function(*args, **kwargs)
            return to_return
        finally:
            self._lock.release()

    async def get_matches(self, week):
        return await self._do_with_lock(self._get_matches, week)

    async def _get_matches(self, week):
        wks = self._get_wks(week)
        if wks:
            matches = []
            racer_1_headcell = wks.find("Racer 1")
            racer_1_footcell = wks.find("--------")

            ul_addr = wks.get_addr_int(racer_1_headcell.row+1, racer_1_headcell.col)
            lr_addr = wks.get_addr_int(racer_1_footcell.row-1, racer_1_footcell.col+1)
            racers = wks.range('{0}:{1}'.format(ul_addr, lr_addr))

            for cell in grouper(racers, 2, None):
                racer_1 = self._db.get_from_rtmp_name(cell[0].value.rstrip(' '), register=True)
                racer_2 = self._db.get_from_rtmp_name(cell[1].value.rstrip(' '), register=True)
                if racer_1 and racer_2:
                    new_match = CondorMatch(racer_1, racer_2, week)
                    # Can set best-of info here later
                    matches.append(new_match)

            return matches
        else:
            self._log_warning('Couldn\'t find worksheet for week {}.'.format(week))

    async def unschedule_match(self, match):
        return await self._do_with_lock(self._unschedule_match, match)

    async def _unschedule_match(self, match):
        week = match.week
        wks = self._get_wks(week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
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
                    wks.update_cell(match_row, the_col.col, '')
                else:
                    self._log_warning('Couldn\'t find either the "Date:" or "Scheduled:" column on the GSheet.')
            else:
                self._log_warning('Couldn\'t find match between <{0}> and <{1}> on the GSheet.'.format(
                    match.racer_1.unique_name, match.racer_2.unique_name))
        else:
            self._log_warning('Couldn\'t find worksheet for week {}.'.format(week))

    async def schedule_match(self, match):
        return await self._do_with_lock(self._schedule_match, match)

    async def _schedule_match(self, match):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
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
                    self._log_warning('Couldn\'t find either the "Date:" or "Scheduled:" column on the GSheet.')
            else:
                self._log_warning('Couldn\'t find match between <{0}> and <{1}> on the GSheet.'.format(
                    match.racer_1.unique_name, match.racer_2.unique_name))
        else:
            self._log_warning('Couldn\'t find worksheet for week <{}>.'.format(match.week))

    async def record_match(self, match):
        return await self._do_with_lock(self._record_match, match)

    async def _record_match(self, match):
        match_results = self._db.get_score(match)
        if not match_results:
            return
        
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                winner = ''
                if match_results[0] > match_results[1]:
                    winner = match.racer_1.unique_name
                elif match_results[0] < match_results[1]:
                    winner = match.racer_2.unique_name

                score_list = [match_results[0] + 0.5*match_results[2], match_results[1] + 0.5*match_results[2]]
                score_list = list(sorted(score_list, reverse=True))
                high_score = str(round(score_list[0], 1) if score_list[0] % 1 else int(score_list[0]))
                low_score = str(round(score_list[1], 1) if score_list[1] % 1 else int(score_list[1]))
                score_str = '=("{0}-{1}")'.format(high_score, low_score)
                
                winner_column = wks.find('Winner:')
                if winner_column:
                    wks.update_cell(match_row, winner_column.col, winner)
                else:
                    self._log_warning('Couldn\'t find the "Winner:" column on the GSheet.')
                    return

                score_column = wks.find('Game Score:')
                if score_column:
                    wks.update_cell(match_row, score_column.col, score_str)
                else:
                    self._log_warning('Couldn\'t find the "Game Score:" column on the GSheet.')
                    return
                
                self._update_standings(match, match_results)
            else:
                self._log_warning('Couldn\'t find match between <{0}> and <{1}> on the GSheet.'.format(
                    match.racer_1.unique_name, match.racer_2.unique_name))
        else:
            self._log_warning('Couldn\'t find worksheet for week <{}>.'.format(match.week))

    def _update_standings(self, match, match_results):
        standings = self._get_standings()
        if standings:
            racer_1_regex = match.racer_1.gsheet_regex
            racer_2_regex = match.racer_2.gsheet_regex
            try:
                racer_1_cells = standings.findall(racer_1_regex)
                racer_2_cells = standings.findall(racer_2_regex)
            except xml.etree.ElementTree.ParseError as e:
                timestamp = datetime.datetime.utcnow()
                self._log_warning('{0}: XML parse error when looking up racer names in the standings: '
                                  '{1}, {2}.'.format(timestamp.strftime("%Y/%m/%d %H:%M:%S"),
                                                     match.racer_1.unique_name, match.racer_2.unique_name))
                self._log_warning(e)
                raise
            
            self._set_score(standings, racer_1_cells, racer_2_cells, match_results[0])
            self._set_score(standings, racer_2_cells, racer_1_cells, match_results[1])
        else:
            self._log_warning('Couldn\'t find worksheet <standings>.')

    @staticmethod
    def _set_score(standings, racer_1_cells, racer_2_cells, score):
        for cell_1 in racer_1_cells:
            if cell_1.col == 2:
                for cell_2 in racer_2_cells:
                    if cell_2.row == cell_1.row:
                        standings.update_cell(cell_1.row, cell_2.col - 7, score)
                        return

    async def get_cawmentary(self, match):
        return await self._do_with_lock(self._get_cawmentary, match)

    async def _get_cawmentary(self, match):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                cawmentary_column = wks.find('Cawmentary:')
                if cawmentary_column:
                    cawmentary_cell = wks.cell(match_row, cawmentary_column.col)
                    if not cawmentary_cell.value:
                        return None
                    args = cawmentary_cell.value.split('/')
                    if args and args[0] == 'twitch.tv':
                        return args[len(args) - 1].rstrip(' ')
                else:
                    self._log_warning('Couldn\'t find the Cawmentary: column.')
            else:
                self._log_warning('Couldn\'t find row for match.')
        return None

    async def add_cawmentary(self, match, cawmentator_twitchname):
        return await self._do_with_lock(self._add_cawmentary, match, cawmentator_twitchname)

    async def _add_cawmentary(self, match, cawmentator_twitchname):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                cawmentary_column = wks.find('Cawmentary:')
                if cawmentary_column:
                    cawmentary_cell = wks.cell(match_row, cawmentary_column.col)
                    if cawmentary_cell.value:
                        self._log_warning('Error: tried to add cawmentary to a match that already had it.')
                    else:
                        wks.update_cell(match_row, cawmentary_column.col, 'twitch.tv/{}'.format(cawmentator_twitchname))
                else:
                    self._log_warning('Couldn\'t find the Cawmentary: column.')
            else:
                self._log_warning('Couldn\'t find row for the match.')

    async def remove_cawmentary(self, match):
        return await self._do_with_lock(self._remove_cawmentary, match)

    async def _remove_cawmentary(self, match):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                cawmentary_column = wks.find('Cawmentary:')
                if cawmentary_column:
                    wks.update_cell(match_row, cawmentary_column.col, '')
                else:
                    self._log_warning('Couldn\'t find the Cawmentary: column.')
            else:
                self._log_warning('Couldn\'t find row for the match.')

    async def is_showcase_match(self, match):
        return await self._do_with_lock(self._is_showcase_match, match)

    async def _is_showcase_match(self, match):
        wks = self._get_wks(match.week)
        if wks:
            match_row = self._get_row(match, wks)
            if match_row:
                cawmentary_column = wks.find('Cawmentary:')
                if cawmentary_column:
                    sched_cell = wks.cell(match_row, cawmentary_column.col)
                    if sched_cell and sched_cell.value.lower().startswith("showcase"):
                        return True            
                else:
                    self._log_warning('Couldn\'t find either the "Date:" or "Scheduled:" column on the GSheet.')
            else:
                self._log_warning('Couldn\'t find row for the match.')
        return False
