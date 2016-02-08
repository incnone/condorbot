import asyncio
import datetime
import gspread
import json

from itertools import zip_longest
from oauth2client.client import SignedJwtAssertionCredentials

import config

from condordb import CondorDB
from condormatch import CondorMatch

def grouper(iterable, n, fillvalue=None):
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)

class CondorSheet(object):
    def __init__(self, condor_db):
        self._db = condor_db
        json_key = json.load(open(config.GSHEET_CREDENTIALS_FILENAME))
        scope = ['https://spreadsheets.google.com/feeds']
        credentials = SignedJwtAssertionCredentials(json_key['client_email'], json_key['private_key'].encode(), scope)
        gc = gspread.authorize(credentials)
        self._gsheet = gc.open(config.GSHEET_DOC_NAME)

    def get_matches(self, week):       
        worksheet_name = "Week {}".format(week)
        wks = self._gsheet.worksheet(worksheet_name)
        if wks:
            matches = []
            racer_1_headcell = wks.find("Racer 1")
            racer_1_footcell = wks.find("--------")

            ul_addr = wks.get_addr_int(racer_1_headcell.row+1, racer_1_headcell.col)
            lr_addr = wks.get_addr_int(racer_1_footcell.row-1, racer_1_footcell.col+1)
            racers = wks.range('{0}:{1}'.format(ul_addr, lr_addr))

            for cell in grouper(racers, 2, None):
                print('{0} vs {1}'.format(cell[0].value, cell[1].value))
                r1id = self._db.get_discord_id(cell[0].value)
                r2id = self._db.get_discord_id(cell[1].value)
                if r1id and r2id:
                    matches.append(CondorMatch(r1id, r2id, week))

            return matches
        else:
            print('Couldn\'t find worksheet <{}>.'.worksheet_name)
    
