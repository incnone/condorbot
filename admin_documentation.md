# Condorbot Admin Documentation (for CoNDOR Season 4)

Version: 0.4.5

## Organization

These commands should be entered in the #adminchat channel.

- `.closeweek <week_number>` : Deletes all the race rooms for the specified week number, saving the text in them to a .log file in the /logs/ folder on the server.

- `.makeweek <week_number>` : Makes the race rooms for the specified week number, e.g., you should call `.makeweek 1` once at the beginning of this week, after the matchups have been put on the Google Doc. If this command breaks during execution (this happens sometimes, I think due to request timeouts on the google sheet), simply call it again (`.makeweek 1`). It should make the rooms correctly (possibly with one duplicate room, if it broke at exactly the wrong time; you should check for this).

- `.closeallracechannels` : Closes all the private race channels. You almost certainly don't want to call this unless something has gone very wrong.

- `.remind` : Sends "@racer_1, @racer_2: Please remember to schedule your races!" to all racers in unscheduled matches. `.remind` <text> instead sends "@racer_1, @racer_2: <text>".

- `.forcetransferaccount` : Transfers a racer account from one Discord user to another. Can be called in any channel (not via PM). Usage is `.forcetransferaccount @from_user @to_user`.

## Match management

These commands should be entered in a race channel, before a match.

- `.forcebeginmatch` : Force the match to begin.

- `.forceconfirm` : Force both racers to confirm a suggested time.

- `.forcerescheduleutc [datetime]`: Force the race to be rescheduled for a specific UTC time. Usage is the same as `.suggest`, e.g., `.forcerescheduleutc Feb 5 15:00`.

- `.forceupdate` : Update the room topic and gsheet for the match.

- `.forceunschedule` : Force the match to be unscheduled.

## Races

These commands should be entered in a race channel, during a match.

- `.forcecancel` : Cancels the current race. You will probably need to call `.forcemakenew` after this command to start the next race.

- `.forcecancelrace <race_number>` : Marks a previously recorded race as cancelled.

- `.forcenewrace` : Force the bot to make a new race. This cancels any race in progress.

- `.forceforfeit <discord_name>` : Force a racer to forfeit the race.

- `.forcechangewinner <race_number> <winner_twitch_name>` : Changes the winner for the given race number. (Main use case is for when a close race is reviewed, and on review it's found that the other racer actually finished first, contrary to what bot recorded.)

- `.forcerecordrace [winner | -draw] [time_winner [time_loser]] [-seed seed_number]` : Records a race that the bot did not record (e.g. if it was down). This command is untested atm (warning). Examples:
    - `.forcerecordrace eladdifficult` records eladdifficult as the winner.
    - `.forcerecordrace -draw` records a draw. (This is a bit untested: warning.)
    - `.forcerecordrace eladdifficult 5:08.07 5:12.12 -seed 12345` records eladdifficult as the winner, with a time of 5:08.07, and his opponent as the loser, with a time of 5:12.12, playing on the seed 12345.

- `.forcerecordmatch` : Updates the current match in the gsheet. Useful if bot doesn't update info properly after one of the above commands is called.